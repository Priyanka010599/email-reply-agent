import json

import pytest

from email_agent import cli
from email_agent.config import Config, EvalThresholds
from tests.conftest import FakeClaudeClient, classification_json, evaluation_json, reply_json


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        anthropic_api_key="unused-because-client-is-mocked",
        anthropic_workspace_id=None,
        claude_model="claude-sonnet-5",
        claude_max_tokens=1024,
        database_path=str(tmp_path / "test.db"),
        eval_thresholds=EvalThresholds(min_professionalism=4, min_tone_match=4, min_relevance=4),
    )


@pytest.fixture(autouse=True)
def patch_load_config(monkeypatch, config):
    monkeypatch.setattr(cli, "load_config", lambda: config)


def _patch_claude_client(monkeypatch, responses):
    fake = FakeClaudeClient(responses)
    monkeypatch.setattr(cli, "ClaudeClient", lambda _config: fake)
    return fake


def test_cmd_run_success(monkeypatch, tmp_path, capsys):
    email_path = tmp_path / "email.txt"
    email_path.write_text("From: a@b.com\nSubject: Hello\n\nCan you tell me about pricing?", encoding="utf-8")
    _patch_claude_client(
        monkeypatch,
        [classification_json(category="sales_inquiry", confidence=0.77), reply_json(subject="Re: Hello")],
    )

    exit_code = cli.main(["run", str(email_path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Category: sales_inquiry" in out
    assert "Confidence: 0.77" in out
    assert "Re: Hello" in out


def test_cmd_run_missing_file(monkeypatch, capsys):
    _patch_claude_client(monkeypatch, [])

    exit_code = cli.main(["run", "does/not/exist.txt"])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "not found" in err.lower()


def test_cmd_eval_and_report(monkeypatch, tmp_path, capsys):
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(
        json.dumps(
            [
                {
                    "id": "case_a",
                    "email": {"sender": "a@b.com", "subject": "Hi", "body": "What does your product do?"},
                    "expected_category": "sales_inquiry",
                    "expected_tone": "friendly_professional",
                    "must_address": ["what the product does"],
                    "must_not_invent": ["pricing"],
                    "quality_notes": "test case",
                }
            ]
        ),
        encoding="utf-8",
    )
    _patch_claude_client(
        monkeypatch,
        [
            classification_json(category="sales_inquiry"),
            reply_json(),
            evaluation_json(professionalism_score=5, tone_match_score=5, relevance_score=5),
        ],
    )

    eval_exit_code = cli.main(["eval", "--golden-path", str(golden_path)])
    eval_out = capsys.readouterr().out

    assert eval_exit_code == 0
    assert "Running 1 evaluation cases" in eval_out
    assert "case_a" in eval_out
    assert "Evaluation Summary" in eval_out

    report_exit_code = cli.main(["report"])
    report_out = capsys.readouterr().out

    assert report_exit_code == 0
    assert "Evaluation Report" in report_out
    assert "Cases evaluated: 1" in report_out


def test_cmd_report_with_no_data(monkeypatch, capsys):
    _patch_claude_client(monkeypatch, [])

    exit_code = cli.main(["report"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "No evaluation results found" in out


def test_cmd_db_init(monkeypatch, config, capsys):
    _patch_claude_client(monkeypatch, [])

    exit_code = cli.main(["db-init"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert config.database_path in out
