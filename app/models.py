from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import uuid

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

    def __repr__(self):
        return f"<AdCampaign(status='{self.status}', event_id='{self.event_id}')>"
