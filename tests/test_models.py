import pytest
from pydantic import ValidationError

from email_agent.models.classification import EmailClassification
from email_agent.models.email import Email
from email_agent.models.evaluation import EvaluationResult
from email_agent.models.reply import GeneratedReply


def test_email_valid():
    email = Email(sender="a@b.com", subject="Hi", body="Hello there")
    assert email.sender == "a@b.com"


def test_email_rejects_blank_body():
    with pytest.raises(ValidationError):
        Email(sender="a@b.com", subject="Hi", body="   ")


def test_classification_valid():
    classification = EmailClassification(category="sales_inquiry", confidence=0.8, reasoning="Asks about pricing")
    assert classification.category == "sales_inquiry"


def test_classification_rejects_invalid_category():
    with pytest.raises(ValidationError):
        EmailClassification(category="not_a_real_category", confidence=0.8, reasoning="x")


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_classification_rejects_out_of_range_confidence(confidence):
    with pytest.raises(ValidationError):
        EmailClassification(category="other", confidence=confidence, reasoning="x")


def test_reply_valid():
    reply = GeneratedReply(subject="Re: Hi", body="Thanks for your message.")
    assert reply.subject == "Re: Hi"


def test_reply_rejects_empty_body():
    with pytest.raises(ValidationError):
        GeneratedReply(subject="Re: Hi", body="")


def test_evaluation_result_valid():
    result = EvaluationResult(
        professionalism_score=5,
        tone_match_score=4,
        relevance_score=5,
        hallucination_detected=False,
        overall_score=4.7,
        passed=True,
        reasoning="Good reply.",
    )
    assert result.passed is True


@pytest.mark.parametrize("field", ["professionalism_score", "tone_match_score", "relevance_score"])
def test_evaluation_result_rejects_out_of_range_scores(field):
    kwargs = dict(
        professionalism_score=5,
        tone_match_score=5,
        relevance_score=5,
        hallucination_detected=False,
        overall_score=5.0,
        passed=True,
        reasoning="x",
    )
    kwargs[field] = 6
    with pytest.raises(ValidationError):
        EvaluationResult(**kwargs)


def test_evaluation_result_rejects_overall_score_above_five():
    with pytest.raises(ValidationError):
        EvaluationResult(
            professionalism_score=5,
            tone_match_score=5,
            relevance_score=5,
            hallucination_detected=False,
            overall_score=5.5,
            passed=True,
            reasoning="x",
        )
