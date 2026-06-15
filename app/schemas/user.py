from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserUpsert(BaseModel):
    telegram_id: int
    username: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=64)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)


class UserRead(UserUpsert):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
