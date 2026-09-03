"""Ticket and ticket-transition schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreateRequest(BaseModel):
    subject: str = Field(max_length=200)
    description: str = Field(max_length=4000)
    category: str = Field(max_length=80)


class TicketTransitionRequest(BaseModel):
    to_status: str
    comment: str = Field(max_length=2000)


class TicketAssignRequest(BaseModel):
    assigned_to: uuid.UUID


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    subject: str
    description: str
    category: str
    status: str
    assigned_to: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TicketTransitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    from_status: str
    to_status: str
    comment: str
    transitioned_by: uuid.UUID
    created_at: datetime


class FeedbackCreateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    rating: int
    comment: str | None
