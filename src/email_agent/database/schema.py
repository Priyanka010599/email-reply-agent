"""SQLite schema definition and initialization."""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    generated_subject TEXT NOT NULL,
    generated_body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    golden_case_id TEXT,
    professionalism_score INTEGER NOT NULL,
    tone_match_score INTEGER NOT NULL,
    relevance_score INTEGER NOT NULL,
    hallucination_detected INTEGER NOT NULL,
    overall_score REAL NOT NULL,
    passed INTEGER NOT NULL,
    reasoning TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES agent_runs (id)
);

CREATE TABLE IF NOT EXISTS golden_cases (
    id TEXT PRIMARY KEY,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    expected_category TEXT NOT NULL,
    expected_tone TEXT NOT NULL,
    must_address TEXT NOT NULL,
    must_not_invent TEXT NOT NULL,
    quality_notes TEXT NOT NULL
);
"""


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.commit()
