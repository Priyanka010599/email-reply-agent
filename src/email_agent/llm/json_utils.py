"""Shared helper for pulling a JSON object out of a Claude text response."""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class JsonExtractionError(Exception):
    """Raised when no valid JSON object could be found in the model output."""


def extract_json_object(text: str) -> dict:
    """Parse a JSON object from `text`, tolerating markdown code fences and
    leading/trailing prose that some models add despite instructions not to."""
    candidates = [text.strip()]

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidates.insert(0, fence_match.group(1).strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise JsonExtractionError(f"Could not find a JSON object in model output: {text!r}")
