"""Centralized configuration loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class EvalThresholds:
    """Pass criteria for the evaluation harness. All score fields are on a 1-5 scale."""

    min_professionalism: float
    min_tone_match: float
    min_relevance: float

    def passes(self, professionalism: float, tone_match: float, relevance: float, hallucination_detected: bool) -> bool:
        if hallucination_detected:
            return False
        return (
            professionalism >= self.min_professionalism
            and tone_match >= self.min_tone_match
            and relevance >= self.min_relevance
        )


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str | None
    anthropic_workspace_id: str | None
    claude_model: str
    claude_max_tokens: int
    database_path: str
    eval_thresholds: EvalThresholds


def load_config() -> Config:
    """Read configuration from the environment, applying safe defaults."""
    return Config(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_workspace_id=os.environ.get("ANTHROPIC_WORKSPACE_ID") or None,
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
        claude_max_tokens=int(os.environ.get("CLAUDE_MAX_TOKENS", "1024")),
        database_path=os.environ.get("DATABASE_PATH", "data/email_agent.db"),
        eval_thresholds=EvalThresholds(
            min_professionalism=float(os.environ.get("EVAL_MIN_PROFESSIONALISM", "4")),
            min_tone_match=float(os.environ.get("EVAL_MIN_TONE_MATCH", "4")),
            min_relevance=float(os.environ.get("EVAL_MIN_RELEVANCE", "4")),
        ),
    )
