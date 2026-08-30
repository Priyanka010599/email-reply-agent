import pytest

from email_agent.classifier import ClassificationError, classify_email
from tests.conftest import FailingClaudeClient, FakeClaudeClient, classification_json


def test_classify_email_valid_output(sample_email):
    client = FakeClaudeClient(classification_json(category="sales_inquiry", confidence=0.92))

    result = classify_email(sample_email, client)

    assert result.category == "sales_inquiry"
    assert result.confidence == 0.92
    assert len(client.calls) == 1


def test_classify_email_malformed_json(sample_email):
    client = FakeClaudeClient("this is not json at all")

    with pytest.raises(ClassificationError):
        classify_email(sample_email, client)


def test_classify_email_invalid_category(sample_email):
    client = FakeClaudeClient(classification_json(category="not_a_real_category"))

    with pytest.raises(ClassificationError):
        classify_email(sample_email, client)


def test_classify_email_confidence_out_of_range(sample_email):
    client = FakeClaudeClient(classification_json(confidence=1.5))

    with pytest.raises(ClassificationError):
        classify_email(sample_email, client)


def test_classify_email_api_error(sample_email):
    client = FailingClaudeClient()

    with pytest.raises(ClassificationError):
        classify_email(sample_email, client)


def test_classify_email_tolerates_markdown_fences(sample_email):
    fenced = f"```json\n{classification_json()}\n```"
    client = FakeClaudeClient(fenced)

    result = classify_email(sample_email, client)

    assert result.category == "sales_inquiry"
