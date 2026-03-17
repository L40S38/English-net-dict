from __future__ import annotations

import nltk
from nltk.corpus import wordnet as wn

from app.config import settings

_WORDNET_READY = False


def ensure_wordnet() -> None:
    global _WORDNET_READY
    if _WORDNET_READY:
        return
    nltk.data.path.append(settings.nltk_data_dir)
    try:
        wn.ensure_loaded()
    except LookupError:
        nltk.download("wordnet", download_dir=settings.nltk_data_dir, quiet=True)
        nltk.download("omw-1.4", download_dir=settings.nltk_data_dir, quiet=True)
    wn.ensure_loaded()
    _WORDNET_READY = True


def get_wordnet_snapshot(word: str) -> dict:
    ensure_wordnet()
    synsets = wn.synsets(word)
    entries: list[dict] = []
    synonyms: set[str] = set()
    for i, syn in enumerate(synsets[:8]):
        lemma_names = [name.replace("_", " ") for name in syn.lemma_names()]
        for name in lemma_names:
            if name.lower() != word.lower():
                synonyms.add(name)
        entries.append(
            {
                "part_of_speech": syn.pos(),
                "definition": syn.definition(),
                "examples": syn.examples()[:2],
                "lemma_names": lemma_names[:6],
                "order": i,
            }
        )
    return {"word": word, "entries": entries, "synonyms": sorted(synonyms)[:20]}
