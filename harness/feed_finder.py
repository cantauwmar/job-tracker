import json
import os
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class FeedSource(BaseModel):
    name: str              # z.B. "Stellenwerk Berlin IT", "Arbeitsagentur Jobs"
    feed_url: str          # URL zum RSS/Atom-Feed oder REST-Endpunkt
    category: str          # "IT", "Startups", "Public"
    parser_type: str       # "rss" oder "html"

class FeedList(BaseModel):
    sources: list[FeedSource]

def discover_feeds() -> list[FeedSource]:
    prompt = """
    Ich brauche eine kuratierte Liste der besten, öffentlich zugänglichen RSS/Atom-Feeds oder offenen Endpunkte 
    für Werkstudenten- und Studentenjobs in Berlin (Schwerpunkte: Informatik/Softwareentwicklung, IT-Support, Data).
    Finde bzw. strukturiere funktionierende Feeds von Plattformen wie Stellenwerk Berlin, Hochschul-Jobbörsen, 
    bund.de/arbeitsagentur oder Berliner Startup-Netzwerken.
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": FeedList
        }
    )
    result = FeedList.model_validate_json(response.text)
    
    # In feeds.json speichern
    with open("feeds.json", "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
        
    return result.sources