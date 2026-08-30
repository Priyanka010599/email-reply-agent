from typing import Literal

from pydantic import BaseModel, Field

EmailCategory = Literal["sales_inquiry", "support_request", "other"]


class EmailClassification(BaseModel):
    """The result of classifying an inbound email."""

    category: EmailCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
