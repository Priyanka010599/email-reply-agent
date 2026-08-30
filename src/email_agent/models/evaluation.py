from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """The result of judging a generated reply against a golden case."""

    professionalism_score: int = Field(ge=1, le=5)
    tone_match_score: int = Field(ge=1, le=5)
    relevance_score: int = Field(ge=1, le=5)
    hallucination_detected: bool
    overall_score: float = Field(ge=0.0, le=5.0)
    passed: bool
    reasoning: str
