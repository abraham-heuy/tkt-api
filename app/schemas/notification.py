"""Notification and push subscription schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID | None
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
