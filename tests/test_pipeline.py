import sqlite3

import pytest

from email_agent.classifier import ClassificationError
from email_agent.config import EvalThresholds
from email_agent.database.repository import Repository
from email_agent.database.schema import init_db
from email_agent.pipeline import EmailAgentPipeline
from tests.conftest import FailingClaudeClient, FakeClaudeClient, classification_json, evaluation_json, reply_json


@pytest.fixture
def repository():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield Repository(conn)
    conn.close()


@pytest.fixture
def thresholds() -> EvalThresholds:
    return EvalThresholds(min_professionalism=4, min_tone_match=4, min_relevance=4)


def test_process_runs_classifier_then_generator_then_persists(sample_email, repository, thresholds):
    client = FakeClaudeClient(
        [
            classification_json(category="sales_inquiry", confidence=0.85),
            reply_json(subject="Re: Hi", body="Thanks for reaching out..."),
        ]
    )
    pipeline = EmailAgentPipeline(client, repository, thresholds)

    result = pipeline.process(sample_email)

    assert result.classification.category == "sales_inquiry"
    assert result.reply.subject == "Re: Hi"
    assert result.run_id is not None
    assert len(client.calls) == 2

    stored = repository.get_run(result.run_id)
    assert stored["sender"] == sample_email.sender
    assert stored["category"] == "sales_inquiry"


def test_process_without_persist_does_not_write_to_db(sample_email, repository, thresholds):
    client = FakeClaudeClient([classification_json(), reply_json()])
    pipeline = EmailAgentPipeline(client, repository, thresholds)

    result = pipeline.process(sample_email, persist=False)

    assert result.run_id is None
    report = repository.get_evaluation_report()
    assert report.total_cases == 0


def test_process_propagates_classifier_failure(sample_email, repository, thresholds):
    pipeline = EmailAgentPipeline(FailingClaudeClient(), repository, thresholds)

    with pytest.raises(ClassificationError):
        pipeline.process(sample_email)


def test_evaluate_golden_case_persists_linked_evaluation(sample_golden_case, repository, thresholds):
    client = FakeClaudeClient(
        [
            classification_json(category="sales_inquiry"),
            reply_json(),
            evaluation_json(professionalism_score=5, tone_match_score=5, relevance_score=5),
        ]
    )
    pipeline = EmailAgentPipeline(client, repository, thresholds)

    result, evaluation = pipeline.evaluate_golden_case(sample_golden_case)

    assert evaluation.passed is True
    report = repository.get_evaluation_report()
    assert report.total_cases == 1
    assert report.passed == 1
