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

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    goal = Column(String(50), nullable=False)  # bookings | awareness | lead_generation
    purpose = Column(String(50), nullable=False)  # activation | acquisition | both
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=False)
    status = Column(String(50), default="draft")  # draft | active | paused | completed
    event_id = Column(String, ForeignKey("events.id"), nullable=True)
    target = Column(JSON)  # {segmentIds: [], source: []}
    created_at = Column(DateTime, server_default=func.now())

    event = relationship("Event", back_populates="campaigns")
    ads = relationship("CampaignAd", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(name='{self.name}', status='{self.status}')>"


class CampaignAd(Base):
    __tablename__ = "campaign_ads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    purpose = Column(String(50), nullable=False)  # activation | acquisition
    channel = Column(String(50), nullable=False)  # sms | email | meta | google
    title = Column(String(255))
    message = Column(Text, nullable=False)
    status = Column(String(50), default="draft")  # draft | running | paused
    budget = Column(Float)  # only for meta/google
    leads_captured = Column(Integer, default=0)  # acquisition metric
    sent_count = Column(Integer, default=0)  # activation metric
    
    # Meta ad specific fields
    target_audience = Column(JSON)
    ai_rationale = Column(Text)
    image_prompt = Column(Text)
    image_url = Column(String)
    
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="ads")

    def __repr__(self):
        return f"<CampaignAd(channel='{self.channel}', purpose='{self.purpose}')>"


class UserSegment(enum.Enum):
    NEW_LEAD = "NEW_LEAD"
    EXISTING_CUSTOMER = "EXISTING"


class SMSCampaign(Base):
    __tablename__ = "sms_campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    segment = Column(Enum(UserSegment), nullable=False)
    message_body = Column(String(160), nullable=False)
    discount_code = Column(String(50))
    landing_page_url = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign")

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
    origin_campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)

    origin_campaign = relationship("Campaign")
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
