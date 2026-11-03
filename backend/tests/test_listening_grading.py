from __future__ import annotations

from sqlalchemy.orm import Session

from core.models import ListeningLine, ListeningScript, ListeningSession, ListeningSpeaker, ListeningWordResult
from core.services.listening_session_service import (
    _align_tokens,
    _grade_tokens,
    _tokenize,
    grade_read_aloud_lines,
    record_attempt,
)


def test_tokenize_lowercases_and_strips_punctuation() -> None:
    assert _tokenize("Hello, World! It's me.") == ["hello", "world", "it's", "me"]


def test_align_tokens_exact_match_marks_everything_correct() -> None:
    tokens = ["the", "quick", "brown", "fox"]
    assert _align_tokens(tokens, list(tokens)) == [True, True, True, True]


def test_align_tokens_single_dropped_word_does_not_cascade() -> None:
    """A single missing word should only fail that word, not every word after it.

    This is the behavior difference from the previous zip_longest-based
    positional comparison, which would have marked every token from the
    drop point onward as wrong.
    """
    correct = ["i", "went", "to", "the", "store", "yesterday"]
    user = ["i", "went", "the", "store", "yesterday"]  # dropped "to"
    correctness = _align_tokens(correct, user)
    assert correctness == [True, True, False, True, True, True]


def test_align_tokens_single_inserted_word_does_not_cascade() -> None:
    correct = ["i", "went", "to", "the", "store"]
    user = ["i", "went", "really", "to", "the", "store"]  # inserted "really"
    correctness = _align_tokens(correct, user)
    assert correctness == [True, True, True, True, True]


def test_align_tokens_misheard_word_only_fails_that_word() -> None:
    correct = ["she", "sells", "sea", "shells"]
    user = ["she", "sells", "sees", "shells"]  # "sea" misheard as "sees"
    correctness = _align_tokens(correct, user)
    assert correctness == [True, True, False, True]


def test_grade_tokens_line_is_correct_only_when_all_words_match() -> None:
    is_correct, correctness = _grade_tokens(["a", "b", "c"], ["a", "b", "c"])
    assert is_correct is True
    assert correctness == [True, True, True]

    is_correct, correctness = _grade_tokens(["a", "b", "c"], ["a", "x", "c"])
    assert is_correct is False
    assert correctness == [True, False, True]


def test_grade_read_aloud_lines_does_not_cascade_across_line_boundary() -> None:
    lines = [
        _FakeLine(id=1, text="Good morning everyone"),
        _FakeLine(id=2, text="Welcome to the show"),
    ]
    user_text = "Good everyone welcome to the show"  # dropped "morning"
    results = grade_read_aloud_lines(lines, user_text)

    assert results[0]["line_id"] == 1
    assert [wr["is_correct"] for wr in results[0]["word_results"]] == [True, False, True]
    assert results[0]["is_correct"] is False
    assert results[1]["line_id"] == 2
    assert [wr["is_correct"] for wr in results[1]["word_results"]] == [True, True, True, True]
    assert results[1]["is_correct"] is True


class _FakeLine:
    def __init__(self, id: int, text: str) -> None:
        self.id = id
        self.text = text


def test_record_attempt_persists_non_cascading_word_results(db_session: Session) -> None:
    script = ListeningScript(title="Test script")
    db_session.add(script)
    db_session.flush()

    speaker = ListeningSpeaker(script_id=script.id, label="Narrator", voice="alloy")
    db_session.add(speaker)
    db_session.flush()

    line = ListeningLine(
        script_id=script.id,
        speaker_id=speaker.id,
        sort_order=0,
        text="I went to the store yesterday",
    )
    db_session.add(line)
    db_session.flush()

    session = ListeningSession(script_id=script.id)
    db_session.add(session)
    db_session.flush()

    attempt = record_attempt(db_session, session, line, dictation_level=0, user_text="I went the store yesterday")

    assert attempt.is_correct is False
    word_results = (
        db_session.query(ListeningWordResult)
        .filter(ListeningWordResult.attempt_id == attempt.id)
        .order_by(ListeningWordResult.id)
        .all()
    )
    assert [wr.is_correct for wr in word_results] == [True, True, False, True, True, True]
