import os
import re
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    proxy_url = os.environ.get("PROXY_URL")
    
    if not api_key:
        return "Missing GEMINI_API_KEY configuration on Vercel."

    # Using standard HTML layout endpoint
    region = "vermont"
    search_query = "estate old antique"
    url = f"https://{region}.craigslist.org/search/sss?query={search_query.replace(' ', '+')}"
    
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    try:
        # Requesting standard HTML layouts using an updated Chrome desktop footprint
        response = requests.get(url, impersonate="chrome110", proxies=proxies, timeout=15)
        if response.status_code != 200:
            return f"HTML Sync Paused. Status code: {response.status_code}. Proxy Connected: {bool(proxy_url)}"
    except Exception as e:
        return f"Network sync failure: {str(e)}"

    # Parse basic listings from HTML using clean text regular expressions
    html_content = response.text
    titles = re.findall(r'class="posting-title"[^>]*>(.*?)<\/a>', html_content)
    links = re.findall(r'href="(https://[a-z]+\.craigslist\.org/[^"]+)" class="posting-title"', html_content)

    # Fallback to Mock Data to let you see your Gemini brain work if Craigslist is still blocking the IP
    if not titles:
        output_report = f"⚠️ Network block detected (403 or empty HTML parsing). Running Mock Pipeline to verify Gemini Brain...\n\n"
        items_to_analyze = [
            {"title": "Old heavy metal sword - $40", "desc": "Found this clearing out my grandpas old garage trunk. It has some rusty looking engravings near the handle and some weird Roman numerals (MDCCXCI maybe?). Very heavy, could use a good polish. Just want it gone. Cash only.", "link": "#"},
            {"title": "Ancient dusty book with leather cover - $25", "desc": "Selling an old leather bound book. Pages are yellowed and some are loose. Looks like it is written in old Latin or something. Dated 1724 on the first page. Found in a box from an estate sale.", "link": "#"}
        ]
    else:
        output_report = f"📡 SUCCESS! Pulled live HTML data from {region}. Processing findings...\n\n"
        items_to_analyze = []
        for i in range(min(3, len(titles))):
            items_to_analyze.append({
                "title": titles[i].strip(),
                "desc": "Live item listing detail parsed from HTML search indexing.",
                "link": links[i] if i < len(links) else ""
            })

    # Initialize the Gemini Curator client
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
            output_report += f"🔍 ITEM: {item['title']}\nAI Analysis Paused: {str(e)}\n\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
