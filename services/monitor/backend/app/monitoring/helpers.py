import json
from typing import Any


class ConfigError(Exception):
    """The PS configuration read from the database is incomplete or malformed."""


class SpecGap(Exception):
    """The configuration asks for something the specification leaves undefined."""


def get_path(doc: Any, path: str) -> Any:
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def is_hashable(value: Any) -> bool:
    """Only hashable values can be grouped, counted as distinct or looked up."""
    try:
        hash(value)
    except TypeError:
        return False
    return True


def whole_number(value: Any) -> int | None:
    """An integer value, or the integer that a text of decimal digits spells (surrounding blanks ignored).
    Anything else (booleans, fractions, other text, None) is not a whole number."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value.strip())
    return None


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"     # as the Data Schema writes Boolean values
    return "—" if value is None else str(value)


def describe_config(cfg: Any, prefix: str = "") -> list[str]:
    """Generic listing of a configuration for 'what is checked'."""
    lines: list[str] = []
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            lines += describe_config(v, f"{prefix}{k}.")
    elif isinstance(cfg, list) and cfg and all(isinstance(i, dict) for i in cfg):
        lines.append(f"{prefix[:-1]}: {len(cfg)} item(s)")
    elif isinstance(cfg, list):
        lines.append(f"{prefix[:-1]}: " + ", ".join(json.dumps(i, ensure_ascii=False, default=str) for i in cfg))
    else:
        lines.append(f"{prefix[:-1]}: {json.dumps(cfg, ensure_ascii=False, default=str)}")
    return lines
