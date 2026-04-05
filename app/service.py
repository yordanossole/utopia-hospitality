from google import genai
from google.genai import types
from groq import Groq
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import os
import logging
import uuid
from .models import Event, Campaign, CampaignAd, SMSCampaign, SMSSent, Customer, UserSegment
from .schemas import EventSearchRequest

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ["religious", "conference", "festival", "diaspora", "education", "trade", "arts", "sports", "music"]

TIMEFRAME_DAYS = {
    "2_weeks": 14,
    "1_month": 30,
    "3_months": 90,
}

# ─── Lazy clients ────────────────────────────────────────────────────────────

_gemini_client = None
_groq_client = None

def get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        _groq_client = Groq(api_key=api_key)
    return _groq_client

# ─── Timeframe resolver ───────────────────────────────────────────────────────

def resolve_timeframe(request: EventSearchRequest) -> tuple[str, str]:
    """Convert timeframe to start_date and end_date strings"""
    start = datetime.utcnow().date()
    days = request.custom_days if request.timeframe == "custom" else TIMEFRAME_DAYS[request.timeframe]
    end = start + timedelta(days=days)
    return str(start), str(end)

# ─── Gemini search agent ──────────────────────────────────────────────────────

# Minimum demand levels worth saving (filter out noise)
MIN_DEMAND_LEVELS = {"extreme", "high", "medium"}

def search_events_with_gemini(categories: list[str], start_date: str, end_date: str) -> str:
    """Use Gemini with Google Search grounding to find real events in Ethiopia"""

    categories_str = ", ".join(categories)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    prompt = f"""You are an expert event research agent for the hospitality industry in Ethiopia.
Today's date is {today}. Search the web and find real, confirmed events happening in Ethiopia between {start_date} and {end_date}.

Focus ONLY on high-impact events relevant to hotel demand in these categories: {categories_str}

IMPORTANT - Only include events that meet at least ONE of these criteria:
- Expected attendance over 5,000 people
- International delegates or diaspora travelers
- Government or UN-level summits
- Major religious holidays with nationwide observance
- Trade fairs, expos, or large cultural festivals

DO NOT include small academic workshops, minor local seminars, or niche professional conferences with under 500 attendees.

For each event you find, extract:
- Full event name
- Exact category (must be one of: {categories_str})
- Start and end dates (YYYY-MM-DD format)
- Whether it recurs yearly or is variable
- All venue details: name, city, approximate lat/lng, estimated capacity, primary or secondary importance
- Who attends: local, international, diaspora, or business travelers
- Demand impact level: extreme (500k+ attendance or major international), high (50k-500k or significant), medium (5k-50k), low (under 5k)
- Estimated lead time in days hotels should prepare in advance
- Impact radius in km around the venue
- Hotel campaign strategy: which of these fit (discount, package, event-based, corporate, long-stay)
- Suggested hotel target audience

Be thorough. Search for religious holidays, government summits, trade fairs, cultural festivals, music concerts, sports events, art exhibitions, university events, and diaspora gatherings.

Return ONLY a valid JSON array with this exact structure per event:
[
  {{
    "name": "event name",
    "slug": "url-friendly-slug",
    "category": "one of the valid categories",
    "startDate": "YYYY-MM-DD",
    "endDate": "YYYY-MM-DD",
    "recurrence": "yearly or variable",
    "locations": {{
      "country": "Ethiopia",
      "venues": [
        {{
          "name": "venue name",
          "city": "city name",
          "lat": 0.0,
          "lng": 0.0,
          "capacity": 0,
          "importance": "primary or secondary"
        }}
      ]
    }},
    "demandImpact": {{
      "level": "extreme or high or medium or low",
      "travelerType": ["local", "international", "diaspora", "business"]
    }},
    "leadTimeDays": 30,
    "impactRadiusKm": 20,
    "timezone": "Africa/Addis_Ababa",
    "description": "brief description",
    "hotelStrategy": {{
      "campaignType": ["event-based"],
      "suggestedAudience": ["tourists", "diaspora"]
    }},
    "sourceUrl": "url where you found this event"
  }}
]

Return ONLY the JSON array. No markdown, no explanation."""

    response = get_gemini_client().models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.1,
            max_output_tokens=8000,
        )
    )

    return response.text

# ─── Parse Gemini response ────────────────────────────────────────────────────

def parse_gemini_response(raw: str) -> list[dict]:
    """Safely parse Gemini JSON response"""
    content = raw.strip()
    
    logger.info(f"Parsing Gemini response ({len(content)} chars)")
    logger.info(f"First 200 chars: {content[:200]}")
    logger.info(f"Last 200 chars: {content[-200:]}")

    # Strip markdown code blocks if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    # Find JSON array boundaries
    start = content.find("[")
    end = content.rfind("]") + 1
    
    if start == -1 or end == 0:
        logger.error(f"No JSON array found. Full response: {content[:1000]}")
        return []

    try:
        return json.loads(content[start:end])
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.error(f"Raw content around error: {content[max(0, e.pos-100):e.pos+100]}")
        # Try to salvage partial results
        try:
            # Find last complete object before error
            last_complete = content[:e.pos].rfind('},')
            if last_complete > 0:
                partial = content[start:last_complete+1] + "]"  # Close array
                logger.info("Attempting to parse partial results")
                return json.loads(partial)
        except:
            pass
        return []

# ─── Save to DB ───────────────────────────────────────────────────────────────

def save_events_to_db(events: list[dict], db: Session) -> list[Event]:
    """Save events with deduplication by slug"""
    saved = []

    for data in events:
        slug = data.get("slug") or data["name"].lower().replace(" ", "-")

        existing = db.query(Event).filter(Event.slug == slug).first()

        if existing:
            existing.name = data.get("name")
            existing.description = data.get("description")
            existing.category = data.get("category")
            existing.start_date = data.get("startDate")
            existing.end_date = data.get("endDate")
            existing.recurrence = data.get("recurrence")
            existing.venues = data.get("locations", {}).get("venues", [])
            existing.demand_level = data.get("demandImpact", {}).get("level")
            existing.traveler_type = data.get("demandImpact", {}).get("travelerType", [])
            existing.lead_time_days = data.get("leadTimeDays")
            existing.impact_radius_km = data.get("impactRadiusKm")
            existing.timezone = data.get("timezone", "Africa/Addis_Ababa")
            existing.campaign_type = data.get("hotelStrategy", {}).get("campaignType", [])
            existing.suggested_audience = data.get("hotelStrategy", {}).get("suggestedAudience", [])
            existing.source_url = data.get("sourceUrl")
            existing.last_seen_at = datetime.utcnow()
            saved.append(existing)
        else:
            event = Event(
                id=str(uuid.uuid4()),
                slug=slug,
                name=data.get("name"),
                description=data.get("description"),
                category=data.get("category"),
                start_date=data.get("startDate"),
                end_date=data.get("endDate"),
                recurrence=data.get("recurrence"),
                country="Ethiopia",
                venues=data.get("locations", {}).get("venues", []),
                demand_level=data.get("demandImpact", {}).get("level"),
                traveler_type=data.get("demandImpact", {}).get("travelerType", []),
                lead_time_days=data.get("leadTimeDays"),
                impact_radius_km=data.get("impactRadiusKm"),
                timezone=data.get("timezone", "Africa/Addis_Ababa"),
                campaign_type=data.get("hotelStrategy", {}).get("campaignType", []),
                suggested_audience=data.get("hotelStrategy", {}).get("suggestedAudience", []),
                source_url=data.get("sourceUrl"),
            )
            db.add(event)
            saved.append(event)

    db.commit()
    # Refresh all to load DB-generated fields like created_at
    for e in saved:
        db.refresh(e)
    return saved

# ─── Main orchestrator ────────────────────────────────────────────────────────

def search_and_save_events(request: EventSearchRequest, db: Session) -> dict:
    """Main agent: resolve timeframe → search with Gemini → save → return"""

    start_date, end_date = resolve_timeframe(request)
    categories = request.categories or VALID_CATEGORIES

    logger.info(f"Agent searching {len(categories)} categories in Ethiopia from {start_date} to {end_date}")

    raw = search_events_with_gemini(categories, start_date, end_date)
    logger.info(f"Raw Gemini response length: {len(raw)} chars")
    logger.debug(f"First 500 chars: {raw[:500]}")
    
    events_data = parse_gemini_response(raw)

    logger.info(f"Gemini found {len(events_data)} events")

    # Filter out low demand events - not useful for hotel strategy
    before_filter = len(events_data)
    events_data = [
        e for e in events_data
        if e.get("demandImpact", {}).get("level") in MIN_DEMAND_LEVELS
    ]
    logger.info(f"Demand filter: {before_filter} → {len(events_data)} events (removed {before_filter - len(events_data)} low-demand)")

    saved = save_events_to_db(events_data, db)

    from .schemas import EventResponse
    serialized_events = [EventResponse.from_orm_event(e) for e in saved]

    return {
        "events": serialized_events,
        "meta": {
            "total": len(saved),
            "start_date": start_date,
            "end_date": end_date,
            "categories_searched": categories,
            "fetched_at": datetime.utcnow().isoformat() + "Z"
        }
    }

# ─── Campaign generator ───────────────────────────────────────────────────────

def generate_campaign_for_event(event: Event, db: Session) -> Campaign:
    """Generate a complete campaign with multi-channel ads for an event"""
    
    # Check if campaign already exists for this event
    existing = db.query(Campaign).filter(Campaign.event_id == event.id).first()
    if existing:
        logger.info(f"Event {event.id} already has campaign, returning existing")
        return existing

    # Generate Meta ad creative using AI
    prompt = f"""You are a hospitality marketing expert. Generate ONE Meta ad campaign for this event.

Event:
- Name: {event.name}
- Description: {event.description or 'N/A'}
- Category: {event.category or 'N/A'}
- Location: Ethiopia
- Start: {event.start_date or 'N/A'}
- Demand Level: {event.demand_level or 'N/A'}
- Traveler Type: {event.traveler_type or 'N/A'}
- Suggested Audience: {event.suggested_audience or 'N/A'}

Return a JSON object:
{{
  "campaign_name": "short campaign name",
  "meta_ad": {{
    "title": "ad headline (max 200 chars)",
    "message": "ad body copy that creates urgency",
    "target_audience": {{"age_range": "...", "interests": [...], "location": "..."}},
    "image_prompt": "detailed prompt for AI image generator"
  }}
}}

Return ONLY valid JSON, no markdown."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)

    # Create campaign
    campaign = Campaign(
        name=data.get("campaign_name", f"{event.name} Campaign"),
        goal="bookings",
        purpose="both",  # both activation and acquisition
        start_date=event.start_date,
        end_date=event.end_date,
        status="draft",
        event_id=event.id,
        target={"source": ["pms", "website", "meta"]}
    )
    db.add(campaign)
    db.flush()  # Get campaign.id

    # Create Meta ad (acquisition)
    meta_ad_data = data.get("meta_ad", {})
    meta_ad = CampaignAd(
        campaign_id=campaign.id,
        purpose="acquisition",
        channel="meta",
        title=meta_ad_data.get("title"),
        message=meta_ad_data.get("message"),
        status="draft",
        target_audience=meta_ad_data.get("target_audience"),
        image_prompt=meta_ad_data.get("image_prompt"),
        budget=1000.0  # default budget
    )
    db.add(meta_ad)

    # Auto-generate SMS ad (activation) from Meta ad
    sms_message = f"Hi {{{{name}}}}, {meta_ad_data.get('title', event.name)}. Book now!"
    sms_ad = CampaignAd(
        campaign_id=campaign.id,
        purpose="activation",
        channel="sms",
        message=sms_message[:160],
        status="draft"
    )
    db.add(sms_ad)

    # Auto-generate Email ad (activation) from Meta ad
    email_ad = CampaignAd(
        campaign_id=campaign.id,
        purpose="activation",
        channel="email",
        title=meta_ad_data.get("title"),
        message=f"Dear {{{{name}}}},\n\n{meta_ad_data.get('message')}\n\nBook your stay today!",
        status="draft"
    )
    db.add(email_ad)

    db.commit()
    db.refresh(campaign)
    
    logger.info(f"Generated campaign {campaign.id} with {len(campaign.ads)} ads for event {event.id}")
    return campaign


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
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)

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
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content)

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
        Customer.origin_campaign_id.isnot(None)
        if template.segment == UserSegment.NEW_LEAD
        else Customer.origin_campaign_id.is_(None)
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
