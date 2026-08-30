"""Reading emails and golden cases from disk.

Sample email files use a simple, human-editable format:

    From: customer@example.com
    Subject: Question about your product

    The body starts after the first blank line and runs to the end of the file.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from email_agent.models.email import Email
from email_agent.models.golden_case import GoldenCase


class EmailFileError(Exception):
    """Raised when an email file is missing or cannot be parsed."""


class GoldenDatasetError(Exception):
    """Raised when the golden dataset file is missing or malformed."""


def parse_email_text(text: str) -> Email:
    if "\n\n" in text:
        header_block, body = text.split("\n\n", 1)
    else:
        header_block, body = text, ""

    sender = ""
    subject = ""
    for line in header_block.splitlines():
        if line.lower().startswith("from:"):
            sender = line.split(":", 1)[1].strip()
        elif line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()

    try:
        return Email(sender=sender, subject=subject, body=body.strip())
    except ValidationError as exc:
        raise EmailFileError(f"Email content is invalid: {exc}") from exc


def load_email_file(path: str) -> Email:
    file_path = Path(path)
    if not file_path.exists():
        raise EmailFileError(f"Email file not found: {path}")
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EmailFileError(f"Could not read email file {path}: {exc}") from exc
    return parse_email_text(text)


def load_golden_cases(path: str) -> list[GoldenCase]:
    file_path = Path(path)
    if not file_path.exists():
        raise GoldenDatasetError(f"Golden dataset not found: {path}")

    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoldenDatasetError(f"Golden dataset is not valid JSON: {exc}") from exc

    try:
        return [GoldenCase.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise GoldenDatasetError(f"Golden dataset entry failed validation: {exc}") from exc
