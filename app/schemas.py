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
    query: str
    location: Optional[str] = None

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
