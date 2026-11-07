"""Administrative URL configurations. Link URLs are immutable snapshots."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import session_dependency
from app.linkspace_config import (
    RESERVED,
    configuration_status,
    normalize_base,
    normalize_prefix,
    root_allowed,
    tracking_url,
)
from app.models import AuditEvent, Link, Linkspace
from app.security import require_admin

router = APIRouter(
    prefix="/api/v1/linkspaces", tags=["Management"], dependencies=[Depends(require_admin)]
)


class LinkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(max_length=300)
    path_prefix: str = Field("r", max_length=52)
    is_active: bool = True
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Name is required and must not contain control characters")
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def clean_base(cls, value):
        return normalize_base(value)

    @field_validator("path_prefix")
    @classmethod
    def clean_prefix(cls, value):
        return normalize_prefix(value)


class LinkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    base_url: str
    path_prefix: str
    is_active: bool
    is_default: bool
    id: uuid.UUID
    created_at: datetime
    link_count: int
    preview_url: str
    configuration_status: str


def fail(code: str, status=422):
    raise HTTPException(status, detail={"code": code})


def lock_settings(session):
    # All default changes and new-link selection share this transaction lock.
    # The partial unique index independently enforces at most one default.
    session.execute(text("SELECT pg_advisory_xact_lock(1729048101)"))


def validate_configuration(base_url, prefix):
    if not prefix and not root_allowed(base_url):
        fail("LINKSPACE_ROOT_UNSAFE")


def select_for_link(session, linkspace_id, slug):
    lock_settings(session)
    query = select(Linkspace)
    query = (
        query.where(Linkspace.id == linkspace_id)
        if linkspace_id
        else query.where(Linkspace.is_default.is_(True))
    )
    space = session.scalar(query)
    if space is None or not space.is_active:
        fail("LINKSPACE_UNAVAILABLE")
    validate_configuration(space.base_url, space.path_prefix)
    if not space.path_prefix and (slug.lower() in RESERVED or slug.startswith("_")):
        fail("LINKSPACE_RESERVED_SLUG")
    return space


def output(space, count):
    return {
        **{key: getattr(space, key) for key in LinkspaceCreate.model_fields},
        "id": space.id,
        "created_at": space.created_at,
        "link_count": count,
        "preview_url": tracking_url(space.base_url, space.path_prefix, "slug"),
        "configuration_status": (
            "routing_blocked"
            if not space.path_prefix and not root_allowed(space.base_url)
            else configuration_status(space.base_url)
        ),
    }


def count_links(session, space_id):
    # Deleted links still reserve their configuration and must retain their association.
    return session.scalar(
        select(func.count()).select_from(Link).where(Link.linkspace_id == space_id)
    )


def save(session, space):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        fail("LINKSPACE_DUPLICATE", 409)
    return output(space, count_links(session, space.id))


@router.get("", response_model=list[LinkspaceOut])
def list_linkspaces(
    response: Response,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=500),
    q: str = Query("", max_length=100),
    active_only: bool = False,
    include_total: bool = False,
    session: Session = Depends(session_dependency),
):
    query = select(Linkspace)
    if q:
        query = query.where(Linkspace.name.icontains(q, autoescape=True))
    if active_only:
        query = query.where(Linkspace.is_active.is_(True))
    if include_total:
        response.headers["X-Total-Count"] = str(
            session.scalar(select(func.count()).select_from(query.subquery()))
        )
    counts = (
        select(func.count())
        .select_from(Link)
        .where(Link.linkspace_id == Linkspace.id)
        .correlate(Linkspace)
        .scalar_subquery()
    )
    rows = session.execute(
        query.add_columns(counts)
        .order_by(Linkspace.is_default.desc(), Linkspace.created_at.desc(), Linkspace.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [output(space, count) for space, count in rows]


def apply_default(session, space, body):
    if body.is_default and not body.is_active:
        fail("LINKSPACE_DEFAULT_ACTIVE")
    if space.is_default and not body.is_default:
        fail("LINKSPACE_SELECT_DEFAULT", 409)
    if body.is_default:
        session.execute(
            update(Linkspace)
            .where(Linkspace.id != space.id, Linkspace.is_default.is_(True))
            .values(is_default=False)
        )


@router.post("", response_model=LinkspaceOut, status_code=201)
def create_linkspace(body: LinkspaceCreate, session: Session = Depends(session_dependency)):
    lock_settings(session)
    validate_configuration(body.base_url, body.path_prefix)
    space = Linkspace(id=uuid.uuid4(), **body.model_dump())
    apply_default(session, space, body)
    session.add(space)
    session.add(AuditEvent(action="linkspace.create", resource_id=space.id))
    return save(session, space)


@router.put("/{space_id}", response_model=LinkspaceOut)
def update_linkspace(
    space_id: uuid.UUID, body: LinkspaceCreate, session: Session = Depends(session_dependency)
):
    lock_settings(session)
    space = session.get(Linkspace, space_id)
    if space is None:
        fail("NOT_FOUND", 404)
    validate_configuration(body.base_url, body.path_prefix)
    apply_default(session, space, body)
    for key, value in body.model_dump().items():
        setattr(space, key, value)
    session.add(AuditEvent(action="linkspace.update", resource_id=space.id))
    return save(session, space)


@router.delete("/{space_id}", status_code=204)
def delete_linkspace(space_id: uuid.UUID, session: Session = Depends(session_dependency)):
    lock_settings(session)
    space = session.get(Linkspace, space_id)
    if space is None:
        fail("NOT_FOUND", 404)
    if space.is_default:
        fail("LINKSPACE_SELECT_DEFAULT", 409)
    if count_links(session, space_id):
        fail("LINKSPACE_IN_USE", 409)
    session.delete(space)
    session.add(AuditEvent(action="linkspace.delete", resource_id=space_id))
    session.commit()
    return Response(status_code=204)
