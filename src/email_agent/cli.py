"""Command-line interface: `python -m email_agent <command>`."""

from __future__ import annotations

import argparse
import sqlite3
import sys

from email_agent.classifier import ClassificationError
from email_agent.config import Config, load_config
from email_agent.database.connection import get_connection
from email_agent.database.repository import Repository
from email_agent.database.schema import init_db
from email_agent.email_io import EmailFileError, GoldenDatasetError, load_email_file, load_golden_cases
from email_agent.evaluator import EvaluationError
from email_agent.llm.client import ClaudeClient, ClaudeClientError
from email_agent.pipeline import EmailAgentPipeline
from email_agent.reply_generator import ReplyGenerationError

DEFAULT_GOLDEN_PATH = "data/golden/golden_cases.json"

AgentError = (ClassificationError, ReplyGenerationError, EvaluationError, ClaudeClientError)


def _build_pipeline(config: Config, repository: Repository) -> EmailAgentPipeline:
    client = ClaudeClient(config)
    return EmailAgentPipeline(client, repository, config.eval_thresholds)


def cmd_db_init(config: Config, _args: argparse.Namespace) -> int:
    connection = get_connection(config.database_path)
    init_db(connection)
    print(f"Database initialized at {config.database_path}")
    return 0


def cmd_run(config: Config, args: argparse.Namespace) -> int:
    email = load_email_file(args.path)

    connection = get_connection(config.database_path)
    init_db(connection)
    repository = Repository(connection)
    pipeline = _build_pipeline(config, repository)

    result = pipeline.process(email)

    print(f"Category: {result.classification.category}")
    print(f"Confidence: {result.classification.confidence:.2f}")
    print()
    print("Generated Reply")
    print("---------------")
    print(f"Subject: {result.reply.subject}")
    print()
    print(result.reply.body)
    print()
    print(f"(saved as run #{result.run_id})")
    return 0


def cmd_eval(config: Config, args: argparse.Namespace) -> int:
    golden_cases = load_golden_cases(args.golden_path)

    connection = get_connection(config.database_path)
    init_db(connection)
    repository = Repository(connection)
    repository.sync_golden_cases(golden_cases)
    pipeline = _build_pipeline(config, repository)

    print(f"Running {len(golden_cases)} evaluation cases...")
    print()

    results = []
    for case in golden_cases:
        _run_result, evaluation = pipeline.evaluate_golden_case(case)
        results.append((case, evaluation))
        status = "PASS" if evaluation.passed else "FAIL"
        print(f"{status:<6}{case.id:<15}{evaluation.overall_score:<6.1f}")

    total = len(results)
    if total == 0:
        print("No golden cases found.")
        return 0

    passed = sum(1 for _, e in results if e.passed)
    failed = total - passed
    avg_prof = sum(e.professionalism_score for _, e in results) / total
    avg_tone = sum(e.tone_match_score for _, e in results) / total
    avg_relevance = sum(e.relevance_score for _, e in results) / total
    hallucination_rate = sum(1 for _, e in results if e.hallucination_detected) / total

    print()
    print("Evaluation Summary")
    print("------------------")
    print(f"Cases: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass rate: {100 * passed / total:.1f}%")
    print()
    print(f"Professionalism: {avg_prof:.1f}/5")
    print(f"Tone match:       {avg_tone:.1f}/5")
    print(f"Relevance:        {avg_relevance:.1f}/5")
    print(f"Hallucination:    {100 * hallucination_rate:.1f}%")
    return 0


def cmd_report(config: Config, _args: argparse.Namespace) -> int:
    connection = get_connection(config.database_path)
    init_db(connection)
    repository = Repository(connection)

    report = repository.get_evaluation_report()
    if report.total_cases == 0:
        print("No evaluation results found. Run `python -m email_agent eval` first.")
        return 0

    print("Evaluation Report")
    print("-----------------")
    print(f"Cases evaluated: {report.total_cases}")
    print(f"Passed: {report.passed}")
    print(f"Failed: {report.failed}")
    print(f"Pass rate: {report.pass_rate}%")
    print()
    print(f"Professionalism: {report.avg_professionalism}/5")
    print(f"Tone match:       {report.avg_tone_match}/5")
    print(f"Relevance:        {report.avg_relevance}/5")
    print(f"Hallucination:    {report.hallucination_rate}%")

    if report.failing_cases:
        print()
        print("Failing cases")
        print("-------------")
        for case in report.failing_cases:
            case_label = case.golden_case_id or f"run eval #{case.evaluation_id}"
            print(f"- {case_label} ({case.category}) overall={case.overall_score} hallucination={case.hallucination_detected}")
            print(f"    subject: {case.subject}")
            print(f"    reasoning: {case.reasoning}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="email_agent", description="LLM-powered email reply agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Classify and reply to a single email file")
    run_parser.add_argument("path", help="Path to a plain-text email file")
    run_parser.set_defaults(func=cmd_run)

    eval_parser = subparsers.add_parser("eval", help="Run the golden dataset through the full pipeline")
    eval_parser.add_argument("--golden-path", default=DEFAULT_GOLDEN_PATH, help="Path to golden_cases.json")
    eval_parser.set_defaults(func=cmd_eval)

    report_parser = subparsers.add_parser("report", help="Show aggregate evaluation metrics from SQLite")
    report_parser.set_defaults(func=cmd_report)

    db_init_parser = subparsers.add_parser("db-init", help="Create the SQLite database and tables")
    db_init_parser.set_defaults(func=cmd_db_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    try:
        return args.func(config, args)
    except (EmailFileError, GoldenDatasetError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except AgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
