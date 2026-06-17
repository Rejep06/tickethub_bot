from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.services.events import DEFAULT_EVENT_TYPE, DEFAULT_SPORT_TYPE


class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=120)
    event_type: str = Field(default=DEFAULT_EVENT_TYPE, min_length=1, max_length=50)
    sport_type: str | None = Field(default=DEFAULT_SPORT_TYPE, max_length=50)
    event_date: date
    event_time: time
    location: str = Field(min_length=1, max_length=255)


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    event_type: str | None = Field(default=None, min_length=1, max_length=50)
    sport_type: str | None = Field(default=None, max_length=50)
    event_date: date | None = None
    event_time: time | None = None
    location: str | None = Field(default=None, min_length=1, max_length=255)


class EventRead(EventBase):
    id: int
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
