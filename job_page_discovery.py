"""
Vision-based job listing page discovery using Qwen2.5-VL-72B.
Finds all job listing pages on a website by visual analysis.
"""

import base64
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urljoin
from playwright.async_api import Page
import asyncio

# Configuration
VISION_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"
MAX_PAGES_TO_EXPLORE = 50
MAX_DEPTH = 3

class JobPageDiscovery:
    def __init__(self, client, verbose=False):
        """Initialize job page discovery with vision model client."""
        self.client = client
        self.verbose = verbose
        self.visited_urls: Set[str] = set()
        self.job_pages: List[Dict] = []
        self.navigation_links: List[Dict] = []
        self.all_discovered_elements: List[Dict] = []  # Store all elements with bboxes
        
    async def discover_job_pages(self, page: Page, start_url: str) -> Dict:
        """Main discovery method to find all job listing pages."""
        if self.verbose:
            print(f"[JobDiscovery] Starting discovery from: {start_url}")
        
        # Stage 1: Find job-related navigation from homepage
        await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        job_nav_links = await self._find_job_navigation(page)
        
        if self.verbose:
            print(f"[JobDiscovery] Found {len(job_nav_links)} initial navigation links")
        
        # Stage 2: Explore found links and identify job listing pages
        pages_to_explore = [(link, 0) for link in job_nav_links]
        
        # Keep exploring until we find job listing pages or hit limits
        while pages_to_explore and len(self.visited_urls) < MAX_PAGES_TO_EXPLORE:
            current_url, depth = pages_to_explore.pop(0)
            
            if current_url in self.visited_urls or depth > MAX_DEPTH:
                continue
                
            self.visited_urls.add(current_url)
            
            if self.verbose:
                print(f"\n[JobDiscovery] Exploring (depth {depth}): {current_url}")
            
            try:
                await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                # Check if this is a job listing page
                is_job_page = await self._verify_job_listing_page(page)
                
                if is_job_page['is_job_page']:
                    self.job_pages.append({
                        'url': current_url,
                        'confidence': is_job_page['confidence'],
                        'job_count': is_job_page.get('job_count', 0),
                        'page_type': is_job_page.get('page_type', 'unknown'),
                        'depth': depth
                    })
                    
                    if self.verbose:
                        print(f"[JobDiscovery] ✅ Found job page: {current_url}")
                        print(f"    - Confidence: {is_job_page['confidence']:.1%}")
                        print(f"    - Type: {is_job_page.get('page_type', 'unknown')}")
                        if is_job_page.get('job_count'):
                            print(f"    - Estimated jobs: {is_job_page.get('job_count')}")
                    
                    # Look for pagination or related job pages
                    related_links = await self._find_related_job_pages(page)
                    for link in related_links:
                        if link not in self.visited_urls:
                            pages_to_explore.append((link, depth + 1))
                            if self.verbose:
                                print(f"[JobDiscovery] Added related page to explore: {link}")
                
                else:
                    # If not a job page, it might be an intermediate navigation page
                    if self.verbose:
                        print(f"[JobDiscovery] Not a job listing page, checking for further navigation...")
                        print(f"    - Page type: {is_job_page.get('page_type', 'unknown')}")
                    
                    # Look for navigation to job sections (could be sub-navigation)
                    nav_links = await self._find_job_navigation(page)
                    
                    if nav_links:
                        if self.verbose:
                            print(f"[JobDiscovery] Found {len(nav_links)} additional navigation links")
                        for link in nav_links:
                            if link not in self.visited_urls:
                                pages_to_explore.append((link, depth + 1))
                    
                    # Also check for any job-related links on intermediate pages
                    job_links = await self._find_job_links_on_page(page)
                    for link in job_links:
                        if link not in self.visited_urls:
                            pages_to_explore.append((link, depth + 1))
                            if self.verbose:
                                print(f"[JobDiscovery] Found potential job link: {link}")
                            
            except Exception as e:
                if self.verbose:
                    print(f"[JobDiscovery] Error exploring {current_url}: {e}")
                continue
        
        return {
            'job_pages': self.job_pages,
            'total_pages_explored': len(self.visited_urls),
            'total_job_pages_found': len(self.job_pages),
            'discovered_elements': self.all_discovered_elements,  # Include all elements with bboxes
            'total_elements_discovered': len(self.all_discovered_elements)
        }
    
    async def _find_job_navigation(self, page: Page) -> List[str]:
        """Find and click job-related navigation links using progressive scrolling."""
        discovered_urls = []
        
        try:
            viewport_height = page.viewport_size['height'] if page.viewport_size else 800
            
            # Get total page height
            page_height = await page.evaluate("document.body.scrollHeight")
            
            if self.verbose:
                print(f"[JobDiscovery] Page height: {page_height}px, Viewport: {viewport_height}px")
            
            # Progressive scrolling through the page with non-overlapping viewports
            scroll_position = 0
            found_elements = []
            viewport_count = 0
            
            while scroll_position < page_height:
                # Scroll to current position
                await page.evaluate(f"window.scrollTo(0, {scroll_position})")
                await page.wait_for_timeout(1000)
                
                # Take screenshot of current viewport
                screenshot_bytes = await page.screenshot(full_page=False)
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                if self.verbose:
                    self._save_debug_screenshot(page.url, screenshot_bytes, f"viewport_{viewport_count}")
                    print(f"[JobDiscovery] Analyzing viewport {viewport_count} (position: {scroll_position}px)")
                
                # Ask vision model to find ALL clickable elements with exact bboxes
                prompt = """Identify ALL clickable elements related to jobs/careers in this screenshot.

Look for:
- "Careers", "Jobs", "Work with Us", "Join Us", "Opportunities"
- "Open Positions", "Vacancies", "Employment", "Hiring"
- "Early Careers", "Students", "Graduates", "Internships"
- Any clickable text/button suggesting jobs or careers

IMPORTANT: Provide exact bounding box coordinates for EACH clickable element.

Return ONLY a JSON array with exact coordinates:
[{"label": "text on element", "bbox": [x1, y1, x2, y2], "clickable": true}]

bbox format: [left, top, right, bottom] in pixels
If none found, return: []"""

                response = self.client.chat.completions.create(
                    model=VISION_MODEL,
                    temperature=0.1,
                    max_tokens=300,
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
                
                try:
                    elements = json.loads(result)
                    
                    if elements and self.verbose:
                        print(f"[JobDiscovery] Found {len(elements)} elements in viewport {viewport_count}")
                    
                    # Process found elements
                    for element in elements:
                        label = element['label']
                        
                        # Check if we've already found this element
                        if any(e['label'] == label for e in found_elements):
                            continue
                        
                        # Add viewport metadata to element
                        element['viewport_number'] = viewport_count
                        element['scroll_position'] = scroll_position
                        element['page_url'] = page.url
                        
                        found_elements.append(element)
                        self.all_discovered_elements.append(element)  # Store for training data
                        bbox = element['bbox']
                        
                        # Calculate click position
                        if len(bbox) == 4:
                            if bbox[2] > 100 and bbox[3] > 100:  # x1, y1, x2, y2
                                click_x = (bbox[0] + bbox[2]) // 2
                                click_y = (bbox[1] + bbox[3]) // 2
                            else:  # x, y, width, height
                                click_x = bbox[0] + bbox[2] // 2
                                click_y = bbox[1] + bbox[3] // 2
                        else:
                            continue
                        
                        if self.verbose:
                            print(f"[JobDiscovery] Clicking '{label}' at ({click_x}, {click_y})")
                        
                        try:
                            current_url = page.url
                            
                            if self.verbose:
                                print(f"[JobDiscovery] Current URL before click: {current_url}")
                            
                            # Try clicking the element
                            click_success = False
                            try:
                                # Method 1: Direct mouse click
                                await page.mouse.click(click_x, click_y)
                                click_success = True
                            except Exception as e1:
                                try:
                                    # Method 2: Playwright click with position
                                    await page.click("body", position={"x": click_x, "y": click_y}, timeout=2000)
                                    click_success = True
                                except Exception as e2:
                                    if self.verbose:
                                        print(f"[JobDiscovery] Click failed: {e2}")
                            
                            if click_success:
                                # Wait for potential navigation or content change
                                await page.wait_for_timeout(2000)
                                
                                try:
                                    # Wait for any navigation
                                    await page.wait_for_url(lambda url: url != current_url, timeout=3000)
                                except:
                                    pass
                                
                                new_url = page.url
                                
                                if new_url != current_url:
                                    discovered_urls.append(new_url)
                                    if self.verbose:
                                        print(f"[JobDiscovery] ✅ Navigated to: {new_url}")
                                    
                                    # Don't go back yet - save URL to explore later
                                else:
                                    if self.verbose:
                                        print(f"[JobDiscovery] No navigation occurred, URL still: {new_url}")
                        
                        except Exception as e:
                            if self.verbose:
                                print(f"[JobDiscovery] Could not click '{label}': {e}")
                
                except json.JSONDecodeError:
                    if self.verbose:
                        print(f"[JobDiscovery] Could not parse response at scroll {scroll_position}")
                
                # Move to next non-overlapping viewport
                scroll_position += viewport_height
                viewport_count += 1
            
            # Check for hamburger menus or dropdowns at the top
            if not discovered_urls:
                if self.verbose:
                    print("[JobDiscovery] No direct navigation found, checking for hidden menus...")
                
                # Scroll back to top
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1000)
                
                # Check for hamburger menu or dropdowns
                discovered_urls.extend(await self._check_hidden_menus(page))
            
            if self.verbose:
                print(f"[JobDiscovery] Total URLs discovered from navigation: {len(discovered_urls)}")
                for url in discovered_urls:
                    print(f"  - {url}")
            
            return discovered_urls
                
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Error in navigation discovery: {e}")
            return discovered_urls
    
    async def _check_hidden_menus(self, page: Page) -> List[str]:
        """Check for hamburger menus, dropdowns, or other hidden navigation elements."""
        discovered_urls = []
        
        try:
            # Take screenshot of header area
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            if self.verbose:
                self._save_debug_screenshot(page.url, screenshot_bytes, "check_menus")
            
            # Ask vision model to find expandable menus
            prompt = """Identify ALL expandable navigation elements in this screenshot:

Look for:
- Hamburger menus (☰ three lines icon)
- Dropdown arrows (▼ or similar)
- "More" or "Menu" buttons
- Any clickable element that might expand to show more options

Return ONLY a JSON array:
[{"label": "description", "bbox": [x1, y1, x2, y2], "type": "hamburger|dropdown|more"}]

If none found, return: []"""

            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                temperature=0.1,
                max_tokens=300,
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
            
            try:
                menus = json.loads(result)
                
                for menu in menus:
                    if self.verbose:
                        print(f"[JobDiscovery] Found {menu.get('type', 'menu')}: {menu['label']}")
                    
                    bbox = menu['bbox']
                    
                    # Calculate click position
                    if len(bbox) == 4:
                        if bbox[2] > 100 and bbox[3] > 100:  # x1, y1, x2, y2
                            click_x = (bbox[0] + bbox[2]) // 2
                            click_y = (bbox[1] + bbox[3]) // 2
                        else:  # x, y, width, height
                            click_x = bbox[0] + bbox[2] // 2
                            click_y = bbox[1] + bbox[3] // 2
                    else:
                        continue
                    
                    try:
                        # Click to open menu
                        await page.mouse.click(click_x, click_y)
                        await page.wait_for_timeout(1500)
                        
                        # Take screenshot of expanded menu
                        expanded_screenshot = await page.screenshot(full_page=False)
                        expanded_base64 = base64.b64encode(expanded_screenshot).decode('utf-8')
                        
                        if self.verbose:
                            self._save_debug_screenshot(page.url, expanded_screenshot, f"expanded_{menu.get('type', 'menu')}")
                        
                        # Look for job links in expanded menu
                        find_prompt = """Find career/job related links in this expanded menu:

Look for: Careers, Jobs, Work with Us, Opportunities, etc.

Return ONLY a JSON array:
[{"label": "text", "bbox": [x1, y1, x2, y2]}]

If none found, return: []"""

                        find_response = self.client.chat.completions.create(
                            model=VISION_MODEL,
                            temperature=0.1,
                            max_tokens=300,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": find_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{expanded_base64}"}}
                                ]
                            }]
                        )
                        
                        find_result = find_response.choices[0].message.content.strip()
                        
                        # Extract JSON
                        if '```json' in find_result:
                            start = find_result.find('```json') + 7
                            end = find_result.find('```', start)
                            if end > start:
                                find_result = find_result[start:end].strip()
                        elif '```' in find_result:
                            start = find_result.find('```') + 3
                            end = find_result.find('```', start)
                            if end > start:
                                find_result = find_result[start:end].strip()
                        
                        try:
                            job_links = json.loads(find_result)
                            
                            for link in job_links:
                                link_bbox = link['bbox']
                                
                                # Calculate click position
                                if len(link_bbox) == 4:
                                    if link_bbox[2] > 100 and link_bbox[3] > 100:
                                        link_x = (link_bbox[0] + link_bbox[2]) // 2
                                        link_y = (link_bbox[1] + link_bbox[3]) // 2
                                    else:
                                        link_x = link_bbox[0] + link_bbox[2] // 2
                                        link_y = link_bbox[1] + link_bbox[3] // 2
                                    
                                    current_url = page.url
                                    
                                    # Click the job link
                                    await page.mouse.click(link_x, link_y)
                                    
                                    # Wait for navigation
                                    try:
                                        await page.wait_for_load_state("domcontentloaded", timeout=3000)
                                    except:
                                        await page.wait_for_timeout(1000)
                                    
                                    new_url = page.url
                                    
                                    if new_url != current_url:
                                        discovered_urls.append(new_url)
                                        if self.verbose:
                                            print(f"[JobDiscovery] ✅ Found in menu: {link['label']} -> {new_url}")
                                        
                                        # Go back
                                        await page.go_back()
                                        await page.wait_for_load_state("domcontentloaded")
                        
                        except json.JSONDecodeError:
                            if self.verbose:
                                print(f"[JobDiscovery] Could not parse job links in menu")
                        
                        # Close menu (click elsewhere or ESC)
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                    
                    except Exception as e:
                        if self.verbose:
                            print(f"[JobDiscovery] Error checking menu: {e}")
            
            except json.JSONDecodeError:
                if self.verbose:
                    print("[JobDiscovery] No expandable menus found")
            
            return discovered_urls
            
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Error checking hidden menus: {e}")
            return discovered_urls
    
    async def _verify_job_listing_page(self, page: Page) -> Dict:
        """Verify if current page contains job listings."""
        try:
            # Take full page screenshot for analysis
            viewport_size = page.viewport_size or {"width": 1280, "height": 800}
            screenshot_bytes = await page.screenshot(clip={"x": 0, "y": 0, "width": viewport_size["width"], "height": min(2000, viewport_size["height"] * 2)})
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            if self.verbose:
                self._save_debug_screenshot(page.url, screenshot_bytes, "verification")
            
            # Ask vision model to analyze if this is a job listing page
            prompt = """Analyze this webpage and determine if it's a job listing page.

Look for these patterns:
1. Multiple job cards/listings in a grid or list layout
2. Job titles (e.g., "Software Engineer", "Product Manager")
3. Location infor


Return a JSON response:
{
  "is_job_page": true/false,
  "confidence": 0.0-1.0,
  "job_count": estimated_number_of_jobs,
  "page_type": "job_listing" | "job_detail" | "career_landing" | "not_job_related",
  "indicators": ["multiple apply buttons", "job titles visible", etc]
}"""

            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                temperature=0.1,
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
                            }
                        ]
                    }
                ]
            )
            
            result = response.choices[0].message.content.strip()
            
            try:
                analysis = json.loads(result)
                return analysis
            except json.JSONDecodeError:
                # Fallback parsing
                is_job = "true" in result.lower() and "job" in result.lower()
                return {
                    "is_job_page": is_job,
                    "confidence": 0.5,
                    "page_type": "unknown"
                }
                
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Error verifying page: {e}")
            return {"is_job_page": False, "confidence": 0.0}
    
    async def _find_job_links_on_page(self, page: Page) -> List[str]:
        """Find any job-related links on the current page using vision model."""
        try:
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Look for any job-related links
            prompt = """Analyze this page and find ALL links that might lead to job listings or job-related pages.

Look for links containing:
- "View Jobs", "See Openings", "Browse Positions"
- "Apply Now", "Join Team", "Current Openings"
- Department/team names with job indicators
- Location-based job links
- "Search Jobs", "Find Jobs", "Explore Opportunities"
- Any text suggesting job listings or application processes

Return JSON array of clickable elements:
[{"label": "text of link", "bbox": [x1, y1, x2, y2]}]

Return [] if no job-related links found."""

            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                temperature=0.1,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
                            }
                        ]
                    }
                ]
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            if result.startswith('```json'):
                start = result.find('```json') + 7
                end = result.rfind('```')
                if end > start:
                    result = result[start:end].strip()
            elif result.startswith('```'):
                start = result.find('```') + 3
                end = result.rfind('```')
                if end > start:
                    result = result[start:end].strip()
            
            try:
                elements = json.loads(result)
                links = []
                
                for element in elements:
                    bbox = element['bbox']
                    
                    # Calculate click position
                    if len(bbox) == 4:
                        if bbox[2] > 100 and bbox[3] > 100:  # x1, y1, x2, y2
                            click_x = (bbox[0] + bbox[2]) // 2
                            click_y = (bbox[1] + bbox[3]) // 2
                        else:  # x, y, width, height
                            click_x = bbox[0] + bbox[2] // 2
                            click_y = bbox[1] + bbox[3] // 2
                    else:
                        continue
                    
                    # Get href without clicking
                    href = await page.evaluate(f"""
                        () => {{
                            const element = document.elementFromPoint({click_x}, {click_y});
                            if (element) {{
                                const link = element.closest('a') || element;
                                return link.href || null;
                            }}
                            return null;
                        }}
                    """)
                    
                    if href:
                        absolute_url = urljoin(page.url, href)
                        links.append(absolute_url)
                
                return links
                
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Error finding job links: {e}")
            return []
    
    async def _find_related_job_pages(self, page: Page) -> List[str]:
        """Find pagination and related job page links."""
        try:
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Look for pagination and category links
            prompt = """Find pagination and job category navigation on this job listing page.

Look for:
- Page numbers (2, 3, 4, etc.)
- "Next", "Load More", "Show More" buttons
- Department/category filters (Engineering, Sales, Marketing)
- Location filters
- Job type filters (Full-time, Remote, etc.)

Return JSON array of clickable elements that lead to more job listings:
[{"label": "Page 2", "bbox": [x, y, width, height]}]

Return [] if none found."""

            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                temperature=0.1,
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
                            }
                        ]
                    }
                ]
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            if '```json' in result:
                # Extract content between ```json and ```
                start = result.find('```json') + 7
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            elif '```' in result:
                # Extract content between ``` and ```
                start = result.find('```') + 3
                end = result.find('```', start)
                if end > start:
                    result = result[start:end].strip()
            
            try:
                if self.verbose:
                    print(f"[JobDiscovery] Vision model raw response for related pages:")
                    print(f"'{result}'")
                    print("-" * 50)
                
                elements = json.loads(result)
                links = []
                
                for element in elements:
                    bbox = element['bbox']
                    click_x = bbox[0] + bbox[2] // 2
                    click_y = bbox[1] + bbox[3] // 2
                    
                    href = await page.evaluate(f"""
                        () => {{
                            const element = document.elementFromPoint({click_x}, {click_y});
                            if (element) {{
                                const link = element.closest('a') || element;
                                return link.href || null;
                            }}
                            return null;
                        }}
                    """)
                    
                    if href:
                        absolute_url = urljoin(page.url, href)
                        links.append(absolute_url)
                
                return links
                
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Error finding related pages: {e}")
            return []
    
    def _save_debug_screenshot(self, url: str, screenshot_bytes: bytes, stage: str):
        """Save debug screenshot."""
        try:
            domain = urlparse(url).netloc
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs("job_discovery_screenshots", exist_ok=True)
            path = f"job_discovery_screenshots/{domain}_{stage}_{ts}.png"
            with open(path, "wb") as f:
                f.write(screenshot_bytes)
            if self.verbose:
                print(f"[JobDiscovery] Saved screenshot: {path}")
        except Exception as e:
            if self.verbose:
                print(f"[JobDiscovery] Could not save screenshot: {e}")


async def discover_all_job_pages(page: Page, website_url: str, client, verbose=True) -> Dict:
    """Main function to discover all job pages on a website."""
    discovery = JobPageDiscovery(client, verbose=verbose)
    results = await discovery.discover_job_pages(page, website_url)
    
    if verbose:
        print("\n" + "="*50)
        print("JOB PAGE DISCOVERY RESULTS")
        print("="*50)
        print(f"Total pages explored: {results['total_pages_explored']}")
        print(f"Job pages found: {results['total_job_pages_found']}")
        print("\nJob Pages:")
        for job_page in results['job_pages']:
            print(f"  - {job_page['url']}")
            print(f"    Confidence: {job_page['confidence']:.2f}")
            print(f"    Type: {job_page['page_type']}")
            if job_page.get('job_count'):
                print(f"    Estimated jobs: {job_page['job_count']}")
    
    return results


# Example usage
async def main():
    from playwright.async_api import async_playwright
    
    # You'll need to set up your Qwen client here
    # from your_qwen_wrapper import get_qwen_client
    # client = get_qwen_client()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Example: Discover job pages on a website
        # results = await discover_all_job_pages(
        #     page, 
        #     "https://example.com",
        #     client,
        #     verbose=True
        # )
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())