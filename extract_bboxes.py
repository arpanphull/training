#!/usr/bin/env python3
"""
Extract bounding boxes from job discovery process for training data.
"""

import json
import asyncio
import base64
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='.envfile')

from playwright.async_api import async_playwright
from config import get_openai_client, LLM_API_AVAILABLE


class BBoxExtractor:
    def __init__(self, client, verbose=True):
        """Initialize bbox extractor with vision model client."""
        self.client = client
        self.verbose = verbose
        self.training_data = []
        
    async def extract_all_bboxes(self, page, url):
        """Extract all job-related bounding boxes from a webpage."""
        
        if self.verbose:
            print(f"\n[BBoxExtractor] Processing: {url}")
            print("=" * 60)
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        viewport_height = page.viewport_size['height'] if page.viewport_size else 800
        page_height = await page.evaluate("document.body.scrollHeight")
        
        all_bboxes = []
        scroll_position = 0
        
        # Take non-overlapping screenshots
        viewport_count = 0
        while scroll_position < page_height:
            # Scroll to exact position for non-overlapping viewport
            await page.evaluate(f"window.scrollTo(0, {scroll_position})")
            await page.wait_for_timeout(1000)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Save screenshot with viewport number
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain = url.replace('https://', '').replace('http://', '').replace('/', '_')
            screenshot_path = f"training_data/screenshots/{domain}_viewport_{viewport_count}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            with open(screenshot_path, 'wb') as f:
                f.write(screenshot_bytes)
            
            if self.verbose:
                print(f"[BBoxExtractor] Analyzing viewport {viewport_count} (position: {scroll_position}px - {scroll_position + viewport_height}px)")
            
            # Extract bounding boxes for all elements using LLM
            bboxes = await self._extract_viewport_bboxes(
                screenshot_base64, 
                url, 
                scroll_position,
                screenshot_path,
                viewport_count
            )
            
            all_bboxes.extend(bboxes)
            
            # Move to next non-overlapping viewport
            scroll_position += viewport_height
            viewport_count += 1
        
        # Also check for hidden menus
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)
        
        hidden_bboxes = await self._extract_hidden_menu_bboxes(page, url)
        all_bboxes.extend(hidden_bboxes)
        
        return all_bboxes
    
    async def _extract_viewport_bboxes(self, screenshot_base64, url, scroll_position, screenshot_path, viewport_count):
        """Extract all bounding boxes from current viewport using LLM."""
        
        prompt = """Identify job/career related clickable elements and their exact bounding boxes.

Focus on:
1. JOB_NAVIGATION: Careers, Jobs, Work with Us links
2. JOB_LISTING: Job titles with apply buttons
3. MENU_BUTTON: Hamburger menus, dropdowns

Return ONLY a JSON array:
[
  {
    "label": "text",
    "category": "JOB_NAVIGATION|JOB_LISTING|MENU_BUTTON",
    "bbox": [x1, y1, x2, y2],
    "clickable": true
  }
]

Empty array if none found: []"""

        try:
            response = self.client.chat.completions.create(
                model="Qwen/Qwen2.5-VL-72B-Instruct",
                temperature=0.1,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]
                }]
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract JSON
            if '```json' in result:
                start = result.find('```json') + 7
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            elif '```' in result:
                start = result.find('```') + 3
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            
            elements = json.loads(result)
            
            # Add metadata to each element
            for element in elements:
                element['url'] = url
                element['viewport_number'] = viewport_count
                element['scroll_position'] = scroll_position
                element['screenshot_path'] = screenshot_path
                # Store both viewport-relative and page-absolute coordinates
                element['bbox_viewport'] = element['bbox']  # Relative to current viewport
                element['bbox_absolute'] = [
                    element['bbox'][0],
                    element['bbox'][1] + scroll_position,
                    element['bbox'][2],
                    element['bbox'][3] + scroll_position
                ]
                
                if self.verbose and element['category'] in ['JOB_NAVIGATION', 'JOB_LISTING', 'MENU_BUTTON']:
                    print(f"  Found: {element['category']} - '{element['label']}' at viewport bbox {element['bbox']}")
            
            return elements
            
        except Exception as e:
            if self.verbose:
                print(f"[BBoxExtractor] Error extracting bboxes: {e}")
            return []
    
    async def _extract_hidden_menu_bboxes(self, page, url):
        """Extract bboxes from hidden menus and dropdowns."""
        
        if self.verbose:
            print(f"[BBoxExtractor] Checking for hidden menus...")
        
        hidden_bboxes = []
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        # Find expandable menus
        prompt = """Find ALL expandable menu elements (hamburger menus, dropdowns, "More" buttons).

Return ONLY JSON array:
[{"label": "description", "bbox": [x1, y1, x2, y2], "type": "hamburger|dropdown|more"}]

Empty array if none: []"""

        try:
            response = self.client.chat.completions.create(
                model="Qwen/Qwen2.5-VL-72B-Instruct",
                temperature=0.1,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]
                }]
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract JSON
            if '```json' in result:
                start = result.find('```json') + 7
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            elif '```' in result:
                start = result.find('```') + 3
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            
            menus = json.loads(result)
            
            for menu in menus:
                # Add as menu button
                hidden_bboxes.append({
                    "label": menu['label'],
                    "category": "MENU_BUTTON",
                    "bbox": menu['bbox'],
                    "confidence": 0.9,
                    "clickable": True,
                    "url": url,
                    "menu_type": menu.get('type', 'unknown'),
                    "hidden_menu": True
                })
                
                if self.verbose:
                    print(f"  Found hidden menu: {menu.get('type')} - '{menu['label']}' at {menu['bbox']}")
        
        except Exception as e:
            if self.verbose:
                print(f"[BBoxExtractor] Error checking menus: {e}")
        
        return hidden_bboxes


async def extract_bboxes_from_url(url, output_file="training_data/bboxes.json"):
    """Extract all bounding boxes from a website."""
    
    if not LLM_API_AVAILABLE:
        print("❌ Error: NEBIUS_API_KEY not found")
        return
    
    client = get_openai_client()
    if not client:
        print("❌ Error: Could not initialize API client")
        return
    
    extractor = BBoxExtractor(client, verbose=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        try:
            # Extract bboxes
            bboxes = await extractor.extract_all_bboxes(page, url)
            
            # Save results
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            output_data = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "total_elements": len(bboxes),
                "elements": bboxes,
                "statistics": {
                    "job_navigation": len([b for b in bboxes if b['category'] == 'JOB_NAVIGATION']),
                    "job_listings": len([b for b in bboxes if b['category'] == 'JOB_LISTING']),
                    "menu_buttons": len([b for b in bboxes if b['category'] == 'MENU_BUTTON']),
                    "apply_buttons": len([b for b in bboxes if b['category'] == 'APPLY_BUTTON']),
                    "other": len([b for b in bboxes if b['category'] not in ['JOB_NAVIGATION', 'JOB_LISTING', 'MENU_BUTTON', 'APPLY_BUTTON']])
                }
            }
            
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            print(f"\n✅ Extraction complete!")
            print(f"📊 Statistics:")
            print(f"  - Total elements: {output_data['statistics']['job_navigation'] + output_data['statistics']['job_listings'] + output_data['statistics']['menu_buttons'] + output_data['statistics']['apply_buttons'] + output_data['statistics']['other']}")
            print(f"  - Job navigation: {output_data['statistics']['job_navigation']}")
            print(f"  - Job listings: {output_data['statistics']['job_listings']}")
            print(f"  - Menu buttons: {output_data['statistics']['menu_buttons']}")
            print(f"  - Apply buttons: {output_data['statistics']['apply_buttons']}")
            print(f"  - Other: {output_data['statistics']['other']}")
            print(f"\n💾 Saved to: {output_file}")
            
            return output_data
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await browser.close()


async def batch_extract(urls_file, output_dir="training_data"):
    """Extract bboxes from multiple websites."""
    
    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📋 Processing {len(urls)} websites")
    
    all_results = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"Processing {i}/{len(urls)}: {url}")
        print('='*60)
        
        domain = url.replace('https://', '').replace('http://', '').replace('/', '_')
        output_file = f"{output_dir}/{domain}_bboxes.json"
        
        result = await extract_bboxes_from_url(url, output_file)
        if result:
            all_results.append(result)
    
    # Save combined results
    combined_file = f"{output_dir}/all_bboxes.json"
    with open(combined_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ Batch extraction complete!")
    print(f"📁 Results saved in: {output_dir}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python extract_bboxes.py <url>")
        print("  python extract_bboxes.py --batch <urls_file>")
        print("\nExample:")
        print("  python extract_bboxes.py https://example.com")
        print("  python extract_bboxes.py --batch websites.txt")
        sys.exit(1)
    
    if sys.argv[1] == "--batch" and len(sys.argv) > 2:
        asyncio.run(batch_extract(sys.argv[2]))
    else:
        asyncio.run(extract_bboxes_from_url(sys.argv[1]))