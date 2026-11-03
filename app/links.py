import secrets
import uuid
from collections import OrderedDict
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_dependency
from app.models import AuditEvent, Campaign, Destination, Link
from app.schemas import (
    UTM_FIELDS,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    DestinationCreate,
    DestinationOut,
    LinkCreate,
    LinkOut,
    LinkUpdate,
)
from app.security import require_admin

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)], tags=["Management"])


class LinkCache:
    def __init__(self):
        self.data = OrderedDict()
        self.lock = Lock()

    def get(self, slug):
        with self.lock:
            entry = self.data.get(slug)
            if entry and entry[0] > monotonic():
                self.data.move_to_end(slug)
                return entry[1]
            self.data.pop(slug, None)
        return None

    def put(self, slug, value):
        with self.lock:
            self.data[slug] = (monotonic() + get_settings().link_cache_ttl_seconds, value)
            self.data.move_to_end(slug)
            while len(self.data) > get_settings().link_cache_max_size:
                self.data.popitem(last=False)

    def invalidate(self, slug):
        with self.lock:
            self.data.pop(slug, None)


link_cache = LinkCache()


def resolve_link(session: Session, slug: str):
    cached = link_cache.get(slug)
    if cached:
        return cached
    row = session.execute(
        select(Link, Destination.url)
        .join(
            Destination,
            Destination.id == Link.active_destination_id,
        )
        .where(Link.slug == slug)
    ).first()
    if row is None:
        return None
    link, url = row
    result = {
        key: getattr(link, key)
        for key in (
            "id",
            "campaign_id",
            "active_destination_id",
            "version",
            "status",
            "expires_at",
            "forward_utm",
            *UTM_FIELDS,
        )
    }
    result["url"] = url
    link_cache.put(slug, result)
    return result


def require_campaign(session, campaign_id):
    if campaign_id:
        campaign = session.get(Campaign, campaign_id)
        if campaign is None or campaign.archived:
            raise HTTPException(422, "Campaign does not exist or is archived")


def get_link(session, link_id, lock=False):
    statement = select(Link).where(Link.id == link_id)
    if lock:
        statement = statement.with_for_update()
    link = session.scalar(statement)
    if link is None:
        raise HTTPException(404, "Link not found")
    return link


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignCreate, session: Session = Depends(session_dependency)):
    campaign = Campaign(name=body.name)
    session.add(campaign)
    session.flush()
    session.add(AuditEvent(action="campaign.create", resource_id=campaign.id))
    session.commit()
    return campaign


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(session_dependency),
):
    return session.scalars(
        select(Campaign).order_by(Campaign.created_at, Campaign.id).offset(offset).limit(limit)
    ).all()


@router.patch("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: uuid.UUID, body: CampaignUpdate, session: Session = Depends(session_dependency)
):
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(422, f"{key} cannot be null")
        setattr(campaign, key, value)
    session.add(AuditEvent(action="campaign.update", resource_id=campaign.id))
    session.commit()
    return campaign


@router.post("/links", response_model=LinkOut, status_code=201)
def create_link(body: LinkCreate, session: Session = Depends(session_dependency)):
    require_campaign(session, body.campaign_id)
    link_id, destination_id = uuid.uuid4(), uuid.uuid4()
    data = body.model_dump(exclude={"destination_url", "slug"})
    link = Link(
        id=link_id,
        active_destination_id=destination_id,
        slug=body.slug or secrets.token_urlsafe(9),
        **data,
    )
    session.add(link)
    try:
        session.flush()
        session.add(
            Destination(id=destination_id, link_id=link_id, url=body.destination_url, version=1)
        )
        session.add(AuditEvent(action="link.create", resource_id=link_id))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Slug is already reserved") from None
    return link


@router.get("/links", response_model=list[LinkOut])
def list_links(
    campaign_id: uuid.UUID | None = None,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(session_dependency),
):
    query = select(Link)
    if campaign_id:
        query = query.where(Link.campaign_id == campaign_id)
    return session.scalars(
        query.order_by(Link.created_at, Link.id).offset(offset).limit(limit)
    ).all()


@router.get("/links/{link_id}", response_model=LinkOut)
def read_link(link_id: uuid.UUID, session: Session = Depends(session_dependency)):
    return get_link(session, link_id)


@router.patch("/links/{link_id}", response_model=LinkOut)
def update_link(
    link_id: uuid.UUID, body: LinkUpdate, session: Session = Depends(session_dependency)
):
    link = get_link(session, link_id, lock=True)
    if link.status == "deleted":
        raise HTTPException(410, "Deleted links cannot be restored")
    if link.version != body.expected_version:
        raise HTTPException(409, "Link version changed; reload before editing")
    data = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    for key in ("status", "forward_utm", "active_destination_id"):
        if key in data and data[key] is None:
            raise HTTPException(422, f"{key} cannot be null")
    if "campaign_id" in data:
        require_campaign(session, data["campaign_id"])
    if data.get("active_destination_id"):
        destination = session.get(Destination, data["active_destination_id"])
        if destination is None or destination.link_id != link.id:
            raise HTTPException(422, "Destination must belong to this link")
    for key, value in data.items():
        setattr(link, key, value)
    link.version += 1
    session.add(
        AuditEvent(action="link.update", resource_id=link.id, details={"fields": list(data)})
    )
    session.commit()
    link_cache.invalidate(link.slug)
    return link


@router.delete("/links/{link_id}", status_code=204)
def delete_link(link_id: uuid.UUID, session: Session = Depends(session_dependency)):
    link = get_link(session, link_id, lock=True)
    link.status = "deleted"
    link.version += 1
    session.add(AuditEvent(action="link.delete", resource_id=link.id))
    session.commit()
    link_cache.invalidate(link.slug)
    return Response(status_code=204)


@router.post("/links/{link_id}/destinations", response_model=DestinationOut, status_code=201)
def add_destination(
    link_id: uuid.UUID, body: DestinationCreate, session: Session = Depends(session_dependency)
):
    link = get_link(session, link_id, lock=True)
    if link.status == "deleted":
        raise HTTPException(410, "Link deleted")
    version = (
        session.scalar(select(func.max(Destination.version)).where(Destination.link_id == link_id))
        or 0
    )
    destination = Destination(link_id=link_id, version=version + 1, url=body.url)
    session.add(destination)
    session.flush()
    session.add(AuditEvent(action="destination.create", resource_id=destination.id))
    session.commit()
    return destination


@router.get("/links/{link_id}/destinations", response_model=list[DestinationOut])
def list_destinations(
    link_id: uuid.UUID,
    offset: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(session_dependency),
):
    get_link(session, link_id)
    return session.scalars(
        select(Destination)
        .where(Destination.link_id == link_id)
        .order_by(Destination.version)
        .offset(offset)
        .limit(limit)
    ).all()
