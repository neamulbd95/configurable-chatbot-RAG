"""Detects conversational small talk (greetings, pleasantries) so it can
bypass the grounded-retrieval gate (FR-4.2) — that gate exists to stop the
service inventing answers about *data*, not to make it refuse "good
morning". Deliberately a narrow, deterministic pattern match rather than an
LLM-based intent classifier: it must never misclassify an actual data
question as small talk, since that would silently skip grounding for a
question that needed it."""

from __future__ import annotations

import re

_SMALL_TALK_PATTERNS = [
    r"hi|hello|hey|yo|howdy",
    r"good\s*(morning|afternoon|evening|day|night)",
    r"how('?s| is| are)\s*(it going|things|you( doing)?)",
    r"what'?s up",
    r"thanks|thank you|thx|ty",
    r"bye|goodbye|see (you|ya)|good night",
    r"who are you|what are you|what can you do|help",
]

# Anchored to the whole (trimmed, punctuation-stripped) message — "hi" is
# small talk, "hi, what's the price of the Widget?" is not.
_COMPILED = re.compile(rf"^({'|'.join(_SMALL_TALK_PATTERNS)})[\s!?.,]*$", re.IGNORECASE)


def is_small_talk(message: str) -> bool:
    return bool(_COMPILED.match(message.strip()))
