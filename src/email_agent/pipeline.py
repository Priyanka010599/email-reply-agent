"""Orchestration layer: validate -> classify -> reply -> persist -> (optionally) evaluate.

This is the one place that wires the pieces together, so both the CLI and any
future caller (a script, a test, a web handler) can drive the agent through a
single `process()` call instead of re-implementing the sequence.
"""

from __future__ import annotations

from dataclasses import dataclass

from email_agent.classifier import classify_email
from email_agent.config import EvalThresholds
from email_agent.database.repository import Repository
from email_agent.evaluator import evaluate_reply
from email_agent.llm.client import ClaudeClient
from email_agent.models.classification import EmailClassification
from email_agent.models.email import Email
from email_agent.models.evaluation import EvaluationResult
from email_agent.models.golden_case import GoldenCase
from email_agent.models.reply import GeneratedReply
from email_agent.reply_generator import generate_reply


@dataclass(frozen=True)
class PipelineResult:
    run_id: int | None
    email: Email
    classification: EmailClassification
    reply: GeneratedReply


class EmailAgentPipeline:
    def __init__(self, client: ClaudeClient, repository: Repository, thresholds: EvalThresholds) -> None:
        self._client = client
        self._repository = repository
        self._thresholds = thresholds

    def process(self, email: Email, *, persist: bool = True) -> PipelineResult:
        classification = classify_email(email, self._client)
        reply = generate_reply(email, classification, self._client)

        run_id = None
        if persist:
            run_id = self._repository.insert_run(email, classification, reply)

        return PipelineResult(run_id=run_id, email=email, classification=classification, reply=reply)

    def evaluate_golden_case(self, case: GoldenCase) -> tuple[PipelineResult, EvaluationResult]:
        result = self.process(case.email)
        evaluation = evaluate_reply(case, result.reply, self._client, self._thresholds)
        self._repository.insert_evaluation(result.run_id, evaluation, golden_case_id=case.id)
        return result, evaluation
