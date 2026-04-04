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
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location_name = Column(String(255))
    
    # AI Metadata
    source_url = Column(String)
    raw_api_data = Column(JSON)
    
    # Tracking
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    last_seen_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    campaigns = relationship("AdCampaign", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(title='{self.title}', category='{self.category}')>"

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
    image_url = Column(String, nullable=False)
    meta_form_id = Column(String(100))

    campaign = relationship("AdCampaign", back_populates="templates")


class UserSegment(enum.Enum):
    NEW_LEAD = "NEW_LEAD"
    EXISTING_CUSTOMER = "EXISTING"


class SMSCampaign(Base):
    __tablename__ = "sms_campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ad_campaign_id = Column(String, ForeignKey("ad_campaigns.id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    segment = Column(Enum(UserSegment), nullable=False)
    message_body = Column(String(160), nullable=False)
    discount_code = Column(String(50))
    landing_page_url = Column(String)
    sent_at = Column(DateTime)
    is_delivered = Column(Boolean, default=False)

    ad_campaign = relationship("AdCampaign")

    def __repr__(self):
        return f"<SMSCampaign(segment='{self.segment}', code='{self.discount_code}')>"


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
    sms_history = relationship("SMSCampaign", backref="customer")

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
