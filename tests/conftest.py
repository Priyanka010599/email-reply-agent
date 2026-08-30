"""Shared test fixtures. No test in this suite calls the live Claude API."""

from __future__ import annotations

import json

import pytest

from email_agent.config import EvalThresholds
from email_agent.llm.client import ClaudeClientError
from email_agent.models.email import Email
from email_agent.models.golden_case import GoldenCase


class FakeClaudeClient:
    """Duck-compatible stand-in for ClaudeClient. Returns queued canned responses."""

    def __init__(self, responses):
        self._responses = list(responses) if isinstance(responses, (list, tuple)) else [responses]
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        if not self._responses:
            raise AssertionError("FakeClaudeClient ran out of queued responses")
        return self._responses.pop(0)


class FailingClaudeClient:
    """Duck-compatible stand-in that always raises, simulating an API failure."""

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        raise ClaudeClientError("simulated API failure")


@pytest.fixture
def sample_email() -> Email:
    return Email(
        sender="jordan.lee@brightpath.io",
        subject="Quick question about Loomis Analytics",
        body="Could you tell me a bit more about what your product does?",
    )


@pytest.fixture
def sample_golden_case(sample_email: Email) -> GoldenCase:
    return GoldenCase(
        id="sales_001",
        email=sample_email,
        expected_category="sales_inquiry",
        expected_tone="friendly_professional",
        must_address=["what the product does"],
        must_not_invent=["pricing"],
        quality_notes="Baseline sales inquiry.",
    )


@pytest.fixture
def default_thresholds() -> EvalThresholds:
    return EvalThresholds(min_professionalism=4, min_tone_match=4, min_relevance=4)


def classification_json(category="sales_inquiry", confidence=0.9, reasoning="Looks like a sales inquiry.") -> str:
    return json.dumps({"category": category, "confidence": confidence, "reasoning": reasoning})


def reply_json(subject="Re: Quick question about Loomis Analytics", body="Hi Jordan, thanks for reaching out...") -> str:
    return json.dumps({"subject": subject, "body": body})


def evaluation_json(
    professionalism_score=5,
    tone_match_score=5,
    relevance_score=5,
    hallucination_detected=False,
    reasoning="Clear, professional, and directly on topic.",
) -> str:
    return json.dumps(
        {
            "professionalism_score": professionalism_score,
            "tone_match_score": tone_match_score,
            "relevance_score": relevance_score,
            "hallucination_detected": hallucination_detected,
            "reasoning": reasoning,
        }
    )
