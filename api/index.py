import os
import csv
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    bee_key = os.environ.get("SCRAPINGBEE_KEY")
    
    # 💡 IF YOU CHOOSE STRATEGY 1: Paste your published Google Sheet CSV link here
    google_sheet_csv_url = "PASTE_YOUR_GOOGLE_CSV_URL_HERE"
    
    if not api_key:
        return "Missing GEMINI_API_KEY configuration on Vercel."

    items_to_analyze = []

    # === METHOD A: USE FREE SCRAPINGBEE PROXY IF KEY EXISTS ===
    if bee_key:
        target_url = "https://vermont.craigslist.org/search/sss?query=estate+old+antique&format=rss"
        api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={target_url}&render_js=false"
        try:
            response = requests.get(api_url, timeout=20)
            if response.status_code == 200:
                namespaces = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'default': 'http://purl.org/rss/1.0/'}
                root = ET.fromstring(response.content)
                for item in root.findall('.//default:item', namespaces)[:3]:
                    items_to_analyze.append({
                        "title": item.find('default:title', namespaces).text or "Untitled",
                        "desc": item.find('default:description', namespaces).text or "No Desc",
                        "link": item.find('default:link', namespaces).text or ""
                    })
        except Exception as e:
            print(f"ScrapingBee failed: {e}")

    # === METHOD B: FALLBACK TO THE GOOGLE SHEETS SHIELD ===
    if not items_to_analyze and "http" in google_sheet_csv_url:
        try:
            res = requests.get(google_sheet_csv_url, timeout=15)
            if res.status_code == 200:
                lines = res.text.splitlines()
                reader = csv.reader(lines)
                next(reader) # Skip header row
                for row in reader:
                    if len(row) >= 2:
                        items_to_analyze.append({
                            "title": row[0], # Column A: Title
                            "desc": row[1],  # Column B: Summary/Description
                            "link": row[2] if len(row) > 2 else "" # Column C: Link
                        })
                    if len(items_to_analyze) >= 3:
                        break
        except Exception as e:
            print(f"Google Sheet fallback failed: {e}")

    # === METHOD C: MOCK FALLBACK ONLY IF PLUGINS FAIL ===
    if not items_to_analyze:
        return "⚠️ Setup Pending: Please plug your Google Sheet CSV URL into line 13 of github code or add your free ScrapingBee Key to Vercel settings!"

    # === INITIALIZE GEMINI BRAIN ===
    output_report = "📡 DATA STREAM MATCH! Running Gemini Antiquarian Intelligence Engine:\n\n"
    client = genai.Client(api_key=api_key)
    sys_instruction = "You are an expert museum curator. Identify rare, historically significant artifacts misidentified by oblivious sellers."
    
    for item in items_to_analyze:
        prompt = f"Analyze this item:\nTitle: {item['title']}\nDescription: {item['desc']}\n\nProvide output EXACTLY as:\nSCORE: [1-10]\nREASON: [1-2 sentences]"
        try:
            ai_res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
            )
            output_report += f"🔍 ITEM: {item['title']}\n{ai_res.text}\n🔗 {item['link']}\n{'-'*30}\n"
        except Exception as e:
            output_report += f"🔍 ITEM: {item['title']}\nAI Processing Interrupted: {str(e)}\n\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
