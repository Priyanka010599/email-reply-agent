import sqlite3

import pytest

from email_agent.database.repository import Repository
from email_agent.database.schema import init_db
from email_agent.models.classification import EmailClassification
from email_agent.models.evaluation import EvaluationResult
from email_agent.models.reply import GeneratedReply


@pytest.fixture
def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def repository(connection):
    return Repository(connection)


def test_init_db_creates_tables(connection):
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"agent_runs", "evaluations", "golden_cases"} <= tables


def test_insert_and_get_run(repository, sample_email):
    classification = EmailClassification(category="sales_inquiry", confidence=0.9, reasoning="x")
    reply = GeneratedReply(subject="Re: Hi", body="Thanks!")

    run_id = repository.insert_run(sample_email, classification, reply)
    row = repository.get_run(run_id)

    assert row is not None
    assert row["sender"] == sample_email.sender
    assert row["category"] == "sales_inquiry"
    assert row["generated_subject"] == "Re: Hi"


def test_get_run_returns_none_for_missing_id(repository):
    assert repository.get_run(999) is None


def test_insert_evaluation(repository, sample_email):
    classification = EmailClassification(category="support_request", confidence=0.8, reasoning="x")
    reply = GeneratedReply(subject="Re: Hi", body="We're looking into it.")
    run_id = repository.insert_run(sample_email, classification, reply)

    evaluation = EvaluationResult(
        professionalism_score=5,
        tone_match_score=4,
        relevance_score=5,
        hallucination_detected=False,
        overall_score=4.6,
        passed=True,
        reasoning="Solid reply.",
    )
    eval_id = repository.insert_evaluation(run_id, evaluation, golden_case_id="support_001")

    stored = repository.get_evaluation(eval_id)
    assert stored["run_id"] == run_id
    assert stored["passed"] == 1
    assert stored["golden_case_id"] == "support_001"


def test_sync_golden_cases_is_idempotent(repository, sample_golden_case, connection):
    repository.sync_golden_cases([sample_golden_case])
    repository.sync_golden_cases([sample_golden_case])

    row = connection.execute("SELECT COUNT(*) AS c FROM golden_cases").fetchone()
    assert row["c"] == 1


def test_evaluation_report_aggregates_correctly(repository, sample_email):
    classification = EmailClassification(category="sales_inquiry", confidence=0.9, reasoning="x")
    reply = GeneratedReply(subject="Re: Hi", body="Thanks!")

    passing = EvaluationResult(
        professionalism_score=5, tone_match_score=5, relevance_score=5,
        hallucination_detected=False, overall_score=5.0, passed=True, reasoning="Great",
    )
    failing = EvaluationResult(
        professionalism_score=2, tone_match_score=2, relevance_score=2,
        hallucination_detected=True, overall_score=1.0, passed=False, reasoning="Bad, hallucinated",
    )

    run_id_1 = repository.insert_run(sample_email, classification, reply)
    run_id_2 = repository.insert_run(sample_email, classification, reply)
    repository.insert_evaluation(run_id_1, passing, golden_case_id="case_a")
    repository.insert_evaluation(run_id_2, failing, golden_case_id="case_b")

    report = repository.get_evaluation_report()

    assert report.total_cases == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.pass_rate == 50.0
    assert report.hallucination_rate == 50.0
    assert len(report.failing_cases) == 1
    assert report.failing_cases[0].golden_case_id == "case_b"


def test_evaluation_report_empty(repository):
    report = repository.get_evaluation_report()
    assert report.total_cases == 0
    assert report.pass_rate == 0.0
    assert report.failing_cases == []
