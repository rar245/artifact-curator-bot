import os
import re
import io
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from PIL import Image
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return "⚠️ Configuration Missing: GEMINI_API_KEY environment variable not found on Vercel."

    region = "longisland"
    rss_url = f"https://{region}.craigslist.org/search/gms?format=rss"
    
    output_report = f"📸 UNCAPPED HIGH-THROUGHPUT ARBITRAGE SCANNER ONLINE ({region} Feed Stream)...\n\n"
    
    try:
        response = requests.get(rss_url, timeout=20)
        if response.status_code == 200:
            xml_raw = response.text
            xml_clean = re.sub(r'xmlns="[^"]+"', '', xml_raw)
            xml_clean = re.sub(r'xmlns:[^=]+="[^"]+"', '', xml_clean)
            
            try:
                root = ET.fromstring(xml_clean)
                items = root.findall('.//item')
            except Exception as parse_error:
                return output_report + f"⚠️ XML Parse Failure: {parse_error}"
            
            if not items:
                return output_report + "📡 Feed parsed successfully, but 0 active items found right now."

            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            # 🔥 THE CONSTRAINT HAS BEEN LIFTED: The engine will now ingest the entire feed array
            for item in items:
                link_el = item.find('link')
                title_el = item.find('title')
                
                if link_el is None or title_el is None:
                    continue
                    
                link = link_el.text.strip() if link_el.text else ""
                title = title_el.text.strip() if title_el.text else ""
                
                if not link or not title:
                    continue
                
                # 🛠️ PRE-FILTER TRIAGE: Instantly skip obvious non-arbitrage assets to save execution time
                lowercase_title = title.lower()
                junk_keywords = ["clothes", "clothing", "shoes", "dvd", "dvds", "tires", "mower", "stroller"]
                if any(keyword in lowercase_title for keyword in junk_keywords):
                    continue  # Bypasses the AI call entirely for junk items

                price_search = re.search(r'\$(\d+)', title)
                price = f"${price_search.group(1)}" if price_search else "$Unpriced"
                
                img_url = None
                enclosure = item.find('.//enclosure')
                if enclosure is not None and 'resource' in enclosure.attrib:
                    img_url = enclosure.attrib['resource']
                else:
                    item_str = ET.tostring(item, encoding='utf-8').decode('utf-8')
                    media_match = re.search(r'url=["\'](https://images\.craigslist\.org/[^"\']+)["\']', item_str)
                    if media_match:
                        img_url = media_match.group(1)

                if img_url:
                    try:
                        high_res_url = re.sub(r'_\d+x\d+\.jpg$', '_600x450.jpg', img_url)
                        img_res = requests.get(high_res_url, timeout=4) # Tight network timeout to prevent lockups
                        
                        if img_res.status_code == 200:
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
                    except Exception:
                        pass # Protects the main loop loop so a single failing image won't crash the program
        else:
            output_report += f"Data stream response dropped: HTTP {response.status_code}\n"
    except Exception as e:
        output_report += f"Execution interrupted: {e}\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
