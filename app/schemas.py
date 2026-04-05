from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, Literal

EVENT_CATEGORIES = ["religious", "conference", "festival", "diaspora", "education", "trade", "arts", "sports", "music"]
TIMEFRAME_OPTIONS = ["2_weeks", "1_month", "3_months", "custom"]

class SignIn(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class EventSearchRequest(BaseModel):
    timeframe: Literal["2_weeks", "1_month", "3_months", "custom"]
    custom_days: Optional[int] = None
    categories: Optional[list[str]] = None

    @field_validator("custom_days")
    @classmethod
    def validate_custom_days(cls, v, info):
        if info.data.get("timeframe") == "custom" and (v is None or v <= 0):
            raise ValueError("custom_days must be a positive integer when timeframe is custom")
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v):
        if v:
            invalid = [c for c in v if c not in EVENT_CATEGORIES]
            if invalid:
                raise ValueError(f"Invalid categories: {invalid}. Must be one of {EVENT_CATEGORIES}")
        return v

class EventResponse(BaseModel):
    id: str
    slug: Optional[str] = None
    name: str
    category: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    recurrence: Optional[str] = None
    locations: Optional[dict] = None
    demandImpact: Optional[dict] = None
    leadTimeDays: Optional[int] = None
    impactRadiusKm: Optional[float] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    hotelStrategy: Optional[dict] = None
    created_at: datetime

    @classmethod
    def from_orm_event(cls, event) -> "EventResponse":
        return cls(
            id=event.id,
            slug=event.slug,
            name=event.name,
            category=event.category,
            startDate=event.start_date,
            endDate=event.end_date,
            recurrence=event.recurrence,
            locations={"country": event.country or "Ethiopia", "venues": event.venues or []},
            demandImpact={"level": event.demand_level, "travelerType": event.traveler_type or []},
            leadTimeDays=event.lead_time_days,
            impactRadiusKm=event.impact_radius_km,
            timezone=event.timezone,
            description=event.description,
            hotelStrategy={"campaignType": event.campaign_type or [], "suggestedAudience": event.suggested_audience or []},
            created_at=event.created_at,
        )

    class Config:
        from_attributes = True

class EventSearchResponse(BaseModel):
    events: list[EventResponse]
    meta: dict

class CampaignAdResponse(BaseModel):
    id: str
    campaignId: str
    purpose: str
    channel: str
    title: Optional[str]
    message: str
    status: str
    budget: Optional[float]
    leadsCaptured: Optional[int]
    sentCount: Optional[int]
    targetAudience: Optional[dict]
    aiRationale: Optional[str]
    imagePrompt: Optional[str]
    imageUrl: Optional[str]

    class Config:
        from_attributes = True

class CampaignResponse(BaseModel):
    id: str
    name: str
    goal: str
    purpose: str
    startDate: str
    endDate: str
    status: str
    eventId: Optional[str]
    target: Optional[dict]
    ads: list[CampaignAdResponse]
    created_at: datetime

    @classmethod
    def from_orm(cls, campaign) -> "CampaignResponse":
        return cls(
            id=campaign.id,
            name=campaign.name,
            goal=campaign.goal,
            purpose=campaign.purpose,
            startDate=campaign.start_date,
            endDate=campaign.end_date,
            status=campaign.status,
            eventId=campaign.event_id,
            target=campaign.target,
            ads=[
                CampaignAdResponse(
                    id=ad.id,
                    campaignId=ad.campaign_id,
                    purpose=ad.purpose,
                    channel=ad.channel,
                    title=ad.title,
                    message=ad.message,
                    status=ad.status,
                    budget=ad.budget,
                    leadsCaptured=ad.leads_captured,
                    sentCount=ad.sent_count,
                    targetAudience=ad.target_audience,
                    aiRationale=ad.ai_rationale,
                    imagePrompt=ad.image_prompt,
                    imageUrl=ad.image_url
                )
                for ad in campaign.ads
            ],
            created_at=campaign.created_at
        )

    class Config:
        from_attributes = True

class SMSTemplateResponse(BaseModel):
    id: str
    segment: str
    message_body: str
    discount_code: Optional[str]
    landing_page_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class SMSCampaignResponse(BaseModel):
    id: str
    customer_id: Optional[str]
    campaign_id: Optional[str]
    segment: str
    message_body: str
    discount_code: Optional[str]
    landing_page_url: Optional[str]
    is_delivered: bool

    class Config:
        from_attributes = True
