import os
import re
import io
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from PIL import Image
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return "⚠️ Configuration Missing: GEMINI_API_KEY environment variable not found on Vercel."

    # 🗺️ Target the official, unblocked RSS Feed for Long Island Garage / Moving / Estate Sales
    region = "longisland"
    rss_url = f"https://{region}.craigslist.org/search/gms?format=rss"
    
    output_report = f"📸 BULLETPROOF VISUAL SCANNER ONLINE ({region} Garage & Moving Sale Stream)...\n\n"
    
    try:
        # Fetching directly from the public RSS feed avoids proxy layers completely
        response = requests.get(rss_url, timeout=20)
        if response.status_code == 200:
            xml_content = response.text
            
            # Extract live post elements using clean text boundaries
            items = xml_content.split('<item')[1:]
            
            if not items:
                return output_report + "📡 Feed loaded successfully, but zero active listings are posted right now. Re-scan shortly!"

            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            items_processed = 0
            for item in items:
                if items_processed >= 4: # Limit visual evaluations to top 4 to manage API usage
                    break
                
                # Clean text extraction for link, title, and images from the RSS block
                link_match = re.search(r'<link>(.*?)</link>', item)
                title_match = re.search(r'<title>(.*?)</title>', item)
                img_match = re.search(r'enc:encstring="([A-Za-z0-9_]+)"', item) # Grabs the raw image token
                
                if not link_match or not title_match:
                    continue
                    
                link = link_match.group(1).strip()
                title = title_match.group(1).strip()
                
                # Clean up pricing layouts if present in the RSS title string (e.g. "Vintage Desk - $40")
                price_search = re.search(r'\$(\d+)', title)
                price = f"${price_search.group(1)}" if price_search else "$Unpriced"
                
                # Reconstruct the direct photo image URL if a token exists
                img_url = None
                if img_match:
                    img_id = img_match.group(1)
                    img_url = f"https://images.craigslist.org/{img_id}_300x300.jpg"
                else:
                    # Secondary regex check looking for raw media asset tags inside the XML structure
                    media_match = re.search(r'url="(https://images\.craigslist\.org/[^"]+)"', item)
                    if media_match:
                        img_url = media_match.group(1)

                if img_url:
                    try:
                        img_res = requests.get(img_url, timeout=10)
                        if img_res.status_code == 200:
                            # Normalize picture matrix shapes via Pillow
                            img_obj = Image.open(io.BytesIO(img_res.content)).convert("RGB")
                            
                            prompt = f"Analyze the visual structure of this item listing: '{title}' being sold for {price}. Does it possess historical hallmarks, maker characteristics, or material compositions indicating it is worth >1000% of its current value? Reply strictly as: ROI POTENTIAL: [High/Low] - REASON: [1 sentence]."
                            
                            ai_res = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[img_obj, prompt],
                                config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.1)
                            )
                            
                            if "High" in ai_res.text:
                                output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title}\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                            else:
                                output_report += f"📁 Scanned: {title} -> Low ROI potential detected.\n"
                            
                            items_processed += 1
                    except Exception:
                        pass
        else:
            output_report += f"Craigslist Data Stream Unavailable: HTTP Status {response.status_code}\n"
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
