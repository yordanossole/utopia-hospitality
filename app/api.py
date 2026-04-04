from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Event
from .schemas import SignIn, Token, EventSearchRequest, EventResponse, AdCampaignResponse
from .auth import verify_password, create_access_token
from .service import search_and_save_events, generate_campaigns_for_event

router = APIRouter()

@router.post("/signin", response_model=Token)
def sign_in(credentials: SignIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/events", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.created_at.desc()).all()


@router.post("/search-events", response_model=list[EventResponse])
def search_events(request: EventSearchRequest, db: Session = Depends(get_db)):
    """Search for events using AI and save to database"""
    try:
        events = search_and_save_events(request.query, request.location, db)
        return events
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching events: {str(e)}"
        )


@router.post("/events/{event_id}/campaigns", response_model=list[AdCampaignResponse])
def generate_campaigns(event_id: str, db: Session = Depends(get_db)):
    """Generate AI ad campaigns for a specific event"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    try:
        return generate_campaigns_for_event(event, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating campaigns: {str(e)}"
        )
