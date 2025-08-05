"""
Vision-based pagination detection using single element targeting.
"""

import base64
import os
from datetime import datetime
from urllib.parse import urlparse

from config import get_openai_client, LLM_API_AVAILABLE, VISION_MODEL
from pagination import wait_for_page_settle


async def vision_detect_pagination(page, verbose=False) -> dict:
    """Continuously find and click pagination elements until all are exhausted."""
    if not LLM_API_AVAILABLE:
        return {"mode": "none"}
        
    try:
        client = get_openai_client()
        if not client:
            if verbose:
                print("[Vision] No NEBIUS_API_KEY found")
            return {"mode": "none"}

        viewport_size = page.viewport_size or {"width": 1280, "height": 800}
        total_clicks = 0
        max_clicks = 20  # Safety limit to prevent infinite loops
        
        if verbose:
            print("[Vision] Starting continuous pagination clicking until exhausted...")
        
        while total_clicks < max_clicks:
            try:
                if verbose:
                    print(f"\n[Vision] === Pagination Round {total_clicks + 1} ===")
                
                # Start from top of page for each search
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)
                
                # Get current page dimensions
                page_height = await page.evaluate("document.body.scrollHeight")
                scroll_step = int(viewport_size['height'] * 0.75)  # 75% overlap
                max_iterations = min(15, (page_height // scroll_step) + 2)
                
                found_pagination = False
            except Exception as e:
                if verbose:
                    print(f"[Vision] Error in pagination round setup: {e}")
                # If we can't even set up the round, we're likely done
                break
            
            # Scroll through page looking for pagination
            for iteration in range(max_iterations):
                try:
                    current_scroll = await page.evaluate("window.pageYOffset")
                    
                    if verbose:
                        print(f"[Vision] Scanning at scroll position {current_scroll}px")
                    
                    # Take viewport screenshot
                    screenshot_bytes = await page.screenshot(full_page=False)
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                except Exception as e:
                    if verbose:
                        print(f"[Vision] Error during scroll/screenshot: {e}")
                    continue
                
                # Save debug screenshot
                try:
                    domain = urlparse(page.url).netloc
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    os.makedirs("scrapers/debug_screenshots", exist_ok=True)
                    debug_path = f"scrapers/debug_screenshots/{domain}_round{total_clicks+1}_scroll{current_scroll}_{ts}.png"
                    with open(debug_path, "wb") as f:
                        f.write(screenshot_bytes)
                    if verbose:
                        print(f"[Vision] Saved: {debug_path}")
                except Exception as e:
                    if verbose:
                        print(f"[Vision] Could not save debug screenshot: {e}")
                
                # Ask Qwen2.5-VL-72B for pagination elements
                response = client.chat.completions.create(
                    model=VISION_MODEL,
                    temperature=0.1,
                    max_tokens=100,
                    timeout=45.0,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Find pagination elements on this job listings page viewport.\n\nLook for:\n- \"Show More\" / \"Load More\" buttons\n- \"Next\" buttons (not \"Previous\")\n- Higher page numbers (3, 4, 5, etc.)\n- Forward navigation arrows (→, >, »)\n \"more jobs\" or \"more openings\"\n \"careers\"\nPrioritize elements that load MORE content (avoid going backwards).\n\nReturn EXACTLY:\nCLICK,x,y\n\nWhere x,y are exact center coordinates within viewport. \nViewport: {viewport_size['width']}x{viewport_size['height']}\n\nIf no forward pagination visible, return: NONE"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{screenshot_base64}"
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                vision_result = response.choices[0].message.content.strip() if response.choices else ""
                
                if verbose:
                    print(f"[Vision] Vision result: {vision_result}")
                
                if "none" not in vision_result.lower():
                    # Parse the response: CLICK,x,y
                    try:
                        parts = vision_result.strip().split(',')
                        if len(parts) == 3 and parts[0].upper() == 'CLICK':
                            click_x = int(parts[1])
                            click_y = int(parts[2])
                            
                            # Validate coordinates are within viewport
                            if 0 <= click_x < viewport_size['width'] and 0 <= click_y < viewport_size['height']:
                                if verbose:
                                    print(f"[Vision] Found pagination at viewport coordinates: ({click_x}, {click_y})")
                                
                                # Debug: Check what element is at those coordinates
                                debug_result = await page.evaluate(f"""
                                    () => {{
                                        const element = document.elementFromPoint({click_x}, {click_y});
                                        if (element) {{
                                            return {{
                                                tagName: element.tagName,
                                                className: element.className || '',
                                                text: (element.innerText || element.textContent || '').substring(0, 100),
                                                id: element.id || '',
                                                isClickable: element.tagName === 'BUTTON' || element.tagName === 'A' || 
                                                            element.getAttribute('role') === 'button' ||
                                                            window.getComputedStyle(element).cursor === 'pointer'
                                            }};
                                        }} else {{
                                            return {{error: 'No element at coordinates'}};
                                        }}
                                    }}
                                """)
                                
                                if verbose:
                                    if 'error' not in debug_result:
                                        print(f"[Vision] Element: <{debug_result['tagName']}> clickable={debug_result['isClickable']}")
                                        print(f"[Vision] Text: '{debug_result['text']}'")
                                        print(f"[Vision] Class: '{debug_result['className']}'")
                                    else:
                                        print(f"[Vision] Debug error: {debug_result['error']}")
                                
                                # Click the element
                                click_result = await page.evaluate(f"""
                                    () => {{
                                        const element = document.elementFromPoint({click_x}, {click_y});
                                        if (element) {{
                                            element.click();
                                            return {{
                                                success: true,
                                                tagName: element.tagName,
                                                className: element.className || '',
                                                text: (element.innerText || element.textContent || '').substring(0, 100),
                                                id: element.id || ''
                                            }};
                                        }} else {{
                                            return {{success: false, error: 'No element found at coordinates'}};
                                        }}
                                    }}
                                """)
                                
                                if click_result['success']:
                                    total_clicks += 1
                                    if verbose:
                                        print(f"[Vision] ✅ CLICK #{total_clicks}: <{click_result['tagName']}> '{click_result['text']}'")
                                    
                                    # Wait for page to settle after click (handle navigation)
                                    try:
                                        await wait_for_page_settle(page, verbose=False, timeout=8000)
                                        await page.wait_for_timeout(2000)  # Extra wait for dynamic content
                                    except Exception as e:
                                        if verbose:
                                            print(f"[Vision] Page navigation detected: {e}")
                                        # If navigation occurred, wait for new page to load
                                        try:
                                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                                            await page.wait_for_timeout(3000)  # Extra wait for new page
                                            if verbose:
                                                print("[Vision] New page loaded after navigation")
                                        except Exception as nav_error:
                                            if verbose:
                                                print(f"[Vision] Navigation wait failed: {nav_error}")
                                    
                                    found_pagination = True
                                    break  # Break inner loop to start new search from top
                                else:
                                    if verbose:
                                        print(f"[Vision] Click failed: {click_result.get('error', 'Unknown error')}")
                            else:
                                if verbose:
                                    print(f"[Vision] Coordinates ({click_x}, {click_y}) outside viewport bounds")
                    
                    except (ValueError, IndexError) as e:
                        if verbose:
                            print(f"[Vision] Error parsing coordinates: {e}")
                
                # Continue scrolling if no pagination found in current viewport
                try:
                    if current_scroll + scroll_step >= page_height:
                        if verbose:
                            print("[Vision] Reached end of page")
                        break
                    
                    await page.evaluate(f"window.scrollTo(0, {current_scroll + scroll_step})")
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    if verbose:
                        print(f"[Vision] Error during scroll: {e}")
                    break
            
            # If no pagination found in entire page, we're done
            if not found_pagination:
                if verbose:
                    print(f"\n[Vision] 🏁 PAGINATION EXHAUSTED after {total_clicks} clicks")
                    print("[Vision] No more pagination elements found")
                break
        
        if total_clicks >= max_clicks:
            if verbose:
                print(f"\n[Vision] ⚠️ Reached maximum click limit ({max_clicks})")
        
        if total_clicks > 0:
            return {"mode": "vision_click", "total_clicks": total_clicks}
        else:
            return {"mode": "none"}
    
    except Exception as e:
        if verbose:
            print(f"[Vision] Error during pagination detection: {e}")
        return {"mode": "none"}