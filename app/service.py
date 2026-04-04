from serpapi import GoogleSearch
from groq import Groq
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as parse_date
import json
import os
from .models import Event, AdCampaign, AdTemplate, SMSCampaign, SMSSent, Customer, UserSegment

HOTEL_LOCATION = "New york city, USA"

groq_client = None

def get_groq_client():
    global groq_client
    if groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        groq_client = Groq(api_key=api_key)
    return groq_client

def _parse_groq_json(content: str):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)

def search_events_from_web(days: int) -> dict:
    today = datetime.now()
    end_date = today + timedelta(days=days)
    query = f"events in {HOTEL_LOCATION} from {today.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    search = GoogleSearch({
        "engine": "google_events",
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY")
    })
    return search.get_dict()

def structure_with_ai(raw_results: dict) -> list[dict]:
    raw_events = raw_results.get("events_results", [])[:10]
    events_data = [
        {
            "title": e.get("title"),
            "description": e.get("description", "")[:300],
            "date": e.get("date"),
            "address": e.get("address"),
            "link": e.get("link"),
        }
        for e in raw_events
    ]
    prompt = f"""Extract and structure event information from the following Google Events data.
Return a JSON array of events with this exact structure:
{{
  "title": "event title",
  "description": "event description",
  "category": "category (e.g., concert, sports, tech, conference)",
  "start_time": "ISO 8601 datetime or null",
  "end_time": "ISO 8601 datetime or null",
  "location_name": "location",
  "source_url": "original URL"
}}

Google Events Data:
{json.dumps(events_data, indent=2)}

Return ONLY valid JSON array, no markdown or explanation."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=4000
    )
    return _parse_groq_json(response.choices[0].message.content)

def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return parse_date(value).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

def save_events_to_db(events: list[dict], raw_api_data: dict, db: Session) -> list[Event]:
    saved_events = []
    for event_data in events:
        existing = db.query(Event).filter(
            Event.title == event_data.get("title"),
            Event.location_name == event_data.get("location_name"),
            Event.start_time == event_data.get("start_time")
        ).first()

        if existing:
            existing.description = event_data.get("description")
            existing.category = event_data.get("category")
            existing.end_time = _parse_dt(event_data.get("end_time"))
            existing.source_url = event_data.get("source_url")
            existing.raw_api_data = raw_api_data
            existing.ai_structured_data = event_data
            existing.last_seen_at = datetime.utcnow()
            saved_events.append(existing)
        else:
            new_event = Event(
                title=event_data.get("title"),
                description=event_data.get("description"),
                category=event_data.get("category"),
                start_time=_parse_dt(event_data.get("start_time")),
                end_time=_parse_dt(event_data.get("end_time")),
                location_name=event_data.get("location_name"),
                source_url=event_data.get("source_url"),
                raw_api_data=raw_api_data,
                ai_structured_data=event_data
            )
            db.add(new_event)
            saved_events.append(new_event)

    db.commit()
    for e in saved_events:
        db.refresh(e)
    return saved_events

def search_and_save_events(days: int, db: Session) -> list[Event]:
    raw_results = search_events_from_web(days)
    structured_events = structure_with_ai(raw_results)
    return save_events_to_db(structured_events, raw_results, db)

def generate_campaigns_for_event(event: Event, db: Session) -> list[AdCampaign]:
    prompt = f"""You are a hospitality marketing expert. Generate 3 distinct Meta ad campaign ideas for the following event.

Event:
- Title: {event.title}
- Description: {event.description or 'N/A'}
- Category: {event.category or 'N/A'}
- Location: {event.location_name or 'N/A'}
- Start: {event.start_time or 'N/A'}

Return a JSON array of exactly 3 campaigns with this structure:
{{
  "headline": "short punchy headline (max 200 chars)",
  "body_text": "ad body copy that creates urgency",
  "target_audience": {{"age_range": "...", "interests": [...], "location": "..."}},
  "ai_rationale": "why this campaign angle works"
}}

Return ONLY valid JSON array, no markdown or explanation."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000
    )
    campaigns_data = _parse_groq_json(response.choices[0].message.content)

    campaigns = [
        AdCampaign(
            event_id=event.id,
            headline=c.get("headline"),
            body_text=c.get("body_text"),
            target_audience=c.get("target_audience"),
            ai_rationale=c.get("ai_rationale"),
            status="draft"
        )
        for c in campaigns_data
    ]
    db.add_all(campaigns)
    db.commit()
    for c in campaigns:
        db.refresh(c)
    return campaigns

def generate_ad_template(campaign: AdCampaign, db: Session) -> AdTemplate:
    event = campaign.event
    prompt = f"""You are a Meta Ads creative specialist for a hospitality brand. Generate one high-converting ad template for the following campaign.

Event:
- Title: {event.title}
- Description: {event.description or 'N/A'}
- Location: {event.location_name or 'N/A'}
- Start: {event.start_time or 'N/A'}

Campaign:
- Headline: {campaign.headline}
- Body: {campaign.body_text}
- Target Audience: {json.dumps(campaign.target_audience)}

Return a single JSON object with this exact structure:
{{
  "primary_text": "the hook text shown above the image (2-3 sentences, creates desire)",
  "headline": "bold offer line shown next to the CTA button (max 255 chars)",
  "image_prompt": "detailed prompt for an AI image generator describing the ideal ad visual",
  "meta_form_id": null
}}

Return ONLY valid JSON, no markdown or explanation."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1000
    )
    data = _parse_groq_json(response.choices[0].message.content)

    template = AdTemplate(
        campaign_id=campaign.id,
        primary_text=data["primary_text"],
        headline=data["headline"],
        image_prompt=data.get("image_prompt"),
        image_url=data.get("image_url"),
        meta_form_id=data.get("meta_form_id")
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def generate_sms_template_existing(db: Session) -> SMSCampaign:
    prompt = """You are a hospitality CRM specialist. Write a base SMS template for returning/existing customers.
Be warm, personal, and include a compelling loyalty offer.
Use {first_name} as a placeholder. Keep it under 130 characters.

Return a single JSON object:
{
  "message_body": "the SMS template with {first_name} placeholder",
  "discount_code": "e.g. LOYALTY20",
  "landing_page_url": "https://example.com/returning-offer"
}

Return ONLY valid JSON, no markdown or explanation."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    data = _parse_groq_json(response.choices[0].message.content)

    template = SMSCampaign(
        segment=UserSegment.EXISTING_CUSTOMER,
        message_body=data["message_body"][:160],
        discount_code=data.get("discount_code"),
        landing_page_url=data.get("landing_page_url")
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def generate_sms_template_lead(db: Session) -> SMSCampaign:
    prompt = """You are a hospitality sales specialist. Write a base SMS template for new leads captured from Meta Ads.
Create urgency and drive them to book. Use {first_name} as a placeholder. Keep it under 130 characters.

Return a single JSON object:
{
  "message_body": "the SMS template with {first_name} placeholder",
  "discount_code": "e.g. WELCOME15",
  "landing_page_url": "https://example.com/book-now"
}

Return ONLY valid JSON, no markdown or explanation."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300
    )
    data = _parse_groq_json(response.choices[0].message.content)

    template = SMSCampaign(
        segment=UserSegment.NEW_LEAD,
        message_body=data["message_body"][:160],
        discount_code=data.get("discount_code"),
        landing_page_url=data.get("landing_page_url")
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def bulk_send_sms(template: SMSCampaign, db: Session) -> dict:
    segment_filter = (
        Customer.origin_ad_campaign_id.isnot(None)
        if template.segment == UserSegment.NEW_LEAD
        else Customer.origin_ad_campaign_id.is_(None)
    )
    customers = db.query(Customer).filter(segment_filter).all()

    sent, skipped = [], []
    for customer in customers:
        try:
            personalized = template.message_body.replace("{first_name}", customer.first_name)
            db.add(SMSSent(
                sms_campaign_id=template.id,
                customer_id=customer.id,
                message_body=personalized[:160],
                sent_at=datetime.utcnow()
            ))
            sent.append(customer.id)
        except Exception as e:
            skipped.append({"customer_id": customer.id, "reason": str(e)})

    db.commit()
    return {"sent": len(sent), "skipped": skipped}
