import os
import json
import re
import requests
import subprocess
import concurrent.futures
import feedparser
from typing import Optional, Set
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

# 1. Pfade & Gemini-Client Initialisierung
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, "../.env")
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
SEEN_JOBS_FILE = os.path.join(BASE_DIR, "seen_jobs.json")

load_dotenv(ENV_PATH)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. Pydantic-Schema für die LLM-Auswertung
class JobEvaluation(BaseModel):
    is_match: bool
    company: str
    position: str
    job_type: str                   # z.B. "IT-Werkstudent", "Standard-Minijob", etc.
    hourly_wage: Optional[float]    # z.B. 18.5 (oder None falls nicht genannt)
    hours_per_week: Optional[int]   # z.B. 15
    location: Optional[str]         # z.B. "Berlin-Mitte"
    reason: str                     # Begründung der Kriterienprüfung

# 3. Hilfsfunktionen: Normalisierung & Persistenter Seen-Cache
def normalize_text(text: str) -> str:
    """Normalisiert Strings (Kleinschreibung, Sonderzeichen entfernen) für Signaturvergleich"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9äöüß]", "", text)
    return text

def create_job_signature(company: str, position: str) -> str:
    """Erstellt einen eindeutigen Fingerabdruck aus Firma + Rolle gegen Portal-Duplikate"""
    c = normalize_text(company)
    p = normalize_text(position)
    return f"{c}::{p}"

def load_seen_cache() -> dict:
    """Lädt bereits geprüfte URLs und Signaturen aus seen_jobs.json"""
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"urls": [], "signatures": []}

def save_seen_cache(seen_data: dict):
    """Speichert den Seen-Cache dauerhaft ab"""
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_data, f, indent=2, ensure_ascii=False)

# 4. LLM-Bewertungsfunktion
def evaluate_job(raw_text: str) -> JobEvaluation:
    prompt = f"""
    Analysiere folgende Stellenanzeige für einen Berliner Informatik-Studenten.
    
    Such-Kriterien:
    - Mindestens 17 bis 18 Euro pro Stunde (oder keine Angabe, dann None)
    - 12 bis 18 Wochenstunden (Werkstudent)
    - Standort: Berlin oder Remote
    - Rollen: Softwareentwicklung, IT-Support/Admin, Data Science/Pipelines oder gut dotierte Nebenjobs
    
    Stellenanzeige:
    {raw_text}
    """
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": JobEvaluation
        }
    )
    return JobEvaluation.model_validate_json(response.text)

# 5. Tracker API & Benachrichtigung
def save_to_tracker(eval_data: JobEvaluation, job_url: str):
    payload = {
        "company": eval_data.company,
        "position": eval_data.position,
        "job_type": eval_data.job_type,
        "hourly_wage": eval_data.hourly_wage,
        "hours_per_week": eval_data.hours_per_week or 15,
        "location": eval_data.location,
        "job_url": job_url,
        "status": "Entwurf",
        "notes": eval_data.reason
    }
    try:
        requests.post("http://localhost:8000/api/applications", json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Konnte Stelle nicht im Tracker speichern: {e}")

def notify(title: str, message: str):
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except Exception:
        pass

# 6. Multi-Worker Feed-Fetching
def fetch_feed_items(feed_source: dict) -> list[dict]:
    """Worker-Funktion: Liest einen einzelnen Feed parallel ein"""
    print(f"📡 Worker scannt: {feed_source.get('name')}...")
    items = []
    try:
        feed = feedparser.parse(feed_source.get("feed_url"))
        for entry in feed.entries[:15]:
            items.append({
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "description": getattr(entry, "summary", "") or getattr(entry, "description", ""),
                "source": feed_source.get("name")
            })
    except Exception as e:
        print(f"⚠️ Fehler beim Feed {feed_source.get('name')}: {e}")
    return items

def run_multi_worker_scout() -> list[dict]:
    # Falls noch keine feeds.json existiert, feed_finder anwerfen
    if not os.path.exists(FEEDS_PATH):
        print("🔍 Keine feeds.json gefunden. Starte feed_finder...")
        import feed_finder
        feed_finder.discover_feeds()

    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        sources = data.get("sources", [])

    all_jobs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(fetch_feed_items, sources)
        for job_list in results:
            all_jobs.extend(job_list)

    print(f"📦 Insgesamt {len(all_jobs)} Inserate aus allen Feeds gesammelt.")
    return all_jobs

# 7. Orchestrator Main
def main():
    print("🚀 Starte Job-Scout mit persistentem Deduplikations-Cache...")
    
    seen_cache = load_seen_cache()
    seen_urls: Set[str] = set(seen_cache.get("urls", []))
    seen_signatures: Set[str] = set(seen_cache.get("signatures", []))

    # Bekannte Stellen auch aus der DB synchronisieren
    try:
        r = requests.get("http://localhost:8000/api/applications", timeout=5)
        if r.status_code == 200:
            for app in r.json():
                if app.get("job_url"):
                    seen_urls.add(app["job_url"])
                if app.get("company") and app.get("position"):
                    seen_signatures.add(create_job_signature(app["company"], app["position"]))
    except Exception:
        print("ℹ️ Lokaler Job-Tracker nicht aktiv oder leer. Verwende lokalen Cache.")

    jobs = run_multi_worker_scout()
    new_matches = 0

    for job in jobs:
        url = job.get("link", "").strip()
        title = job.get("title", "").strip()

        # Stufe 1 Filter: URL bereits in der Vergangenheit gesehen (egal ob Match oder Reject)?
        if url and url in seen_urls:
            continue

        # Stufe 1b Filter: Grober Vorab-Check auf den Titel
        norm_title = normalize_text(title)
        if any(norm_title and norm_title in sig for sig in seen_signatures):
            print(f"⏭️ Überspringe Portal-Duplikat: {title[:50]}...")
            if url:
                seen_urls.add(url)
            continue

        print(f"\n🧠 Prüfe neue Stelle mit Gemini: {title[:55]}...")
        raw_text = f"Titel: {title}\nQuelle: {job.get('source')}\nBeschreibung: {job.get('description')}"

        try:
            evaluation = evaluate_job(raw_text)
            
            # Signatur aus vom Modell extrahierter Firma + Rolle
            sig = create_job_signature(evaluation.company, evaluation.position)

            # Stufe 2 Filter: Wurde diese Stelle bereits über ein anderes Portal gespeichert?
            if sig in seen_signatures:
                print(f"⏭️ Portal-Duplikat erkannt für {evaluation.company} - {evaluation.position}.")
                if url:
                    seen_urls.add(url)
                continue

            # Zu Caches hinzufügen
            if url:
                seen_urls.add(url)
            if sig:
                seen_signatures.add(sig)

            # Entscheidung verarbeiten
            if evaluation.is_match:
                print(f"✅ MATCH! {evaluation.company} - {evaluation.position} ({evaluation.hourly_wage or '?'} €/h)")
                save_to_tracker(evaluation, job_url=url)
                notify(
                    title=f"🎯 Neuer Job: {evaluation.company}",
                    message=f"{evaluation.position} ({evaluation.hourly_wage or '?'} €/h)\n{evaluation.reason[:80]}..."
                )
                new_matches += 1
            else:
                print(f"❌ Kein Match: {evaluation.reason[:70]}...")

        except Exception as e:
            print(f"⚠️ Fehler bei Bewertung: {e}")

    # Cache dauerhaft speichern
    seen_cache["urls"] = list(seen_urls)
    seen_cache["signatures"] = list(seen_signatures)
    save_seen_cache(seen_cache)

    print(f"\n🏁 Scout-Durchlauf beendet: {new_matches} neue passende Stellen in den Tracker importiert.")

if __name__ == "__main__":
    main()
