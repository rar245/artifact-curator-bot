# Operational Security Vault Matrix Loaded v2
import os
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Missing GEMINI_API_KEY configuration on Vercel."

    region = "newyork"
    search_query = "estate old antique"
    url = f"https://{region}.craigslist.org/search/sss?query={search_query.replace(' ', '+')}&format=rss"
    
    try:
        response = requests.get(url, impersonate="chrome", timeout=10)
        if response.status_code != 200:
            return f"Craigslist blocked request with status code: {response.status_code}"
    except Exception as e:
        return f"Network error: {str(e)}"

    namespaces = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'default': 'http://purl.org/rss/1.0/'}
    try:
        root = ET.fromstring(response.content)
        items = root.findall('.//default:item', namespaces)
    except Exception as e:
        return f"XML Parsing Error: {str(e)}"

    if not items:
        return "No new listings found in this feed update."

    output_report = f"Scraped {len(items)} items. Live Artifact Analysis:\n\n"
    
    client = genai.Client(api_key=api_key)
    sys_instruction = "You are an expert museum curator. Identify rare, historically significant artifacts misidentified by oblivious sellers."
    
    for item in items[:3]:
        title = item.find('default:title', namespaces).text if item.find('default:title', namespaces) is not None else "No Title"
        desc = item.find('default:description', namespaces).text if item.find('default:description', namespaces) is not None else "No Description"
        link = item.find('default:link', namespaces).text if item.find('default:link', namespaces) is not None else ""
        
        prompt = f"Analyze this item:\nTitle: {title}\nDescription: {desc}\n\nProvide output EXACTLY as:\nSCORE: [1-10]\nREASON: [1-2 sentences]"
        
        try:
            ai_res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
            )
            output_report += f"🔍 ITEM: {title}\n{ai_res.text}\n🔗 {link}\n{'-'*30}\n"
        except Exception as e:
            output_report += f"🔍 ITEM: {title}\nAI Processing Error: {str(e)}\n\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
