from serpapi import GoogleSearch
from groq import Groq
from sqlalchemy.orm import Session
from datetime import datetime
import json
import os
from .models import Event

# Initialize Groq client only when needed
groq_client = None

def get_groq_client():
    global groq_client
    if groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        groq_client = Groq(api_key=api_key)
    return groq_client

def search_events_from_web(query: str, location: str = None) -> dict:
    """Search for events using SerpAPI Google Events"""
    search_query = f"{query} events"
    if location:
        search_query += f" in {location}"
    
    params = {
        "engine": "google_events",
        "q": search_query,
        "api_key": os.getenv("SERPAPI_KEY")
    }
    
    search = GoogleSearch(params)
    results = search.get_dict()
    return results

def structure_with_ai(raw_results: dict) -> list[dict]:
    """Use Groq to extract and structure event data from search results"""
    
    # Extract events from SerpAPI response
    events_data = raw_results.get('events_results', [])
    
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
    
    content = response.choices[0].message.content.strip()
    
    # Remove markdown code blocks if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    
    return json.loads(content)

def save_events_to_db(events: list[dict], raw_api_data: dict, db: Session) -> list[Event]:
    """Save events to database with deduplication"""
    saved_events = []
    
    for event_data in events:
        # Check for existing event
        existing = db.query(Event).filter(
            Event.title == event_data.get("title"),
            Event.location_name == event_data.get("location_name"),
            Event.start_time == event_data.get("start_time")
        ).first()
        
        if existing:
            # Update existing event
            existing.description = event_data.get("description")
            existing.category = event_data.get("category")
            existing.end_time = event_data.get("end_time")
            existing.source_url = event_data.get("source_url")
            existing.raw_api_data = raw_api_data
            existing.last_seen_at = datetime.utcnow()
            saved_events.append(existing)
        else:
            # Create new event
            new_event = Event(
                title=event_data.get("title"),
                description=event_data.get("description"),
                category=event_data.get("category"),
                start_time=event_data.get("start_time"),
                end_time=event_data.get("end_time"),
                location_name=event_data.get("location_name"),
                source_url=event_data.get("source_url"),
                raw_api_data=raw_api_data
            )
            db.add(new_event)
            saved_events.append(new_event)
    
    db.commit()
    return saved_events

def search_and_save_events(query: str, location: str, db: Session) -> list[Event]:
    """Main service method: search, structure, and save events"""
    # Step 1: Search web with Tavily
    raw_results = search_events_from_web(query, location)
    
    # Step 2: Structure data with Groq
    structured_events = structure_with_ai(raw_results)
    
    # Step 3: Save to database with deduplication
    saved_events = save_events_to_db(structured_events, raw_results, db)
    
    return saved_events
