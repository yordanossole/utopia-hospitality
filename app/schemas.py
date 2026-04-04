from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SignIn(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class EventSearchRequest(BaseModel):
    days: int = 7

class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    category: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    location_name: Optional[str]
    source_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

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
