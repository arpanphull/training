#!/usr/bin/env python3
"""
Simple job discovery that follows clicks to job listing pages.
"""

import asyncio
import json
import base64
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(dotenv_path='.envfile')

from playwright.async_api import async_playwright, Page
from config import get_openai_client, LLM_API_AVAILABLE

VISION_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"

class SimpleJobDiscovery:
    def __init__(self, client, verbose=True):
        self.client = client
        self.verbose = verbose
        self.visited_urls = set()
        self.job_pages = []
        self.discovered_elements = []
        
    async def discover(self, page: Page, start_url: str, max_depth=3) -> Dict:
        """Discover job pages by following navigation."""
        
        print(f"\n🔍 Starting discovery from: {start_url}")
        
        # Navigate to start page
        await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Find and click job navigation
        await self._explore_page(page, 0, max_depth)
        
        return {
            'job_pages': self.job_pages,
            'visited_urls': list(self.visited_urls),
            'discovered_elements': self.discovered_elements,
            'total_elements': len(self.discovered_elements)
        }
    
    async def _explore_page(self, page: Page, depth: int, max_depth: int):
        """Explore current page and follow job-related links."""
        
        current_url = page.url
        
        if current_url in self.visited_urls or depth > max_depth:
            return
            
        self.visited_urls.add(current_url)
        
        print(f"\n📍 Exploring (depth {depth}): {current_url}")
        
        # Check if this is a job listing page
        is_job_page = await self._check_if_job_page(page)
        if is_job_page:
            self.job_pages.append({
                'url': current_url,
                'depth': depth,
                'timestamp': datetime.now().isoformat()
            })
            print(f"✅ Found job listing page!")
            # Continue exploring for more job pages
        
        # Find job-related clickable elements
        element = await self._find_next_job_element(page)
        
        if element:
            print(f"🎯 Found element: '{element['label']}' at {element['bbox']}")
            self.discovered_elements.append(element)
            
            # Click the element
            clicked = await self._click_element(page, element)
            
            if clicked:
                # Wait for navigation
                await page.wait_for_timeout(3000)
                new_url = page.url
                
                if new_url != current_url:
                    print(f"➡️ Navigated to: {new_url}")
                    # Continue exploring on new page
                    await self._explore_page(page, depth + 1, max_depth)
                else:
                    print(f"⚠️ No navigation occurred")
        else:
            print(f"❌ No more job-related elements found")
    
    async def _find_next_job_element(self, page: Page) -> Dict:
        """Find the next job-related element to click by scrolling through page."""
        
        viewport_height = page.viewport_size['height'] if page.viewport_size else 800
        page_height = await page.evaluate("document.body.scrollHeight")
        
        # Scroll through page to find job elements
        scroll_position = 0
        
        while scroll_position <= page_height:
            # Scroll to position
            await page.evaluate(f"window.scrollTo(0, {scroll_position})")
            await page.wait_for_timeout(500)
            
            # Take screenshot
            screenshot = await page.screenshot(full_page=False)
            screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')
            
            if self.verbose:
                print(f"  Checking viewport at position {scroll_position}px")
            
            # Ask LLM to find job-related element
            prompt = """Find ANY clickable element related to jobs/careers in this screenshot.

Look for: Careers, Jobs, Work with Us, Open Positions, Join Us, Opportunities, Apply, etc.

Return the FIRST job-related element found:
{"label": "text", "bbox": [x1, y1, x2, y2]}

Return null if none found in this viewport."""

            try:
                response = self.client.chat.completions.create(
                    model=VISION_MODEL,
                    temperature=0.1,
                    max_tokens=200,
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
                
                element = json.loads(result)
                
                if element and element != "null" and element is not None:
                    element['page_url'] = page.url
                    element['scroll_position'] = scroll_position
                    element['timestamp'] = datetime.now().isoformat()
                    
                    # Save screenshot where element was found
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"discovery_screenshots/found_{timestamp}.png"
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    with open(filename, 'wb') as f:
                        f.write(screenshot)
                    
                    return element
                    
            except Exception as e:
                if self.verbose:
                    print(f"  Error parsing response: {e}")
            
            # Move to next viewport
            scroll_position += viewport_height
        
        return None
    
    async def _click_element(self, page: Page, element: Dict) -> bool:
        """Click the element."""
        
        try:
            bbox = element['bbox']
            
            # Calculate click position
            if len(bbox) == 4:
                if bbox[2] > 100 and bbox[3] > 100:  # x1, y1, x2, y2
                    click_x = (bbox[0] + bbox[2]) // 2
                    click_y = (bbox[1] + bbox[3]) // 2
                else:  # x, y, width, height
                    click_x = bbox[0] + bbox[2] // 2
                    click_y = bbox[1] + bbox[3] // 2
                
                print(f"🖱️ Clicking at ({click_x}, {click_y})")
                
                # Click
                await page.mouse.click(click_x, click_y)
                return True
                
        except Exception as e:
            print(f"❌ Click failed: {e}")
            
        return False
    
    async def _check_if_job_page(self, page: Page) -> bool:
        """Check if current page is a job listing page."""
        
        screenshot = await page.screenshot(full_page=False)
        screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')
        
        prompt = """Is this a job listing page with actual job openings?

Look for:
- Multiple job titles with apply buttons
- Job cards in a list/grid
- Filters for department/location
- "Apply" buttons

Return: true or false"""

        try:
            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                temperature=0.1,
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}}
                    ]
                }]
            )
            
            result = response.choices[0].message.content.strip().lower()
            return "true" in result
            
        except:
            return False


async def main():
    """Run simple job discovery."""
    
    if not LLM_API_AVAILABLE:
        print("❌ Error: NEBIUS_API_KEY not found")
        return
    
    client = get_openai_client()
    
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://stripe.com"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        discovery = SimpleJobDiscovery(client)
        results = await discovery.discover(page, url)
        
        # Save results
        with open('simple_discovery_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📊 RESULTS:")
        print(f"  - Visited: {len(results['visited_urls'])} pages")
        print(f"  - Found: {len(results['job_pages'])} job pages")
        print(f"  - Discovered: {len(results['discovered_elements'])} elements")
        
        if results['job_pages']:
            print(f"\n🎯 Job Pages Found:")
            for jp in results['job_pages']:
                print(f"  - {jp['url']}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())