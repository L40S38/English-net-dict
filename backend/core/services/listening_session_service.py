from __future__ import annotations

import difflib
import re
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from core.models import (
    ListeningAttempt,
    ListeningLine,
    ListeningScript,
    ListeningSession,
    ListeningWeakPhrase,
    ListeningWordResult,
    Phrase,
    Word,
)

_WORD_RE = re.compile(r"[A-Za-z']+")


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD_RE.finditer(text or "")]


def create_session(db: Session, script: ListeningScript) -> ListeningSession:
    session = ListeningSession(script_id=script.id)
    db.add(session)
    db.flush()
    return session


def list_sessions(db: Session, status: str | None = None) -> list[ListeningSession]:
    stmt = select(ListeningSession).order_by(ListeningSession.updated_at.desc())
    if status:
        stmt = stmt.where(ListeningSession.status == status)
    return list(db.scalars(stmt))


def delete_session(db: Session, session: ListeningSession) -> None:
    db.delete(session)
    db.flush()


def update_session(
    db: Session,
    session: ListeningSession,
    *,
    current_step: str | None = None,
    playback_speed: float | None = None,
    dictation_level: int | None = None,
    status: str | None = None,
) -> ListeningSession:
    if current_step is not None:
        session.current_step = current_step
    if playback_speed is not None:
        session.playback_speed = playback_speed
    if dictation_level is not None:
        session.dictation_level = dictation_level
    if status is not None:
        session.status = status
        if status == "completed" and session.completed_at is None:
            session.completed_at = datetime.utcnow()
    db.flush()
    return session


def _resolve_word_id(db: Session, token: str, cache: dict[str, int | None]) -> int | None:
    if token in cache:
        return cache[token]
    word_id = db.scalar(select(Word.id).where(func.lower(Word.word) == token))
    cache[token] = word_id
    return word_id


def _resolve_phrase_id(db: Session, phrase_text: str, cache: dict[str, int | None]) -> int | None:
    key = phrase_text.lower()
    if key in cache:
        return cache[key]
    phrase_id = db.scalar(select(Phrase.id).where(func.lower(Phrase.text) == key))
    cache[key] = phrase_id
    return phrase_id


def _find_wrong_spans(correctness: list[bool]) -> list[tuple[int, int]]:
    """Returns (start, end) ranges of contiguous wrong words, for grouping
    consecutive mistakes into a candidate phrase rather than only single
    words."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for idx, is_correct in enumerate(correctness):
        if not is_correct and start is None:
            start = idx
        elif is_correct and start is not None:
            spans.append((start, idx))
            start = None
    if start is not None:
        spans.append((start, len(correctness)))
    return spans


def _align_tokens(correct_tokens: list[str], user_tokens: list[str]) -> list[bool]:
    """Marks each correct token as matched if it participates in a matching
    block against the user's tokens, so a single inserted/dropped/misheard
    word doesn't shift every word after it out of alignment (autojunk=False
    since common short words like "the"/"is" shouldn't be treated as junk)."""
    matcher = difflib.SequenceMatcher(a=correct_tokens, b=user_tokens, autojunk=False)
    correctness = [False] * len(correct_tokens)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            correctness[block.a + offset] = True
    return correctness


def _grade_tokens(correct_tokens: list[str], user_tokens: list[str]) -> tuple[bool, list[bool]]:
    word_correctness = _align_tokens(correct_tokens, user_tokens)
    is_line_correct = all(word_correctness)
    return is_line_correct, word_correctness


def record_attempt(
    db: Session,
    session: ListeningSession,
    line: ListeningLine,
    dictation_level: int,
    user_text: str,
) -> ListeningAttempt:
    correct_tokens = _tokenize(line.text)
    user_tokens = _tokenize(user_text)
    is_line_correct, word_correctness = _grade_tokens(correct_tokens, user_tokens)

    primary_audio = next((variant for variant in line.audio_variants if variant.is_primary), None)
    voice = primary_audio.voice if primary_audio else (line.speaker_ref.voice if line.speaker_ref else None)

    attempt = ListeningAttempt(
        session_id=session.id,
        line_id=line.id,
        dictation_level=dictation_level,
        user_text=user_text,
        is_correct=is_line_correct,
        voice=voice,
    )
    db.add(attempt)
    db.flush()

    word_id_cache: dict[str, int | None] = {}
    for correct_token, is_correct in zip(correct_tokens, word_correctness):
        db.add(
            ListeningWordResult(
                attempt_id=attempt.id,
                word_text=correct_token,
                matched_word_id=_resolve_word_id(db, correct_token, word_id_cache),
                is_correct=is_correct,
            )
        )
    db.flush()
    return attempt


def grade_read_aloud_lines(lines: list[ListeningLine], user_text: str) -> list[dict]:
    """Grades a single read-aloud transcript covering the whole script against
    each line's text, without persisting anything since read-aloud recordings
    aren't kept. Alignment runs once across the whole script's token sequence
    rather than per line, so one STT insertion/deletion doesn't cascade into a
    wall of false negatives for every word that follows it."""
    user_tokens = _tokenize(user_text)
    line_token_lists = [_tokenize(line.text) for line in lines]
    all_correct_tokens = [token for tokens in line_token_lists for token in tokens]
    word_correctness = _align_tokens(all_correct_tokens, user_tokens)

    results: list[dict] = []
    cursor = 0
    for line, correct_tokens in zip(lines, line_token_lists):
        line_correctness = word_correctness[cursor : cursor + len(correct_tokens)]
        cursor += len(correct_tokens)
        results.append(
            {
                "line_id": line.id,
                "is_correct": all(line_correctness),
                "word_results": [
                    {"id": idx, "word_text": word_text, "matched_word_id": None, "is_correct": is_correct}
                    for idx, (word_text, is_correct) in enumerate(zip(correct_tokens, line_correctness))
                ],
            }
        )
    return results


def record_read_aloud_attempts(
    db: Session,
    session: ListeningSession,
    lines: list[ListeningLine],
    user_text: str,
) -> dict:
    """Grades a read-aloud transcript and persists one attempt per line
    (step="read_aloud") so weak words/phrases feed into the same analytics as
    dictation, without keeping the recording itself or its raw transcript.
    Returns the score plus the raw wrong word/phrase lists; turning those into
    actual advice text is the caller's job (see listening_feedback_service)."""
    line_grades = grade_read_aloud_lines(lines, user_text)
    lines_by_id = {line.id: line for line in lines}
    word_id_cache: dict[str, int | None] = {}
    phrase_id_cache: dict[str, int | None] = {}

    total_words = 0
    correct_words = 0
    correct_long_words: list[str] = []
    wrong_phrases: list[str] = []
    wrong_single_words: list[str] = []

    for grade in line_grades:
        line = lines_by_id[grade["line_id"]]
        attempt = ListeningAttempt(
            session_id=session.id,
            line_id=line.id,
            dictation_level=0,
            step="read_aloud",
            user_text="",
            is_correct=grade["is_correct"],
        )
        db.add(attempt)
        db.flush()

        word_texts = [w["word_text"] for w in grade["word_results"]]
        correctness = [w["is_correct"] for w in grade["word_results"]]
        total_words += len(word_texts)
        correct_words += sum(correctness)

        for word_text, is_correct in zip(word_texts, correctness):
            db.add(
                ListeningWordResult(
                    attempt_id=attempt.id,
                    word_text=word_text,
                    matched_word_id=_resolve_word_id(db, word_text, word_id_cache),
                    is_correct=is_correct,
                )
            )
            if is_correct and len(word_text) >= _LONG_WORD_MIN_LEN:
                correct_long_words.append(word_text)

        phrase_covered_indices: set[int] = set()
        for start, end in _find_wrong_spans(correctness):
            if end - start >= 2:
                phrase_text = " ".join(word_texts[start:end])
                matched_phrase_id = _resolve_phrase_id(db, phrase_text, phrase_id_cache)
                if matched_phrase_id is not None:
                    db.add(
                        ListeningWeakPhrase(
                            attempt_id=attempt.id,
                            phrase_text=phrase_text,
                            matched_phrase_id=matched_phrase_id,
                        )
                    )
                    wrong_phrases.append(phrase_text)
                    phrase_covered_indices.update(range(start, end))
                    continue
            for idx in range(start, end):
                if idx not in phrase_covered_indices:
                    wrong_single_words.append(word_texts[idx])

    db.flush()

    score = round(correct_words / total_words * 100) if total_words else 0
    return {
        "score": score,
        "correct_long_words": list(dict.fromkeys(correct_long_words)),
        "wrong_words": list(dict.fromkeys(wrong_single_words)),
        "wrong_phrases": list(dict.fromkeys(wrong_phrases)),
        "lines": line_grades,
    }


_LONG_WORD_MIN_LEN = 7


def build_fallback_good_points(score: int, correct_long_words: list[str]) -> list[str]:
    """Template-based good points, used when the LLM-based feedback in
    listening_feedback_service is unavailable or fails."""
    points: list[str] = []
    if score == 100:
        points.append("全文を正確に読み上げられました。")
    elif score >= 90:
        points.append("全体的に高い精度で読み上げられました。")
    elif score >= 70:
        points.append("大部分の単語を正しく読み上げられました。")

    highlighted = list(dict.fromkeys(correct_long_words))[:5]
    if highlighted:
        points.append("発音が難しい単語「" + "」「".join(highlighted) + "」を正確に発音できていました。")

    if not points:
        points.append("発音できた単語もありました。引き続き練習しましょう。")
    return points


def build_fallback_review_points(wrong_phrases: list[str], wrong_single_words: list[str]) -> list[str]:
    points: list[str] = []
    unique_phrases = list(dict.fromkeys(wrong_phrases))[:5]
    if unique_phrases:
        points.append("次の熟語の発音を見直しましょう: " + "、".join(unique_phrases))

    unique_words = list(dict.fromkeys(wrong_single_words))[:8]
    if unique_words:
        points.append("次の単語の発音を見直しましょう: " + "、".join(unique_words))

    if not points:
        points.append("特に大きな間違いはありませんでした。引き続き音読を続けましょう。")
    return points


def get_weak_word_stats(db: Session, limit: int = 50) -> list[dict]:
    wrong_count = func.sum(case((ListeningWordResult.is_correct.is_(False), 1), else_=0))
    total_count = func.count()
    matched_word_id = func.max(ListeningWordResult.matched_word_id)
    stmt = (
        select(
            ListeningWordResult.word_text,
            total_count.label("total"),
            wrong_count.label("wrong"),
            matched_word_id.label("matched_word_id"),
        )
        .group_by(ListeningWordResult.word_text)
        .having(wrong_count > 0)
        .order_by(wrong_count.desc(), total_count.desc())
        .limit(limit)
    )
    results: list[dict] = []
    for row in db.execute(stmt).all():
        total = int(row.total)
        wrong = int(row.wrong)
        results.append(
            {
                "word_text": row.word_text,
                "total": total,
                "wrong": wrong,
                "accuracy": round((total - wrong) / total, 3) if total else 0.0,
                "matched_word_id": row.matched_word_id,
            }
        )
    return results


def get_weak_phrase_stats(db: Session, limit: int = 50) -> list[dict]:
    count = func.count()
    stmt = (
        select(
            ListeningWeakPhrase.phrase_text,
            count.label("count"),
            func.max(ListeningWeakPhrase.matched_phrase_id).label("matched_phrase_id"),
        )
        .group_by(ListeningWeakPhrase.phrase_text)
        .order_by(count.desc())
        .limit(limit)
    )
    return [
        {
            "phrase_text": row.phrase_text,
            "count": int(row.count),
            "matched_phrase_id": row.matched_phrase_id,
        }
        for row in db.execute(stmt).all()
    ]


def get_voice_accuracy_weights(db: Session, *, min_attempts: int = 5, bias: float = 1.0) -> dict[str, float]:
    """Per-voice random-pick weights, biased toward voices the learner has
    historically found harder to understand (lower dictation accuracy). A
    voice with 0% accuracy gets at most `1 + bias` the weight of a voice with
    100% accuracy, keeping the nudge slight rather than dominant. Voices
    without enough history are omitted so callers can default them to a
    neutral weight."""
    wrong_count = func.sum(case((ListeningWordResult.is_correct.is_(False), 1), else_=0))
    total_count = func.count()
    stmt = (
        select(
            ListeningAttempt.voice,
            total_count.label("total"),
            wrong_count.label("wrong"),
        )
        .join(ListeningWordResult, ListeningWordResult.attempt_id == ListeningAttempt.id)
        .where(ListeningAttempt.voice.is_not(None))
        .group_by(ListeningAttempt.voice)
    )
    weights: dict[str, float] = {}
    for row in db.execute(stmt).all():
        total = int(row.total)
        if total < min_attempts:
            continue
        accuracy = (total - int(row.wrong)) / total
        weights[row.voice] = 1.0 + bias * (1.0 - accuracy)
    return weights
