import os
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv()

def test_serpapi():
    api_key = os.getenv("SERPAPI_KEY")
    print(f"API Key: {api_key[:10]}...")
    
    # Simple test search
    params = {
        "engine": "google",
        "q": "test search",
        "api_key": api_key
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        print(f"Results keys: {list(results.keys())}")
        
        if 'error' in results:
            print(f"Error: {results['error']}")
        else:
            print("SerpAPI is working!")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_serpapi()