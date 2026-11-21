"""Request/response shapes for the REST API."""

from pydantic import BaseModel, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        email = value.strip().lower()
        local, _, domain = email.partition("@")
        if not local or "." not in domain or domain.startswith(".") or " " in email:
            raise ValueError("Enter a valid email address")
        return email


class UserOut(BaseModel):
    id: int
    email: str


class ConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ConversationOut(BaseModel):
    id: int
    title: str
    updated_at: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message is empty")
        return value.strip()


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ChatOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
