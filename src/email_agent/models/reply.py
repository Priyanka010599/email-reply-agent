from pydantic import BaseModel, Field


class GeneratedReply(BaseModel):
    """A generated reply to an inbound email."""

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
