import os
import re
import io
import json
import base64
import urllib.parse
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from PIL import Image
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # 🔐 Paste your SCRAMBLED base64 token string inside these quotes
    scrambled_bee_token = "54c8887115af4dd7b475a9f83dc571b02cf6d77956a"
    
    try:
        bee_key = base64.b64decode(scrambled_bee_token).decode("utf-8")
    except Exception:
        bee_key = ""

    if not api_key or "PASTE" in scrambled_bee_token or not bee_key:
        return f"⚠️ Setup incomplete. Make sure GEMINI_API_KEY is active in Vercel and your encoded ScrapingBee token is pasted into line 16 of GitHub!"

    region = "longisland"
    # Target the primary classified backend data query stream endpoint
    raw_target_url = f"https://webapi.craigslist.org/webapi/v1/search/search?cl_category=gms&areaSubdomain={region}&lang=en"
    encoded_target = urllib.parse.quote_plus(raw_target_url)
    
    # 💡 FIX: Changing parameter string '?key=' to '?api_key=' satisfies ScrapingBee's structural constraint
    api_url = f"https://app.scrapingbee.com/api/v1/?api_key={bee_key}&url={encoded_target}&render_js=false"
    
    output_report = f"📸 HIGH-THROUGHPUT VISUAL SCANNER ONLINE ({region} Moving/Estate Category Stream)...\n\n"
    
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            parsed_json = response.json()
            
            # Drill cleanly into the nested JSON objects returned by Craigslist's data pool
            data_items = parsed_json.get("data", {}).get("items", [])
            
            if not data_items:
                return output_report + "⚠️ Live data stream accessed successfully, but 0 active listings were returned by the server at this time."

            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            items_processed = 0
            for item in data_items:
                if items_processed >= 4: # Limit visual analysis to top 4 listings to manage rate usage
                    break
                    
                title = item.get("title", "Unknown Item")
                price = f"${item.get('price', '0')}"
                posting_id = item.get("id")
                
                # Craigslist data schema packages internal photo identifiers inside a string block
                image_string = item.get("images", "")
                if not image_string:
                    continue
                    
                # Extract the primary image hash token sequence
                first_img_id = image_string.split(',')[0].replace('1:', '')
                img_url = f"https://images.craigslist.org/{first_img_id}_300x300.jpg"
                link = f"https://{region}.craigslist.org/gms/d/listings/{posting_id}.html"

                try:
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        # Normalize image dimensions cleanly via Pillow middleware
                        img_obj = Image.open(io.BytesIO(img_res.content)).convert("RGB")
                        
                        prompt = f"Analyze the visual structure of this item listing: '{title}' being sold for {price}. Does it possess historical hallmarks, maker characteristics, or material compositions indicating it is worth >1000% of its current value? Reply strictly as: ROI POTENTIAL: [High/Low] - REASON: [1 sentence]."
                        
                        ai_res = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[img_obj, prompt],
                            config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.1)
                        )
                        
                        if "High" in ai_res.text:
                            output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title} ({price})\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                        else:
                            output_report += f"📁 Scanned: {title} ({price}) -> Low ROI potential detected.\n"
                        
                        items_processed += 1
                except Exception:
                    pass
        else:
            output_report += f"API Feed Refused: HTTP Status {response.status_code} - Text: {response.text[:200]}\n"
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
