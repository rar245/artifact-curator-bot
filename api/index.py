import os
import re
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    bee_key = os.environ.get("SCRAPINGBEE_KEY")
    
    if not api_key or not bee_key:
        return "⚠️ Configuration Missing: Check Vercel Keys."

    # 🗺️ Target the RAW garage/estate sale category grid directly (high volume)
    region = "longisland"
    target_url = f"https://{region}.craigslist.org/search/gms" 
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={target_url}&render_js=false"
    
    output_report = f"📸 HIGH-THROUGHPUT VISUAL SCANNER ONLINE ({region} Garage/Estate Category)...\n\n"
    
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            html = response.text
            
            # Extract image IDs and post URLs directly from the main index list map
            # This allows us to find images for dozens of items in 1 single proxy call
            post_links = re.findall(r'href="(https://[a-z]+\.craigslist\.org/[a-z]+/d/[^"]+\.html)"', html)
            img_ids = re.findall(r'data-id="([A-Za-z0-9_]+)"', html)
            
            unique_links = list(set(post_links))
            
            if not unique_links:
                return output_report + "No active category listings found in this sweep cycle. Retry shortly."

            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            # Batch process the first 4 active listings found in the live stream
            for i, link in enumerate(unique_links[:4]):
                url_slug = link.split('/')[-1].replace('.html', '').replace('-', ' ')
                title_guess = re.sub(r'^\d+\s*', '', url_slug).title()
                
                # Construct the thumb URL using the index ID map
                img_url = f"https://images.craigslist.org/{img_ids[i]}_300x300.jpg" if i < len(img_ids) else None
                
                if img_url:
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
                            
                            # Only display items flagged with High Valuation Potential to keep your feed clean
                            if "High" in ai_res.text:
                                output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title_guess}\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                            else:
                                output_report += f"📁 Scanned: {title_guess} -> Low ROI potential detected.\n"
                    except Exception:
                        pass
        else:
            output_report += f"Craigslist Connection Blocked: Status {response.status_code}\n"
    except Exception as e:
        output_report += f"Pipeline Execution Failure: {e}\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
