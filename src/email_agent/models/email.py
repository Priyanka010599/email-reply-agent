from pydantic import BaseModel, Field, field_validator


class Email(BaseModel):
    """An inbound email to be classified and replied to."""

    sender: str
    subject: str
    body: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("email body must not be blank")
        return value
