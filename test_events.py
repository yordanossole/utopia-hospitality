import os
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv()

def test_google_events():
    api_key = os.getenv("SERPAPI_KEY")
    print(f"Testing Google Events engine...")
    
    # Test Google Events engine
    params = {
        "engine": "google_events",
        "q": "events New York",  # Test with a city that definitely has events
        "api_key": api_key
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        print(f"Results keys: {list(results.keys())}")
        
        if 'error' in results:
            print(f"Error: {results['error']}")
        elif 'events_results' in results:
            print(f"Found {len(results['events_results'])} events")
            if results['events_results']:
                print(f"First event: {results['events_results'][0].get('title', 'No title')}")
        else:
            print("No events_results key found")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_google_events()