"""Email -> Claude -> EmailClassification."""

from __future__ import annotations

from pydantic import ValidationError

from email_agent.llm.client import ClaudeClient, ClaudeClientError
from email_agent.llm.json_utils import JsonExtractionError, extract_json_object
from email_agent.llm.prompts import CLASSIFICATION_SYSTEM_PROMPT, build_classification_prompt
from email_agent.models.classification import EmailClassification
from email_agent.models.email import Email


class ClassificationError(Exception):
    """Raised when an email could not be classified."""


def classify_email(email: Email, client: ClaudeClient) -> EmailClassification:
    prompt = build_classification_prompt(email)

    try:
        raw_response = client.generate(prompt, system=CLASSIFICATION_SYSTEM_PROMPT)
    except ClaudeClientError as exc:
        raise ClassificationError(f"Claude API call failed during classification: {exc}") from exc

    try:
        data = extract_json_object(raw_response)
    except JsonExtractionError as exc:
        raise ClassificationError(f"Classifier returned non-JSON output: {exc}") from exc

    try:
        return EmailClassification.model_validate(data)
    except ValidationError as exc:
        raise ClassificationError(f"Classifier output failed validation: {exc}") from exc
