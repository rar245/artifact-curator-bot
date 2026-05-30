import os
import re
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    # 🔐 Securely reading the token directly from Vercel's cloud environment keys
    bee_key = os.environ.get("SCRAPINGBEE_KEY")
    
    if not api_key or not bee_key:
        return f"⚠️ Configuration Missing: Check Vercel Environment Variables. GEMINI_API_KEY found: {bool(api_key)}, SCRAPINGBEE_KEY found: {bool(bee_key)}"

    region = "longisland"
    search_query = "antique vintage estate"
    target_url = f"https://{region}.craigslist.org/search/sss?query={search_query.replace(' ', '+')}"
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={target_url}&render_js=false"
    
    html_content = ""
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            html_content = response.text
    except Exception as e:
        print(f"Index fetch failed: {e}")

    items_to_check = []
    if html_content:
        raw_links = re.findall(r'href="(https://[a-z]+\.craigslist\.org/[a-z]+/d/[^"]+\.html)"', html_content)
        raw_prices = re.findall(r'(?:\$[0-9,]+)', html_content)
        
        unique_links = list(set(raw_links))
        for i, link in enumerate(unique_links[:2]): 
            price = raw_prices[i] if i < len(raw_prices) else "$Unknown"
            url_slug = link.split('/')[-1].replace('.html', '').replace('-', ' ')
            title_guess = re.sub(r'^\d+\s*', '', url_slug).title()
            
            items_to_check.append({
                "title": title_guess,
                "price": price,
                "link": link,
                "is_demo": False
            })

    # Demo Fallback Target
    if not items_to_check:
        items_to_check = [{
            "title": "Industrial Mechanical Filter Press",
            "price": "$50",
            "link": "https://upload.wikimedia.org/wikipedia/commons/e/e5/Imperial_Filter_Press_Markham_%26_Co.jpg",
            "is_demo": True
        }]

    # Initialize Gemini Appraiser Brain
    client = genai.Client(api_key=api_key)
    sys_instruction = """You are an expert antiquarian and museum art appraiser. Your exclusive job is to evaluate item images to discover misidentified, extremely rare objects being sold for a fraction of their true worth. 
    Calculate value purely from structural clues, maker marks, material tells, or craftsmanship eras. Flag targets crossing 1000% ROI."""

    output_report = f"📸 VISUAL 1000% ROI APPRAISER ONLINE! Scouting {region} Classifieds...\n\n"
    
    for item in items_to_check:
        img_data = None
        
        if item["is_demo"]:
            try:
                img_data = requests.get(item["link"]).content
            except Exception:
                pass
        else:
            # Click directly into the listing detail page to grab the high-resolution photo asset
            detail_api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={item['link']}&render_js=false"
            try:
                detail_res = requests.get(detail_api_url, timeout=20)
                if detail_res.status_code == 200:
                    img_urls = re.findall(r'src="(https://images\.craigslist\.org/[^"]+\d+x\d+\.jpg)"', detail_res.text)
                    if img_urls:
                        img_data = requests.get(img_urls[0], timeout=10).content
            except Exception as e:
                output_report += f"Error connecting to subpage layout: {e}\n"

        if img_data:
            prompt = f"""Review the item photo for listing: '{item['title']}' being sold at an asking price of: {item['price']}.
            Examine the photo for physical evidence proving this object is an authentic historical asset worth over 1000% of this price.
            
            Respond strictly in this template format:
            TARGET COMPLETION: [YES or NO]
            ESTIMATED VALUE: [Provide currency range based on visual authentication]
            PROBABLE ROI: [X% or Low]
            VISUAL PROOF: [Provide 1-2 analytical sentences identifying specific design traits, era, maker marks, or material composition seen in the image]"""
            
            try:
                # 💡 FIX: Feeding raw network content bytes directly into data solves the encoding error
                ai_res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.1)
                )
                
                label = "DEMO ITEM" if item["is_demo"] else "LIVE FIND"
                output_report += f"🔍 [{label}]: {item['title']} (Asking: {item['price']})\n{ai_res.text}\n🔗 Source: {item['link']}\n{'-'*40}\n"
            except Exception as e:
                output_report += f"🔍 ITEM: {item['title']} -> Vision appraisal module failed: {str(e)}\n"
        else:
            output_report += f"🔍 LIVE ITEM: {item['title']}\nSkipped: Image gallery asset links unextractable.\n🔗 {item['link']}\n{'-'*40}\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
