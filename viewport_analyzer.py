#!/usr/bin/env python3
"""
Viewport Screenshot Analyzer Tool

A tool that agent models can call to analyze webpage screenshots using Qwen 2.5 72B vision model.
Takes a screenshot of the current viewport and identifies interactive elements with bounding boxes and semantic labels.
"""

import asyncio
import base64
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Set
from playwright.async_api import Page
from dotenv import load_dotenv

# Load environment variables before importing config
load_dotenv(dotenv_path='.envfile')

from config import get_openai_client

# Configuration
VISION_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"

class ViewportAnalyzer:
    """Analyzes webpage screenshots and performs actions on interactive elements."""
    
    def __init__(self, client=None, verbose=False):
        """Initialize viewport analyzer with vision model client."""
        self.client = client or get_openai_client()
        self.verbose = verbose
        
        if self.client is None:
            raise ValueError(
                "No OpenAI client available. Please ensure NEBIUS_API_KEY is set in .envfile"
            )
        
    async def analyze_viewport_screenshot(
        self, 
        page: Page, 
        page_url: str = None,
        include_description: bool = True,
        element_types: List[str] = None
    ) -> Dict:
        """
        Analyze current viewport screenshot and identify interactive elements.
        
        Args:
            page: Playwright page object
            page_url: URL of the current page
            include_description: Whether to include text description
            element_types: Types of elements to detect
            
        Returns:
            Dict containing analysis results with elements and their bounding boxes
        """
        if element_types is None:
            element_types = ["button", "input", "link", "clickable"]
            
        try:
            # Get current page URL if not provided
            if not page_url:
                page_url = page.url
                
            # Take viewport screenshot
            screenshot_bytes = await page.screenshot(full_page=False)
            screenshot_path = self._save_screenshot(page_url, screenshot_bytes)
            
            # Convert to base64 for vision model
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
            
            # Get viewport size
            viewport_size = page.viewport_size or {"width": 1280, "height": 800}
            
            # Create prompt based on requested element types
            prompt = self._create_analysis_prompt(element_types, include_description)
            
            # Call vision model
            response = await self._call_vision_model(prompt, screenshot_base64)
            
            # Parse and validate response
            analysis_result = self._parse_vision_response(response)
            
            # Add metadata
            result = {
                "success": True,
                "screenshot_path": screenshot_path,
                "page_url": page_url,
                "viewport_size": viewport_size,
                "timestamp": datetime.now().isoformat(),
                **analysis_result
            }
            
            if self.verbose:
                print(f"[ViewportAnalyzer] Analyzed {page_url}")
                print(f"[ViewportAnalyzer] Found {len(result.get('elements', []))} interactive elements")
                
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "page_url": page_url,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.verbose:
                print(f"[ViewportAnalyzer] Error analyzing {page_url}: {e}")
                
            return error_result
    
    async def perform_action(
        self,
        page: Page,
        action_type: str,
        bbox: List[int] = None,
        text: str = None,
        x: int = None,
        y: int = None,
        option_value: str = None
    ) -> Dict:
        """
        Perform an action on the webpage.
        
        Args:
            page: Playwright page object
            action_type: Type of action ('click', 'input', 'select', 'scroll')
            bbox: Bounding box [x, y, width, height] for click/input actions
            text: Text to input (for 'input' action)
            x, y: Coordinates for scroll action
            option_value: Value to select (for 'select' action)
            
        Returns:
            Dict containing action result
        """
        try:
            if action_type == "click":
                return await self._perform_click(page, bbox)
            elif action_type == "input":
                return await self._perform_input(page, bbox, text)
            elif action_type == "select":
                return await self._perform_select(page, bbox, option_value)
            elif action_type == "scroll":
                return await self._perform_scroll(page, x, y)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action_type": action_type,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _perform_click(self, page: Page, bbox: List[int]) -> Dict:
        """Click on an element using its bounding box."""
        if not bbox or len(bbox) != 4:
            raise ValueError("bbox must be [x, y, width, height]")
            
        # Calculate click coordinates (center of bbox)
        click_x = bbox[0] + bbox[2] // 2
        click_y = bbox[1] + bbox[3] // 2
        
        # Perform click
        await page.mouse.click(click_x, click_y)
        
        # Wait for potential page changes or navigation
        try:
            # Wait for either navigation or timeout
            await page.wait_for_load_state("networkidle", timeout=5000)
        except:
            # If no navigation, just wait for potential dynamic changes
            await page.wait_for_timeout(2000)
        
        if self.verbose:
            print(f"[ViewportAnalyzer] Clicked at ({click_x}, {click_y})")
            
        return {
            "success": True,
            "action_type": "click",
            "coordinates": [click_x, click_y],
            "bbox": bbox,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _perform_input(self, page: Page, bbox: List[int], text: str) -> Dict:
        """Input text into an element using its bounding box."""
        if not bbox or len(bbox) != 4:
            raise ValueError("bbox must be [x, y, width, height]")
        if not text:
            raise ValueError("text is required for input action")
            
        # Calculate click coordinates (center of bbox)
        click_x = bbox[0] + bbox[2] // 2
        click_y = bbox[1] + bbox[3] // 2
        
        # Click to focus the input field
        await page.mouse.click(click_x, click_y)
        await page.wait_for_timeout(1000)  # Increased wait time
        
        # Clear existing text and type new text
        await page.keyboard.press("Control+a")  # Select all
        await page.wait_for_timeout(200)
        await page.keyboard.type(text)
        await page.wait_for_timeout(500)  # Wait for text to be processed
        
        if self.verbose:
            print(f"[ViewportAnalyzer] Typed '{text}' at ({click_x}, {click_y})")
            
        return {
            "success": True,
            "action_type": "input",
            "coordinates": [click_x, click_y],
            "bbox": bbox,
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _perform_select(self, page: Page, bbox: List[int], option_value: str) -> Dict:
        """Select an option from a dropdown using its bounding box."""
        if not bbox or len(bbox) != 4:
            raise ValueError("bbox must be [x, y, width, height]")
        if not option_value:
            raise ValueError("option_value is required for select action")
            
        # Calculate click coordinates (center of bbox)
        click_x = bbox[0] + bbox[2] // 2
        click_y = bbox[1] + bbox[3] // 2
        
        # Click to open dropdown
        await page.mouse.click(click_x, click_y)
        await page.wait_for_timeout(500)
        
        # Try to find and select the option
        try:
            # Method 1: Try direct selection by value
            await page.select_option(f'xpath=//select[contains(@style, "position") or @class]', option_value)
        except:
            try:
                # Method 2: Try clicking on option text
                await page.click(f'text="{option_value}"')
            except:
                # Method 3: Use keyboard navigation
                await page.keyboard.type(option_value)
                await page.keyboard.press("Enter")
        
        if self.verbose:
            print(f"[ViewportAnalyzer] Selected '{option_value}' at ({click_x}, {click_y})")
            
        return {
            "success": True,
            "action_type": "select",
            "coordinates": [click_x, click_y],
            "bbox": bbox,
            "option_value": option_value,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _perform_scroll(self, page: Page, x: int, y: int) -> Dict:
        """Scroll to specific coordinates."""
        if x is None or y is None:
            raise ValueError("Both x and y coordinates are required for scroll action")
            
        # Scroll to coordinates
        await page.evaluate(f"window.scrollTo({x}, {y})")
        await page.wait_for_timeout(1000)  # Wait for scroll to complete
        
        if self.verbose:
            print(f"[ViewportAnalyzer] Scrolled to ({x}, {y})")
            
        return {
            "success": True,
            "action_type": "scroll",
            "coordinates": [x, y],
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_analysis_prompt(self, element_types: List[str], include_description: bool) -> str:
        """Create prompt for vision model based on requested analysis."""
        
        element_descriptions = {
            "button": "Buttons (submit, cancel, action buttons, etc.)",
            "input": "Input fields (text, email, password, search, etc.)",
            "link": "Links and navigation elements",
            "clickable": "Other clickable elements (tabs, toggles, etc.)",
            "form": "Form elements and containers",
            "navigation": "Navigation menus and breadcrumbs",
            "all": "All interactive elements"
        }
        
        # Build element type description
        if "all" in element_types:
            elements_to_find = "all interactive elements including buttons, inputs, links, and any clickable elements"
        else:
            descriptions = [element_descriptions.get(t, t) for t in element_types]
            elements_to_find = ", ".join(descriptions)
        
        prompt = f"""Analyze this webpage screenshot and identify {elements_to_find}.

For each interactive element, provide:
1. Element type: button, input, link, or clickable
2. Visible text/label (or aria-label if no visible text)
3. Bounding box coordinates as [x, y, width, height] where x,y is top-left corner
4. Semantic role/purpose (e.g., "submit_button", "email_input", "navigation_link")
5. Relevant attributes if visible (placeholder text, button type, etc.)

{"Also provide a brief description of what the webpage shows." if include_description else ""}

Return ONLY a JSON object in this exact format:
{{
  {"\"description\": \"Brief description of the webpage content and layout\"," if include_description else ""}
  "elements": [
    {{
      "type": "button|input|link|clickable",
      "label": "visible text or descriptive label",
      "bbox": [x, y, width, height],
      "semantic_role": "descriptive_purpose",
      "attributes": {{"key": "value"}}
    }}
  ]
}}

If no interactive elements are found, return: {{"elements": []}}"""

        return prompt
    
    async def _call_vision_model(self, prompt: str, screenshot_base64: str) -> str:
        """Call the vision model with prompt and screenshot."""
        
        response = self.client.chat.completions.create(
            model=VISION_MODEL,
            temperature=0.1,
            max_tokens=2000,
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
        
        if self.verbose:
            print(f"[ViewportAnalyzer] Vision model raw response:")
            print(f"'{result}'")
            print("-" * 50)
            
        return result
    
    def _parse_vision_response(self, response: str) -> Dict:
        """Parse and validate vision model response."""
        
        # Extract JSON from markdown code blocks if present
        if response.startswith('```json'):
            start = response.find('```json') + 7
            end = response.rfind('```')
            if end > start:
                response = response[start:end].strip()
        elif response.startswith('```'):
            start = response.find('```') + 3
            end = response.rfind('```')
            if end > start:
                response = response[start:end].strip()
        
        try:
            parsed = json.loads(response)
            
            # Validate structure
            if not isinstance(parsed, dict):
                raise ValueError("Response must be a JSON object")
                
            if "elements" not in parsed:
                raise ValueError("Response must contain 'elements' field")
                
            if not isinstance(parsed["elements"], list):
                raise ValueError("'elements' must be a list")
            
            # Validate each element
            for i, element in enumerate(parsed["elements"]):
                self._validate_element(element, i)
            
            return parsed
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
    
    def _validate_element(self, element: Dict, index: int):
        """Validate individual element structure."""
        
        required_fields = ["type", "label", "bbox", "semantic_role"]
        for field in required_fields:
            if field not in element:
                raise ValueError(f"Element {index} missing required field: {field}")
        
        # Validate element type
        valid_types = ["button", "input", "link", "clickable"]
        if element["type"] not in valid_types:
            raise ValueError(f"Element {index} has invalid type: {element['type']}")
        
        # Validate bbox format
        bbox = element["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"Element {index} bbox must be [x, y, width, height]")
            
        if not all(isinstance(x, (int, float)) and x >= 0 for x in bbox):
            raise ValueError(f"Element {index} bbox values must be non-negative numbers")
    
    def _save_screenshot(self, url: str, screenshot_bytes: bytes) -> str:
        """Save screenshot and return path."""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace(":", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            os.makedirs("screenshots", exist_ok=True)
            filename = f"{domain}_viewport_{timestamp}.png"
            path = f"screenshots/{filename}"
            
            with open(path, "wb") as f:
                f.write(screenshot_bytes)
                
            return path
            
        except Exception as e:
            if self.verbose:
                print(f"[ViewportAnalyzer] Could not save screenshot: {e}")
            return None


# Tool interface for agent models
async def analyze_viewport_screenshot(
    page: Page,
    page_url: str = None,
    include_description: bool = True,
    element_types: List[str] = None,
    verbose: bool = False
) -> Dict:
    """
    Tool function that agent models can call to analyze viewport screenshots.
    
    Args:
        page: Playwright page object
        page_url: URL of the current page (optional, will be detected)
        include_description: Whether to include text description of the page
        element_types: List of element types to detect (button, input, link, clickable, form, navigation, all)
        verbose: Whether to print debug information
        
    Returns:
        Dict containing:
        - success: bool
        - screenshot_path: str (path to saved screenshot)
        - page_url: str
        - description: str (if include_description=True)
        - elements: List[Dict] (detected interactive elements with bboxes)
        - viewport_size: Dict (width, height)
        - timestamp: str (ISO format)
        - error: str (if success=False)
    """
    analyzer = ViewportAnalyzer(verbose=verbose)
    return await analyzer.analyze_viewport_screenshot(
        page=page,
        page_url=page_url,
        include_description=include_description,
        element_types=element_types
    )


async def perform_click_action(
    page: Page,
    bbox: List[int],
    verbose: bool = False
) -> Dict:
    """
    Tool function to click on an element using its bounding box.
    
    Args:
        page: Playwright page object
        bbox: Bounding box [x, y, width, height] of element to click
        verbose: Whether to print debug information
        
    Returns:
        Dict containing action result
    """
    analyzer = ViewportAnalyzer(verbose=verbose)
    return await analyzer.perform_action(page, "click", bbox=bbox)


async def perform_input_action(
    page: Page,
    bbox: List[int],
    text: str,
    verbose: bool = False
) -> Dict:
    """
    Tool function to input text into an element using its bounding box.
    
    Args:
        page: Playwright page object
        bbox: Bounding box [x, y, width, height] of input element
        text: Text to input
        verbose: Whether to print debug information
        
    Returns:
        Dict containing action result
    """
    analyzer = ViewportAnalyzer(verbose=verbose)
    return await analyzer.perform_action(page, "input", bbox=bbox, text=text)


async def perform_select_action(
    page: Page,
    bbox: List[int],
    option_value: str,
    verbose: bool = False
) -> Dict:
    """
    Tool function to select an option from a dropdown using its bounding box.
    
    Args:
        page: Playwright page object
        bbox: Bounding box [x, y, width, height] of select element
        option_value: Value or text of option to select
        verbose: Whether to print debug information
        
    Returns:
        Dict containing action result
    """
    analyzer = ViewportAnalyzer(verbose=verbose)
    return await analyzer.perform_action(page, "select", bbox=bbox, option_value=option_value)


async def perform_scroll_action(
    page: Page,
    x: int,
    y: int,
    verbose: bool = False
) -> Dict:
    """
    Tool function to scroll to specific coordinates.
    
    Args:
        page: Playwright page object
        x: X coordinate to scroll to
        y: Y coordinate to scroll to
        verbose: Whether to print debug information
        
    Returns:
        Dict containing action result
    """
    analyzer = ViewportAnalyzer(verbose=verbose)
    return await analyzer.perform_action(page, "scroll", x=x, y=y)


# Example usage
async def main():
    """Example usage of the viewport analyzer."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Navigate to a test page
        await page.goto("https://aijobs.ai")
        await page.wait_for_load_state("networkidle")
        
        # Analyze the viewport
        result = await analyze_viewport_screenshot(
            page=page,
            include_description=True,
            element_types=["button", "input", "link"],
            verbose=True
        )
        
        # Print analysis results
        print("=== VIEWPORT ANALYSIS ===")
        print(json.dumps(result, indent=2))
        
        # Example actions (if elements are found)
        if result.get("success") and result.get("elements"):
            elements = result["elements"]
            
            # Example 1: Click on first button found
            buttons = [e for e in elements if e["type"] == "button"]
            if buttons:
                print("\n=== CLICKING FIRST BUTTON ===")
                click_result = await perform_click_action(
                    page=page,
                    bbox=buttons[0]["bbox"],
                    verbose=True
                )
                print(json.dumps(click_result, indent=2))
            
            # Example 2: Input text in first input field
            inputs = [e for e in elements if e["type"] == "input"]
            if inputs:
                print("\n=== INPUTTING TEXT ===")
                input_result = await perform_input_action(
                    page=page,
                    bbox=inputs[0]["bbox"],
                    text="example@email.com",
                    verbose=True
                )
                print(json.dumps(input_result, indent=2))
            
            # Example 3: Scroll down
            print("\n=== SCROLLING ===")
            scroll_result = await perform_scroll_action(
                page=page,
                x=0,
                y=500,
                verbose=True
            )
            print(json.dumps(scroll_result, indent=2))
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())