import os
import re
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    bee_key = os.environ.get("SCRAPINGBEE_KEY")
    
    if not api_key or not bee_key:
        return f"⚠️ Configuration Missing: GEMINI_API_KEY={bool(api_key)}, SCRAPINGBEE_KEY={bool(bee_key)}"

    region = "longisland"
    # Target the primary classified index feed URL cleanly
    raw_target_url = f"https://{region}.craigslist.org/search/gms"
    
    # 💡 FIX: Safely URL-encode the target address to prevent ScrapingBee parameter separation failures
    encoded_target = urllib.parse.quote_plus(raw_target_url)
    
    # Define native cloud rules to pull links and thumbnail image tokens automatically
    extraction_configuration = {
        "listings": {
            "selector": "li.cl-search-result",
            "type": "list",
            "output": {
                "link": {"selector": "a.cl-app-anchor", "output": "href"},
                "img_id": {"selector": "div.cl-gallery img", "output": "data-id"}
            }
        }
    }
    encoded_rules = urllib.parse.quote_plus(json.dumps(extraction_configuration))
    
    # Compile parameters into a structured proxy call format
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={encoded_target}&extract_rules={encoded_rules}&render_js=false"
    
    output_report = f"📸 HIGH-THROUGHPUT VISUAL SCANNER ONLINE ({region} Moving/Estate Category)...\n\n"
    
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            parsed_data = response.json()
            listings = parsed_data.get("listings", [])
            
            if not listings:
                return output_report + "⚠️ Cloud verification block parsed successfully, but index grid was empty. Retrying shortly..."

            # Initialize Gemini Curator Evaluation Cluster
            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            # Sequentially process the top 4 visual entities extracted natively by the cloud proxy
            for item in listings[:4]:
                link = item.get("link")
                img_id = item.get("img_id")
                
                if not link or not img_id:
                    continue
                    
                url_slug = link.split('/')[-1].replace('.html', '').replace('-', ' ')
                title_guess = re.sub(r'^\d+\s*', '', url_slug).title()
                
                # Reconstruct image thumbnail URLs from extracted tokens
                img_url = f"https://images.craigslist.org/{img_id}_300x300.jpg"
                
                try:
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        prompt = f"Analyze the visual structure of this item listing: '{title_guess}'. Does it possess historical hallmarks, maker characteristics, or material compositions indicating it is worth >1000% of a casual yard sale value? Reply strictly as: ROI POTENTIAL: [High/Low] - REASON: [1 sentence]."
                        
                        ai_res = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[
                                types.Part.from_bytes(data=img_res.content, mime_type="image/jpeg"),
                                prompt
                            ],
                            config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.1)
                        )
                        
                        if "High" in ai_res.text:
                            output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title_guess}\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                        else:
                            output_report += f"📁 Scanned: {title_guess} -> Low ROI potential detected.\n"
                except Exception:
                    pass
        else:
            output_report += f"Craigslist Proxy Error: Status {response.status_code} - Text: {response.text[:200]}\n"
    except Exception as e:
        output_report += f"Pipeline Execution Interrupted: {e}\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
