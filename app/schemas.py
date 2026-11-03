import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security import validate_destination

UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


class UTMFields(BaseModel):
    utm_source: str | None = Field(None, max_length=200)
    utm_medium: str | None = Field(None, max_length=200)
    utm_campaign: str | None = Field(None, max_length=200)
    utm_content: str | None = Field(None, max_length=200)
    utm_term: str | None = Field(None, max_length=200)


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=200)
    archived: bool | None = None


class CampaignOut(CampaignCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    archived: bool
    created_at: datetime


class DestinationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=4096)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return validate_destination(value)


class DestinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    url: str
    id: uuid.UUID
    link_id: uuid.UUID
    version: int
    created_at: datetime


class LinkCreate(UTMFields):
    model_config = ConfigDict(extra="forbid")
    destination_url: str = Field(max_length=4096)
    slug: str | None = None
    campaign_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    forward_utm: bool = False

    @field_validator("destination_url")
    @classmethod
    def valid_url(cls, value):
        return validate_destination(value)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value):
        if value is not None and not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", value):
            raise ValueError("Slug must be 3–80 ASCII letters, digits, underscores or hyphens")
        return value

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError("Expiry must include a timezone")
        return value


class LinkUpdate(UTMFields):
    model_config = ConfigDict(extra="forbid")
    campaign_id: uuid.UUID | None = None
    status: Literal["active", "disabled"] | None = None
    expires_at: datetime | None = None
    forward_utm: bool | None = None
    active_destination_id: uuid.UUID | None = None
    expected_version: int = Field(ge=1)

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value):
        return LinkCreate.aware_expiry(value)


class LinkOut(UTMFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    campaign_id: uuid.UUID | None
    status: str
    expires_at: datetime | None
    forward_utm: bool
    active_destination_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
