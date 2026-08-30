"""Data access layer. All SQL lives here, parameterized, behind typed methods."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from email_agent.models.classification import EmailClassification
from email_agent.models.email import Email
from email_agent.models.evaluation import EvaluationResult
from email_agent.models.golden_case import GoldenCase
from email_agent.models.reply import GeneratedReply


@dataclass(frozen=True)
class FailingCase:
    evaluation_id: int
    golden_case_id: str | None
    subject: str
    category: str
    professionalism_score: int
    tone_match_score: int
    relevance_score: int
    hallucination_detected: bool
    overall_score: float
    reasoning: str


@dataclass(frozen=True)
class EvaluationReport:
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    avg_professionalism: float
    avg_tone_match: float
    avg_relevance: float
    hallucination_rate: float
    failing_cases: list[FailingCase] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def insert_run(self, email: Email, classification: EmailClassification, reply: GeneratedReply) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO agent_runs
                (timestamp, sender, subject, body, category, confidence, generated_subject, generated_body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                email.sender,
                email.subject,
                email.body,
                classification.category,
                classification.confidence,
                reply.subject,
                reply.body,
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def get_run(self, run_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def insert_evaluation(
        self,
        run_id: int,
        evaluation: EvaluationResult,
        golden_case_id: str | None = None,
    ) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO evaluations
                (run_id, golden_case_id, professionalism_score, tone_match_score,
                 relevance_score, hallucination_detected, overall_score, passed,
                 reasoning, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                golden_case_id,
                evaluation.professionalism_score,
                evaluation.tone_match_score,
                evaluation.relevance_score,
                int(evaluation.hallucination_detected),
                evaluation.overall_score,
                int(evaluation.passed),
                evaluation.reasoning,
                _utc_now(),
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def get_evaluation(self, evaluation_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM evaluations WHERE id = ?", (evaluation_id,)).fetchone()
        return dict(row) if row else None

    def sync_golden_cases(self, cases: list[GoldenCase]) -> None:
        for case in cases:
            self._conn.execute(
                """
                INSERT INTO golden_cases
                    (id, sender, subject, body, expected_category, expected_tone,
                     must_address, must_not_invent, quality_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    sender=excluded.sender,
                    subject=excluded.subject,
                    body=excluded.body,
                    expected_category=excluded.expected_category,
                    expected_tone=excluded.expected_tone,
                    must_address=excluded.must_address,
                    must_not_invent=excluded.must_not_invent,
                    quality_notes=excluded.quality_notes
                """,
                (
                    case.id,
                    case.email.sender,
                    case.email.subject,
                    case.email.body,
                    case.expected_category,
                    case.expected_tone,
                    json.dumps(case.must_address),
                    json.dumps(case.must_not_invent),
                    case.quality_notes,
                ),
            )
        self._conn.commit()

    def get_evaluation_report(self) -> EvaluationReport:
        rows = self._conn.execute(
            """
            SELECT e.*, r.subject AS run_subject, r.category AS run_category
            FROM evaluations e
            JOIN agent_runs r ON r.id = e.run_id
            ORDER BY e.id
            """
        ).fetchall()

        if not rows:
            return EvaluationReport(
                total_cases=0,
                passed=0,
                failed=0,
                pass_rate=0.0,
                avg_professionalism=0.0,
                avg_tone_match=0.0,
                avg_relevance=0.0,
                hallucination_rate=0.0,
                failing_cases=[],
            )

        total = len(rows)
        passed = sum(1 for row in rows if row["passed"])
        failed = total - passed
        avg_professionalism = sum(row["professionalism_score"] for row in rows) / total
        avg_tone_match = sum(row["tone_match_score"] for row in rows) / total
        avg_relevance = sum(row["relevance_score"] for row in rows) / total
        hallucination_rate = sum(1 for row in rows if row["hallucination_detected"]) / total

        failing_cases = [
            FailingCase(
                evaluation_id=row["id"],
                golden_case_id=row["golden_case_id"],
                subject=row["run_subject"],
                category=row["run_category"],
                professionalism_score=row["professionalism_score"],
                tone_match_score=row["tone_match_score"],
                relevance_score=row["relevance_score"],
                hallucination_detected=bool(row["hallucination_detected"]),
                overall_score=row["overall_score"],
                reasoning=row["reasoning"],
            )
            for row in rows
            if not row["passed"]
        ]

        return EvaluationReport(
            total_cases=total,
            passed=passed,
            failed=failed,
            pass_rate=round(100 * passed / total, 1),
            avg_professionalism=round(avg_professionalism, 2),
            avg_tone_match=round(avg_tone_match, 2),
            avg_relevance=round(avg_relevance, 2),
            hallucination_rate=round(100 * hallucination_rate, 1),
            failing_cases=failing_cases,
        )
