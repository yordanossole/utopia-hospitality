from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean, Date, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import uuid
import enum

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(255), unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))

    start_date = Column(String(20))  # ISO date string
    end_date = Column(String(20))    # ISO date string
    recurrence = Column(String(20))  # yearly | variable

    # Location
    country = Column(String(100), default="Ethiopia")
    venues = Column(JSON)            # list of venue objects

    # Demand & Impact
    demand_level = Column(String(20))   # extreme | high | medium | low
    traveler_type = Column(JSON)        # list of traveler types
    lead_time_days = Column(Integer)
    impact_radius_km = Column(Float)
    timezone = Column(String(100), default="Africa/Addis_Ababa")

    # Hotel Strategy
    campaign_type = Column(JSON)        # list of campaign types
    suggested_audience = Column(JSON)   # list of audience strings

    # Meta
    source_url = Column(String)
    raw_api_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_seen_at = Column(DateTime, server_default=func.now())

    campaigns = relationship("AdCampaign", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(name='{self.name}', category='{self.category}')>"

class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    
    # AI Creative Content
    headline = Column(String(200))
    body_text = Column(Text)
    generated_image_url = Column(String)
    
    # Targeting & Logic
    target_audience = Column(JSON)
    ai_rationale = Column(Text)
    
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    event = relationship("Event", back_populates="campaigns")
    templates = relationship("AdTemplate", back_populates="campaign")

    def __repr__(self):
        return f"<AdCampaign(status='{self.status}', event_id='{self.event_id}')>"


class AdTemplate(Base):
    __tablename__ = "ad_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("ad_campaigns.id"), nullable=False)
    primary_text = Column(Text, nullable=False)
    headline = Column(String(255), nullable=False)
    image_prompt = Column(Text)
    image_url = Column(String, nullable=True)
    meta_form_id = Column(String(100))

    campaign = relationship("AdCampaign", back_populates="templates")


class UserSegment(enum.Enum):
    NEW_LEAD = "NEW_LEAD"
    EXISTING_CUSTOMER = "EXISTING"


class SMSCampaign(Base):
    __tablename__ = "sms_campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ad_campaign_id = Column(String, ForeignKey("ad_campaigns.id"), nullable=True)
    segment = Column(Enum(UserSegment), nullable=False)
    message_body = Column(String(160), nullable=False)
    discount_code = Column(String(50))
    landing_page_url = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    ad_campaign = relationship("AdCampaign")

    def __repr__(self):
        return f"<SMSCampaign(segment='{self.segment}')>"


class SMSSent(Base):
    __tablename__ = "sms_sent"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sms_campaign_id = Column(String, ForeignKey("sms_campaigns.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    message_body = Column(String(160), nullable=False)
    sent_at = Column(DateTime)
    is_delivered = Column(Boolean, default=False)

    campaign = relationship("SMSCampaign")

    def __repr__(self):
        return f"<SMSSent(customer='{self.customer_id}', delivered='{self.is_delivered}')>"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    phone_number = Column(String(20), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String(100), nullable=True)
    room_preference = Column(String(100), nullable=True)
    dietary_requirements = Column(Text, nullable=True)
    is_loyalty_member = Column(Boolean, default=False)
    origin_ad_campaign_id = Column(String, ForeignKey("ad_campaigns.id"), nullable=True)

    origin_campaign = relationship("AdCampaign")
    sms_history = relationship("SMSSent", backref="customer")

    def __repr__(self):
        return f"<Customer(name='{self.first_name}', phone='{self.phone_number}')>"


class PhotoMetadata(Base):
    __tablename__ = "photo_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_url = Column(String, nullable=False)
    file_name = Column(String(255))
    mime_type = Column(String(50))
    captured_at = Column(DateTime, nullable=False)
    location_tag = Column(String(100))

    def __repr__(self):
        return f"<Photo(location='{self.location_tag}', captured='{self.captured_at}')>"
