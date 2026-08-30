import pytest

from email_agent.evaluator import EvaluationError, evaluate_reply
from email_agent.models.reply import GeneratedReply
from tests.conftest import FailingClaudeClient, FakeClaudeClient, evaluation_json


@pytest.fixture
def reply() -> GeneratedReply:
    return GeneratedReply(subject="Re: Hi", body="Thanks for reaching out, here's what our product does...")


def test_evaluate_reply_valid_passing(sample_golden_case, reply, default_thresholds):
    client = FakeClaudeClient(evaluation_json(professionalism_score=5, tone_match_score=5, relevance_score=5))

    result = evaluate_reply(sample_golden_case, reply, client, default_thresholds)

    assert result.passed is True
    assert result.hallucination_detected is False
    assert result.overall_score > 4.0


def test_evaluate_reply_hallucination_forces_low_score_and_fail(sample_golden_case, reply, default_thresholds):
    client = FakeClaudeClient(
        evaluation_json(professionalism_score=5, tone_match_score=5, relevance_score=5, hallucination_detected=True)
    )

    result = evaluate_reply(sample_golden_case, reply, client, default_thresholds)

    assert result.hallucination_detected is True
    assert result.passed is False
    assert result.overall_score <= 2.5


def test_evaluate_reply_low_scores_fail(sample_golden_case, reply, default_thresholds):
    client = FakeClaudeClient(evaluation_json(professionalism_score=2, tone_match_score=2, relevance_score=2))

    result = evaluate_reply(sample_golden_case, reply, client, default_thresholds)

    assert result.passed is False


def test_evaluate_reply_malformed_judge_output(sample_golden_case, reply, default_thresholds):
    client = FakeClaudeClient("not valid json")

    with pytest.raises(EvaluationError):
        evaluate_reply(sample_golden_case, reply, client, default_thresholds)


def test_evaluate_reply_api_error(sample_golden_case, reply, default_thresholds):
    client = FailingClaudeClient()

    with pytest.raises(EvaluationError):
        evaluate_reply(sample_golden_case, reply, client, default_thresholds)
