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

class AdCampaignResponse(BaseModel):
    id: str
    event_id: str
    headline: Optional[str]
    body_text: Optional[str]
    generated_image_url: Optional[str]
    target_audience: Optional[dict]
    ai_rationale: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdTemplateResponse(BaseModel):
    id: str
    campaign_id: str
    primary_text: str
    headline: str
    image_prompt: Optional[str]
    image_url: Optional[str]
    meta_form_id: Optional[str]

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
    ad_campaign_id: Optional[str]
    segment: str
    message_body: str
    discount_code: Optional[str]
    landing_page_url: Optional[str]
    is_delivered: bool

    class Config:
        from_attributes = True
