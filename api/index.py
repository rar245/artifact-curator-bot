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
        return f"⚠️ Configuration Missing: GEMINI_API_KEY={bool(api_key)}, SCRAPINGBEE_KEY={bool(bee_key)}"

    # 🗺️ Broad sweeping category targeting live Garage/Moving/Estate drops
    region = "longisland"
    target_url = f"https://{region}.craigslist.org/search/gms" 
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={target_url}&render_js=false"
    
    output_report = f"📸 HIGH-THROUGHPUT VISUAL SCANNER ONLINE ({region} Garage/Moving Sales)...\n\n"
    
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            html = response.text
            
            # 💡 ROBUST 2026 PATTERN: Extracts links regardless of attribute ordering or spacing
            post_links = re.findall(r'href=["\'](https://[a-z]+\.craigslist\.org/[A-Za-z0-9/_-]+\.html)["\']', html)
            
            # Secondary check: If Craigslist served relative slugs instead of absolute links, resolve them
            if not post_links:
                relative_links = re.findall(r'href=["\'](/[A-Za-z0-9/_-]+\.html)["\']', html)
                post_links = [f"https://{region}.craigslist.org{l}" for l in relative_links]
                
            # Extract live image token hashes directly from the gallery index map
            img_ids = re.findall(r'data-id=["\']([A-Za-z0-9_]+)["\']', html)
            
            # Deduplicate the master URL link queue
            unique_links = []
            for link in post_links:
                if "/d/" in link and link not in unique_links:
                    unique_links.append(link)
            
            if not unique_links:
                return output_report + "⚠️ Index verification step returned 0 active listings. The markup layout is locked or empty right now. Retrying shortly..."

            # Initialize Gemini Curator Evaluation Cluster
            client = genai.Client(api_key=api_key)
            sys_instruction = "You are an antiquarian expert. Review item images to flag misidentified treasures worth >1000% of standard yard-sale prices."

            # Sequentially process the top 4 visual entities in the live category index stream
            for i, link in enumerate(unique_links[:4]):
                url_slug = link.split('/')[-1].replace('.html', '').replace('-', ' ')
                title_guess = re.sub(r'^\d+\s*', '', url_slug).title()
                
                # Match links to their image IDs safely
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
                            
                            # Log the scanned item alongside its high-throughput appraisal results
                            if "High" in ai_res.text:
                                output_report += f"🔥 HIGH ROI TARGET DISCOVERED:\n📦 {title_guess}\n📊 {ai_res.text}\n🔗 Link: {link}\n{'-'*40}\n"
                            else:
                                output_report += f"📁 Scanned: {title_guess} -> Low ROI potential detected.\n"
                    except Exception:
                        pass
        else:
            output_report += f"Craigslist Proxy Link Refused: HTTP Status {response.status_code}\n"
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
