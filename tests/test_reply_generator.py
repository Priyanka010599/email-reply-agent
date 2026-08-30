import json

import pytest

from email_agent.models.classification import EmailClassification
from email_agent.reply_generator import ReplyGenerationError, generate_reply
from tests.conftest import FailingClaudeClient, FakeClaudeClient, reply_json


@pytest.fixture
def classification() -> EmailClassification:
    return EmailClassification(category="sales_inquiry", confidence=0.9, reasoning="Asks about the product")


def test_generate_reply_valid_output(sample_email, classification):
    client = FakeClaudeClient(reply_json(subject="Re: Hi", body="Thanks for reaching out..."))

    reply = generate_reply(sample_email, classification, client)

    assert reply.subject == "Re: Hi"
    assert "Thanks" in reply.body


def test_generate_reply_malformed_json(sample_email, classification):
    client = FakeClaudeClient("not json")

    with pytest.raises(ReplyGenerationError):
        generate_reply(sample_email, classification, client)


def test_generate_reply_missing_field(sample_email, classification):
    client = FakeClaudeClient(json.dumps({"subject": "Re: Hi"}))

    with pytest.raises(ReplyGenerationError):
        generate_reply(sample_email, classification, client)


def test_generate_reply_api_error(sample_email, classification):
    client = FailingClaudeClient()

    with pytest.raises(ReplyGenerationError):
        generate_reply(sample_email, classification, client)
