from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=4,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        examples=["web-abc123"],
    )
    question: str = Field(..., min_length=1, max_length=500)
    version: str | None = Field(default=None, max_length=32)
