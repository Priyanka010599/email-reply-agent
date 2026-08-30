"""All prompt templates used by the agent, kept in one place for easy tuning.

Each function returns a complete prompt string. Every prompt asks Claude to
respond with a single JSON object and nothing else, so callers can parse the
response directly.
"""

from __future__ import annotations

from email_agent.models.email import Email

CLASSIFICATION_SYSTEM_PROMPT = "You are a precise email triage assistant. You only output valid JSON."

REPLY_SYSTEM_PROMPT = "You are a professional customer-facing support and sales representative. You only output valid JSON."

EVALUATION_SYSTEM_PROMPT = "You are a strict, impartial quality reviewer grading customer-service email replies. You only output valid JSON."


def build_classification_prompt(email: Email) -> str:
    return f"""ROLE
You are an email triage classifier for a software company's inbox.

TASK
Classify the email below into exactly one of these categories:
- "sales_inquiry": pricing questions, product questions from a prospective buyer,
  demo requests, purchasing questions, partnership or commercial interest.
- "support_request": bugs, account issues, troubleshooting, problems using the
  product, requests for help from an existing user.
- "other": newsletters, spam, irrelevant messages, unclear or general messages
  that do not fit the two categories above.

CONTEXT
Sender: {email.sender}
Subject: {email.subject}
Body:
{email.body}

CONSTRAINTS
- Classify using only the information provided above.
- Do not invent context about the sender or their relationship to the company.
- If the email is ambiguous, choose the closest category and reflect the
  uncertainty in the confidence score rather than in the category itself.

PROHIBITED
- Do not return a category other than the three listed above.
- Do not include any text outside the JSON object.

OUTPUT SCHEMA
Return exactly one JSON object with these fields:
{{
  "category": "sales_inquiry" | "support_request" | "other",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one or two concise sentences explaining the classification>"
}}
"""


def build_reply_prompt(email: Email, category: str) -> str:
    return f"""ROLE
You are a professional customer-facing representative replying on behalf of a
software company.

TASK
Write a reply to the email below. The email has been classified as: {category}.

CONTEXT
Sender: {email.sender}
Subject: {email.subject}
Body:
{email.body}

CONSTRAINTS
- Directly address what the sender actually asked or reported.
- Be concise and professional, and match the sender's tone (e.g. respond to
  frustration with empathy and calm, respond to a simple question concisely).
- If the email provides enough information to answer, answer it.
- If it asks for something you have no information about (pricing, specific
  features, timelines, account-specific details, etc.), clearly say that
  information is not available here and suggest a concrete next step (e.g.
  "our sales team will follow up with pricing details").
- Avoid generic filler openers like "Thank you for reaching out. I understand
  your concern." unless it is genuinely the most natural response.

PROHIBITED
- Never invent company-specific facts: no fabricated pricing, discounts,
  product capabilities, timelines, or guarantees.
- Never claim an action has been taken (e.g. "I've refunded your account",
  "I've escalated this to engineering") unless the email itself states that it
  already happened.
- Do not include any text outside the JSON object.

OUTPUT SCHEMA
Return exactly one JSON object with these fields:
{{
  "subject": "<reply subject line, typically 'Re: ...'>",
  "body": "<the full reply body as plain text, including a greeting and sign-off>"
}}
"""


def build_evaluation_prompt(
    *,
    email: Email,
    expected_category: str,
    expected_tone: str,
    must_address: list[str],
    must_not_invent: list[str],
    reply_subject: str,
    reply_body: str,
) -> str:
    must_address_text = "\n".join(f"- {item}" for item in must_address) or "- (none specified)"
    must_not_invent_text = "\n".join(f"- {item}" for item in must_not_invent) or "- (none specified)"

    return f"""ROLE
You are a strict, impartial quality reviewer grading a customer-service email
reply produced by an AI agent.

TASK
Score the generated reply below against the original email and the grading
criteria. Be skeptical: only give high scores when the reply clearly earns them.

CONTEXT
Original email:
  Sender: {email.sender}
  Subject: {email.subject}
  Body: {email.body}

Expected category: {expected_category}
Expected tone: {expected_tone}

The reply must address:
{must_address_text}

The reply must NOT invent or state as fact (if it does, this is a hallucination):
{must_not_invent_text}

Generated reply:
  Subject: {reply_subject}
  Body: {reply_body}

SCORING CRITERIA (each 1-5, where 5 is best)
- professionalism_score: grammar, politeness, business appropriateness, clarity, structure.
- tone_match_score: does the reply's tone match the expected tone for this situation?
- relevance_score: does the reply actually answer/address the items listed above?
- hallucination_detected: true if the reply states as fact anything from the
  "must not invent" list, or any other unsupported specific claim (fabricated
  pricing, features, timelines, or guarantees not present in the original email).
  Otherwise false.

CONSTRAINTS
- Judge only what is written in the reply; do not assume good intent.
- A reply that correctly says information is unavailable is NOT a hallucination.

PROHIBITED
- Do not include any text outside the JSON object.

OUTPUT SCHEMA
Return exactly one JSON object with these fields:
{{
  "professionalism_score": <integer 1-5>,
  "tone_match_score": <integer 1-5>,
  "relevance_score": <integer 1-5>,
  "hallucination_detected": <true or false>,
  "reasoning": "<two or three concise sentences explaining the scores>"
}}
"""
