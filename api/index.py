import os
import re
from http.server import BaseHTTPRequestHandler
from curl_cffi import requests
from google import genai
from google.genai import types

def run_scraper_pipeline():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # 🐝 Keep your ScrapingBee token pasted here
    bee_key = "54c8887115af4dd7b475a9f83dc571b02cf6d77956a"
    
    if not api_key or bee_key == "none":
        return "⚠️ Configuration Missing."

    # 🗺️ Target Region set to Long Island, NY
    region = "longisland"
    search_query = "antique vintage estate"
    target_url = f"https://{region}.craigslist.org/search/sss?query={search_query.replace(' ', '+')}"
    api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={target_url}&render_js=false"
    
    post_links = []
    try:
        response = requests.get(api_url, timeout=25)
        if response.status_code == 200:
            # Grab real listing links from the main Long Island index
            post_links = list(set(re.findall(r'href="(https://[a-z]+\.craigslist\.org/[a-z]+/d/[^"]+\.html)"', response.text)))
    except Exception as e:
        print(f"Index fetch failed: {e}")

    # Initialize Gemini
    client = genai.Client(api_key=api_key)
    sys_instruction = """You are an expert antiquarian and museum appraiser. Your job is to analyze item photos to spot misidentified, highly valuable items being sold for under 10% of their true value (>1000% ROI). 
    Look for makers marks, structural tells, specific historical patterns, or material telltales that the seller missed."""

    output_report = f"📸 VISUAL APPRAISER ONLINE! Scanning top listings in {region}...\n\n"
    
    # If Craigslist has 0 matches today, run a live demo using a real web image so you can see it appraise
    if not post_links:
        output_report += "⚠️ No live regional links found right now. Running visual appraisal on a sample antique target:\n\n"
        demo_img = "https://upload.wikimedia.org/wikipedia/commons/e/e5/Imperial_Filter_Press_Markham_%26_Co.jpg"
        prompt = "Analyze this machine part image. What is its estimated historical value if found on an estate sale for $50? Does it cross 1000% ROI? Respond EXACTLY as:\nPROBABLE ROI: [X%]\nVISUAL EVIDENCE: [1-2 sentences]"
        
        try:
            img_response = requests.get(demo_img)
            ai_res = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=img_response.content, mime_type="image/jpeg"),
                    prompt
                ],
                config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
            )
            output_report += f"🔍 TARGET: Vintage Industrial Machinery\n{ai_res.text}\n🔗 Demo Link\n{'-'*30}\n"
        except Exception as e:
            output_report += f"AI Image Processing error: {e}"
        return output_report

    # Process the top live listings found on Long Island
    for link in post_links[:2]: # Checking 2 listings to protect your free credits
        url_slug = link.split('/')[-1].replace('.html', '').replace('-', ' ')
        title_guess = re.sub(r'^\d+\s*', '', url_slug).title()
        
        # Click into the individual post using ScrapingBee to find the high-res images
        detail_api_url = f"https://app.scrapingbee.com/api/v1/?key={bee_key}&url={link}&render_js=false"
        try:
            detail_res = requests.get(detail_api_url, timeout=20)
            if detail_res.status_code == 200:
                # Find the first high-res JPEG photo link in the post's gallery layout
                img_urls = re.findall(r'src="(https://images\.craigslist\.org/[^"]+\d+x\d+\.jpg)"', detail_res.text)
                
                if img_urls:
                    target_img = img_urls[0]
                    img_data = requests.get(target_img, timeout=10).content
                    
                    prompt = f"Analyze the item image for listing: '{title_guess}'. Look closely for signs it is worth over 1000% of a typical casual asking price. Provide output EXACTLY as:\nPROBABLE ROI: [Estimated % or Low]\nVISUAL EVIDENCE: [1-2 sentences identifying maker marks, materials, or style context]"
                    
                    ai_res = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                            prompt
                        ],
                        config=types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
                    )
                    output_report += f"🔍 LIVE ITEM: {title_guess}\n{ai_res.text}\n🔗 {link}\n{'-'*30}\n"
                else:
                    output_report += f"🔍 LIVE ITEM: {title_guess}\nSkipped: No images found inside listing.\n🔗 {link}\n{'-'*30}\n"
        except Exception as e:
            output_report += f"Error analyzing {title_guess}: {str(e)}\n"

    return output_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        report = run_scraper_pipeline()
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(f"Scraper Executed Successfully.\n\n{report}".encode('utf-8'))
