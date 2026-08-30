# email-reply-agent

An LLM-powered agent that classifies inbound customer emails and drafts
replies with Claude, then grades its own output against a golden dataset
using an LLM-as-judge evaluation harness. Built as a small, fully-typed,
end-to-end reference project: classification → generation → evaluation →
persistence → CLI reporting.

## Why this exists

Most "LLM demo" projects stop at "call the model and print the answer."
This one is built the way you'd actually want an email-automation agent to
ship: typed inputs and outputs at every boundary (Pydantic), a hallucination
check baked into the evaluation harness instead of an afterthought, results
persisted so quality can be tracked over time, and a test suite that runs
with zero network access. It's deliberately small — no frameworks, no
orchestration engine, no vector store — because the point is to demonstrate
judgment about LLM application structure, not to show off tooling.

## Architecture

```
                    ┌───────────────┐
                    │ Incoming Email│
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │  Classifier   │   sales_inquiry / support_request / other
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │Reply Generator│   drafts a reply, forbidden from
                    └───────┬───────┘   inventing pricing/features/promises
                            ↓
                    ┌───────────────┐
                    │   Evaluator   │   LLM-judge scores + deterministic
                    └───────┬───────┘   aggregate score & pass/fail
                            ↓
                    ┌───────────────┐
                    │    SQLite     │   agent_runs, evaluations, golden_cases
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │ CLI / Reports │
                    └───────────────┘
```

`ClaudeClient` (`src/email_agent/llm/client.py`) is the only module that
imports the Anthropic SDK. Classification, generation, and evaluation each
depend on a simple `generate(prompt) -> str` interface, which is why they can
be tested with a fake client and no network access.

## Setup

```bash
git clone <this-repo>
cd email-reply-agent
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"
cp .env.example .env          # then add your ANTHROPIC_API_KEY
```

Requires Python 3.11+.

## Environment variables

Set these in `.env` (see `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key. Required for `run` and `eval`. | *(none)* |
| `ANTHROPIC_WORKSPACE_ID` | Only needed for an "identity-linked" key issued via SSO under a multi-workspace org — find it in the Console under Settings > Workspaces. Leave blank for a standard personal key. | *(none)* |
| `CLAUDE_MODEL` | Model used for classification, generation, and evaluation. | `claude-sonnet-5` |
| `CLAUDE_MAX_TOKENS` | Max tokens per Claude completion. | `1024` |
| `DATABASE_PATH` | SQLite file path. Created automatically. | `data/email_agent.db` |
| `EVAL_MIN_PROFESSIONALISM` / `EVAL_MIN_TONE_MATCH` / `EVAL_MIN_RELEVANCE` | Pass thresholds (1-5 scale) for the evaluation harness. | `4` each |

`.env` is gitignored. Never commit a real API key.

## Running the agent

```bash
python -m email_agent run data/sample_emails/sales_inquiry.txt
```

```
Category: sales_inquiry
Confidence: 0.94

Generated Reply
---------------
Subject: Re: Quick question about Loomis Analytics

Hi Jordan, ...

(saved as run #1)
```

Every `run` is persisted to SQLite. Sample inputs live in
`data/sample_emails/` — one per category.

Other commands:

```bash
python -m email_agent eval      # run all golden cases through the full pipeline
python -m email_agent report    # aggregate metrics from everything persisted so far
python -m email_agent db-init   # create the SQLite file and tables explicitly
```

## Running tests

```bash
pytest
```

44 tests, zero live API calls — every Claude call is replaced with a fake
client that returns canned JSON (see `tests/conftest.py`). This means the
suite is deterministic and runs the same with or without an API key.

## Running evaluations

```bash
python -m email_agent eval
```

```
Running 15 evaluation cases...

PASS  sales_001      4.8
PASS  sales_002      4.6
FAIL  support_003    3.1
...

Evaluation Summary
------------------
Cases: 15
Passed: 12
Failed: 3
Pass rate: 80.0%

Professionalism: 4.4/5
Tone match:       4.2/5
Relevance:        4.5/5
Hallucination:    6.7%
```

All numbers above are illustrative of the *shape* of the output — every
figure the CLI actually prints is computed from real evaluation results in
that run, never hardcoded (see `src/email_agent/cli.py::cmd_eval`).
`eval` requires `ANTHROPIC_API_KEY` to be set, since both reply generation
and judging are live model calls. **This project's own automated verification
was run without an API key available in that environment** — the full test
suite (44/44) was run and passed against mocked Claude responses, and the
`run`/`report`/`db-init` commands were exercised live, but `eval` was not
executed against the real API. Anyone cloning this repo with a valid key can
run it directly; the code path is identical to what the tests already
exercise against fakes.

`python -m email_agent report` reads back whatever has already been
persisted to SQLite (across however many past `eval` runs), independent of
whether the run that populated it happened in this session.

## Evaluation methodology

**Golden dataset.** `data/golden/golden_cases.json` has 15 hand-written cases
covering the scenarios that actually break email agents: pricing questions
(pressure to invent a number), demo requests (pressure to invent a
confirmed time slot), unsupported feature/integration questions (pressure to
confirm something unverified), missing-information account questions,
one-line emails with almost no context, long multi-paragraph emails, emails
with several distinct questions bundled together, a frustrated customer, a
product complaint, a genuinely ambiguous message, and an untargeted
newsletter. Each case specifies `must_address` (what a good reply has to
cover) and `must_not_invent` (facts that would be a hallucination if stated
as true) rather than an exact expected reply string — the harness grades
*substance*, not wording.

**LLM-as-judge.** For each case, the pipeline runs email → classify → reply,
then a separate Claude call (`src/email_agent/llm/prompts.py::build_evaluation_prompt`)
judges the generated reply against the case's original email, expected tone,
and `must_address` / `must_not_invent` lists. The judge returns four raw
signals: `professionalism_score` (1-5), `tone_match_score` (1-5),
`relevance_score` (1-5), and `hallucination_detected` (bool).

**Scoring.** The aggregate score is computed in code, not by the model, so
the weighting is auditable and tunable (`src/email_agent/evaluator.py`):

- Relevance: 40% — did it actually answer what was asked
- Professionalism: 35% — grammar, tone, structure, appropriateness
- Tone match: 25% — did it match the expected emotional register

This differs slightly from a naive equal split because a professional,
well-tuned reply that doesn't answer the question is still a failure; the
project spec's suggested 30/25/35/10 split treated hallucination as a small
weighted component, but a *confidently wrong* answer is worse than a
mediocre one, so hallucination is instead a hard override: any detected
hallucination caps the aggregate score at 2.5/5, regardless of how polished
the rest of the reply is.

**Pass/fail.** A case passes when `professionalism_score >= 4`,
`tone_match_score >= 4`, `relevance_score >= 4`, and no hallucination was
detected — all four thresholds configurable via `.env`
(`src/email_agent/config.py::EvalThresholds`). These are hard boolean gates,
not folded into the weighted average, so a single missed threshold fails the
case even if the aggregate score looks fine.

**Limitations of LLM-based evaluation.** The judge is itself a language
model and can be inconsistent between runs, biased toward verbose or
confident-sounding replies, or simply wrong about whether a claim is
actually unsupported. Using the same underlying model family for both
generation and judging also risks shared blind spots — a fact the *generator*
model considers "safe" to assume might not register as a hallucination to a
judge with the same training. Golden-case coverage is intentionally broad
but still only 15 cases; a production system would need continuous,
much larger-scale evaluation and periodic human spot-checks of the judge
itself.

## Example (illustrative)

**Inbound** (`data/sample_emails/sales_inquiry.txt`):

> From: jordan.lee@brightpath.io
> Subject: Quick question about Loomis Analytics
>
> I came across Loomis Analytics through a friend's recommendation. Could you
> tell me a bit more about what the product does? We're a 20-person
> marketing agency looking for a way to track campaign performance across
> multiple clients in one place. Also, do you offer a free trial before we
> commit to anything?

**A representative generated reply** (shape and constraints an actual run
should satisfy — this project does not fabricate a transcript for output it
did not run live):

> Subject: Re: Quick question about Loomis Analytics
>
> Hi Jordan,
>
> Thanks for reaching out! Loomis Analytics is a dashboard tool built for
> teams that need to track performance metrics across multiple sources in
> one place — which sounds like a good fit for tracking campaigns across
> your different clients.
>
> I don't have trial-availability details on hand from this inbox, but I've
> flagged your question so our sales team can follow up directly with trial
> options and next steps for a 20-person agency setup.
>
> Best,
> The Loomis Team

Note what it does *not* do: it doesn't confirm a specific trial length,
invent a price, or claim a feature it can't verify — it explicitly defers
those to a human follow-up, which is exactly what the `must_not_invent` list
for this class of case is designed to catch if violated.

## Project structure

```
src/email_agent/
  config.py            # env-var loading, EvalThresholds
  models/              # Pydantic models: Email, EmailClassification,
                        #   GeneratedReply, EvaluationResult, GoldenCase
  llm/
    client.py           # the only module that imports the Anthropic SDK
    prompts.py           # every prompt template, kept in one place for tuning
    json_utils.py         # tolerant JSON extraction from model output
  classifier.py         # Email -> Claude -> EmailClassification
  reply_generator.py    # Email + classification -> Claude -> GeneratedReply
  evaluator.py           # golden case + reply -> Claude judge -> EvaluationResult
  pipeline.py            # orchestrates classify -> reply -> persist -> evaluate
  email_io.py            # parses sample-email .txt files and golden_cases.json
  database/
    connection.py         # sqlite3 connection + directory creation
    schema.py             # CREATE TABLE statements
    repository.py         # all parameterized SQL, aggregate report query
  cli.py                 # `run`, `eval`, `report`, `db-init` subcommands

data/
  golden/golden_cases.json     # 15 labeled evaluation cases
  sample_emails/*.txt          # one runnable sample per category

tests/                  # 44 tests, all against a fake Claude client
```

## Design decisions

- **SQLite over a client-server database.** Zero setup, one file, created
  automatically on first run — appropriate for a project meant to be cloned
  and run in under a minute.
- **Pydantic everywhere data crosses a boundary.** Every LLM response is
  validated into a typed model before the rest of the app touches it, so a
  malformed or partially-wrong model response fails loudly (a caught,
  specific exception) instead of silently propagating a bad category or an
  out-of-range score.
- **Golden sets over spot-checking.** A fixed, versioned set of cases means
  prompt changes can be evaluated against a stable baseline instead of
  "it looked fine in the three examples I tried."
- **LLM-as-judge over string-matching.** Reply quality (tone, relevance,
  hallucination) isn't checkable with exact-match assertions; a second model
  call grading against explicit criteria is the practical alternative, with
  its limitations documented above rather than glossed over.
- **Structured JSON output over free text.** Every Claude call is prompted
  to return a single JSON object matching a documented schema, parsed with a
  tolerant extractor (`json_utils.py`) that survives markdown fences, and
  validated with Pydantic — this is what makes the classifier, generator,
  and evaluator each independently testable with a one-line fake response.
- **Minimal dependencies.** `anthropic`, `pydantic`, `python-dotenv`, and
  `pytest` are the entire dependency list. No agent framework, no ORM, no
  vector store — none of the three pipeline stages need them.

## Known limitations

- The evaluation judge and the reply generator currently share the same
  model family, which risks shared blind spots (see "Limitations of
  LLM-based evaluation" above).
- 15 golden cases give broad but not exhaustive coverage; edge cases in
  languages other than English, multi-email threads, and attachments are
  out of scope.
- The CLI's plain-text email format (`From:` / `Subject:` header block plus
  body) is intentionally simple and does not parse real `.eml`/MIME files.
"# email-reply-agent" 
