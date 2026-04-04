from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Event, AdCampaign, Customer
from .schemas import SignIn, Token, EventSearchRequest, EventResponse, AdCampaignResponse, AdTemplateResponse, SMSCampaignResponse
from .auth import verify_password, create_access_token
from .service import search_and_save_events, generate_campaigns_for_event, generate_ad_template, generate_sms_for_existing_customer, generate_sms_for_lead
import csv
import io
from datetime import date

router = APIRouter()

@router.post("/signin", response_model=Token)
def sign_in(credentials: SignIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return {"access_token": create_access_token(data={"sub": user.email}), "token_type": "bearer"}

@router.get("/events", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.created_at.desc()).all()

@router.post("/search-events", response_model=list[EventResponse])
def search_events(request: EventSearchRequest, db: Session = Depends(get_db)):
    try:
        return search_and_save_events(request.days, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error searching events: {str(e)}")

@router.post("/events/{event_id}/campaigns", response_model=list[AdCampaignResponse])
def generate_campaigns(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    try:
        return generate_campaigns_for_event(event, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating campaigns: {str(e)}")

@router.post("/campaigns/{campaign_id}/templates", response_model=AdTemplateResponse)
def generate_template(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(AdCampaign).filter(AdCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    try:
        return generate_ad_template(campaign, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating template: {str(e)}")

@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()

@router.post("/customers/import")
def import_customers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are accepted")

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created, updated, skipped = 0, 0, []

    for row in reader:
        try:
            dob_raw = row.get("date_of_birth", "").strip()
            dob = date.fromisoformat(dob_raw) if dob_raw else None
            is_loyalty = row.get("is_loyalty_member", "False").strip().lower() in ("true", "1", "yes")
            campaign_id = row.get("origin_ad_campaign_id", "").strip() or None

            existing = db.query(Customer).filter(Customer.id == row["id"]).first()
            if existing:
                existing.first_name = row["first_name"]
                existing.last_name = row.get("last_name") or None
                existing.email = row.get("email") or None
                existing.phone_number = row["phone_number"]
                existing.date_of_birth = dob
                existing.nationality = row.get("nationality") or None
                existing.room_preference = row.get("room_preference") or None
                existing.dietary_requirements = row.get("dietary_requirements") or None
                existing.is_loyalty_member = is_loyalty
                existing.origin_ad_campaign_id = campaign_id
                updated += 1
            else:
                db.add(Customer(
                    id=row["id"],
                    first_name=row["first_name"],
                    last_name=row.get("last_name") or None,
                    email=row.get("email") or None,
                    phone_number=row["phone_number"],
                    date_of_birth=dob,
                    nationality=row.get("nationality") or None,
                    room_preference=row.get("room_preference") or None,
                    dietary_requirements=row.get("dietary_requirements") or None,
                    is_loyalty_member=is_loyalty,
                    origin_ad_campaign_id=campaign_id
                ))
                created += 1
        except Exception as e:
            skipped.append({"row": row.get("id", "unknown"), "reason": str(e)})

    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}

@router.post("/customers/{customer_id}/sms/existing", response_model=SMSCampaignResponse)
def sms_existing_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    try:
        return generate_sms_for_existing_customer(customer, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating SMS: {str(e)}")

@router.post("/customers/{customer_id}/sms/lead", response_model=SMSCampaignResponse)
def sms_lead_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    try:
        return generate_sms_for_lead(customer, db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating SMS: {str(e)}")
