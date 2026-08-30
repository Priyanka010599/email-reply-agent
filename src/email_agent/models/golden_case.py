from pydantic import BaseModel

from email_agent.models.classification import EmailCategory
from email_agent.models.email import Email


class GoldenCase(BaseModel):
    """A single labeled example used by the evaluation harness."""

    id: str
    email: Email
    expected_category: EmailCategory
    expected_tone: str
    must_address: list[str]
    must_not_invent: list[str]
    quality_notes: str
