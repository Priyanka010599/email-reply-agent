"""Judge a generated reply against a golden case using Claude as an LLM judge.

The raw judged scores (professionalism, tone match, relevance, hallucination)
come from the model. The aggregate score and pass/fail decision are computed
here, deterministically, so the weighting and thresholds stay auditable and
configurable instead of being hidden inside a prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from email_agent.config import EvalThresholds
from email_agent.llm.client import ClaudeClient, ClaudeClientError
from email_agent.llm.json_utils import JsonExtractionError, extract_json_object
from email_agent.llm.prompts import EVALUATION_SYSTEM_PROMPT, build_evaluation_prompt
from email_agent.models.evaluation import EvaluationResult
from email_agent.models.golden_case import GoldenCase
from email_agent.models.reply import GeneratedReply

# Aggregate score weighting. Relevance matters most (did it actually answer the
# question), professionalism next, tone last among the three judged scores.
# Hallucination is not part of the weighted sum: it is a hard override below,
# since a confidently wrong answer is worse than a merely mediocre one.
PROFESSIONALISM_WEIGHT = 0.35
TONE_WEIGHT = 0.25
RELEVANCE_WEIGHT = 0.40


class _JudgeOutput(BaseModel):
    professionalism_score: int
    tone_match_score: int
    relevance_score: int
    hallucination_detected: bool
    reasoning: str


class EvaluationError(Exception):
    """Raised when a reply could not be evaluated."""


def _compute_overall_score(professionalism: int, tone: int, relevance: int, hallucination_detected: bool) -> float:
    weighted = (
        professionalism * PROFESSIONALISM_WEIGHT
        + tone * TONE_WEIGHT
        + relevance * RELEVANCE_WEIGHT
    )
    if hallucination_detected:
        # A hallucinated reply cannot score above the midpoint, regardless of
        # how polished or on-topic it otherwise reads.
        weighted = min(weighted, 2.5)
    return round(weighted, 2)


def evaluate_reply(
    golden_case: GoldenCase,
    reply: GeneratedReply,
    client: ClaudeClient,
    thresholds: EvalThresholds,
) -> EvaluationResult:
    prompt = build_evaluation_prompt(
        email=golden_case.email,
        expected_category=golden_case.expected_category,
        expected_tone=golden_case.expected_tone,
        must_address=golden_case.must_address,
        must_not_invent=golden_case.must_not_invent,
        reply_subject=reply.subject,
        reply_body=reply.body,
    )

    try:
        raw_response = client.generate(prompt, system=EVALUATION_SYSTEM_PROMPT)
    except ClaudeClientError as exc:
        raise EvaluationError(f"Claude API call failed during evaluation: {exc}") from exc

    try:
        data = extract_json_object(raw_response)
    except JsonExtractionError as exc:
        raise EvaluationError(f"Evaluator returned non-JSON output: {exc}") from exc

    try:
        judged = _JudgeOutput.model_validate(data)
    except ValidationError as exc:
        raise EvaluationError(f"Evaluator output failed validation: {exc}") from exc

    overall_score = _compute_overall_score(
        judged.professionalism_score,
        judged.tone_match_score,
        judged.relevance_score,
        judged.hallucination_detected,
    )
    passed = thresholds.passes(
        professionalism=judged.professionalism_score,
        tone_match=judged.tone_match_score,
        relevance=judged.relevance_score,
        hallucination_detected=judged.hallucination_detected,
    )

    return EvaluationResult(
        professionalism_score=judged.professionalism_score,
        tone_match_score=judged.tone_match_score,
        relevance_score=judged.relevance_score,
        hallucination_detected=judged.hallucination_detected,
        overall_score=overall_score,
        passed=passed,
        reasoning=judged.reasoning,
    )
