"""NORMALIZE a text using only what the configuration supplies (removal tokens, letter case), so a written value can
be looked up in a configured ordering and its aliases. Nothing here knows what any value means."""
from app.monitoring.request import Normalization


def normalize(text: str, n: Normalization) -> str:
    if not n.enabled:
        return text
    out = text.lower() if n.case_insensitive else text
    for token in n.remove:            # in the order the configuration lists them
        out = out.replace(token.lower() if n.case_insensitive else token, "")
    return out
