"""Email + EmailClassification -> Claude -> GeneratedReply."""

from __future__ import annotations

from pydantic import ValidationError

from email_agent.llm.client import ClaudeClient, ClaudeClientError
from email_agent.llm.json_utils import JsonExtractionError, extract_json_object
from email_agent.llm.prompts import REPLY_SYSTEM_PROMPT, build_reply_prompt
from email_agent.models.classification import EmailClassification
from email_agent.models.email import Email
from email_agent.models.reply import GeneratedReply


class ReplyGenerationError(Exception):
    """Raised when a reply could not be generated."""


def generate_reply(email: Email, classification: EmailClassification, client: ClaudeClient) -> GeneratedReply:
    prompt = build_reply_prompt(email, classification.category)

    try:
        raw_response = client.generate(prompt, system=REPLY_SYSTEM_PROMPT)
    except ClaudeClientError as exc:
        raise ReplyGenerationError(f"Claude API call failed during reply generation: {exc}") from exc

    try:
        data = extract_json_object(raw_response)
    except JsonExtractionError as exc:
        raise ReplyGenerationError(f"Reply generator returned non-JSON output: {exc}") from exc

    try:
        return GeneratedReply.model_validate(data)
    except ValidationError as exc:
        raise ReplyGenerationError(f"Reply generator output failed validation: {exc}") from exc
