import os
import re
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
    # 🗺️ Target Craigslist's hidden backend data query stream (bypasses HTML completely)
    raw_target_url = f"https://webapi.craigslist.org/webapi/v1/search/search?cl_category=gms&areaSubdomain={region}&lang=en"
    encoded_target = urllib.parse.quote_plus(raw_target_url)
    
    # Bundle proxy target via ScrapingBee
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={encoded_target}&render_js=false"
    
    output_report = f"📸 HIGH-THROUGHPUT VISUAL SCANNER ONLINE ({region} Moving/Estate API Stream)...\n\n"
    
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            parsed_json = response.json()
            
            # Drill into the structured API data mapping array
            data_items = parsed_json.get("data", {}).get("items", [])
            
            if not data_items:
                return output_report + "⚠️ Connection successful, but 0 active listings were returned by the local API feed right now."

            # Initialize Gemini Curator Evaluation Engine
            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            items_processed = 0
            # Scan the live listings array for objects that contain images
            for item in data_items:
                if items_processed >= 4: # Process top 4 targets to protect free rate limits
                    break
                    
                title = item.get("title", "Unknown Item")
                price = f"${item.get('price', '0')}"
                posting_id = item.get("id")
                
                # Extract the primary image cluster string array
                image_string = item.get("images", "")
                if not image_string:
                    continue
                    
                # Craigslist data layers provide image sequences as comma-separated ID tokens
                first_img_id = image_string.split(',')[0].replace('1:', '')
                img_url = f"https://images.craigslist.org/{first_img_id}_300x300.jpg"
                link = f"https://{region}.craigslist.org/gms/d/listings/{posting_id}.html"

                try:
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        prompt = f"Analyze the visual structure of this item listing: '{title}' being sold for {price}. Does it possess historical hallmarks, maker characteristics, or material compositions indicating it is worth >1000% of its current value? Reply strictly as: ROI POTENTIAL: [High/Low] - REASON: [1 sentence]."
                        
                        ai_res = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[
                                types.Part.from_bytes(data=img_res.content, mime_type="image/jpeg"),
                                prompt
                            ],
                            config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.1)
                        )
                        
                        # Only showcase items labeled with high flip potential to maintain a high-value feed
                        if "High" in ai_res.text:
                            output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title} ({price})\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                        else:
                            output_report += f"📁 Scanned: {title} ({price}) -> Low ROI potential detected.\n"
                        
                        items_processed += 1
                except Exception:
                    pass
        else:
            output_report += f"API Feed Refused: HTTP Status {response.status_code}\n"
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
