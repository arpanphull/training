#!/usr/bin/env python3
"""
Test Tool Actions Separately

This script tests each web automation tool action individually to ensure
they work correctly before integrating with Claude.
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright
from sonnet_tools_interface import get_tools_for_sonnet, create_tool_handler

class ToolActionTester:
    """Test individual tool actions."""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.tool_handler = None
        self.test_results = []
    
    async def setup(self):
        """Set up browser and page."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.page = await self.browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        self.tool_handler = create_tool_handler(self.page)
        print("🌐 Browser setup complete")
    
    async def test_navigation(self):
        """Test navigate_to_url tool."""
        print("\n" + "="*50)
        print("🧪 TESTING NAVIGATION")
        print("="*50)
        
        test_urls = [
            "https://httpbin.org/forms/post",
            "https://aijobs.ai",
            "https://example.com"
        ]
        
        for url in test_urls:
            print(f"\n🔗 Testing navigation to: {url}")
            
            result = await self.tool_handler.execute_tool("navigate_to_url", {
                "url": url,
                "wait_for": "networkidle"
            })
            
            success = result.get("success", False)
            print(f"   ✅ Success: {success}")
            if success:
                print(f"   📄 Title: {result.get('title', 'N/A')}")
                print(f"   🌐 Final URL: {result.get('url', 'N/A')}")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown')}")
            
            self.test_results.append({
                "test": "navigation",
                "url": url,
                "success": success,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            await asyncio.sleep(2)  # Wait between tests
    
    async def test_analysis(self):
        """Test analyze_viewport_screenshot tool."""
        print("\n" + "="*50)
        print("🧪 TESTING PAGE ANALYSIS")
        print("="*50)
        
        # Navigate to a page with forms first
        await self.tool_handler.execute_tool("navigate_to_url", {
            "url": "https://httpbin.org/forms/post"
        })
        
        print(f"\n📸 Testing viewport analysis...")
        
        result = await self.tool_handler.execute_tool("analyze_viewport_screenshot", {
            "include_description": True,
            "element_types": ["all"],
            "verbose": True
        })
        
        success = result.get("success", False)
        print(f"   ✅ Success: {success}")
        
        if success:
            elements = result.get("elements", [])
            print(f"   🔍 Elements found: {len(elements)}")
            print(f"   📝 Description: {result.get('description', 'N/A')[:100]}...")
            print(f"   📸 Screenshot: {result.get('screenshot_path', 'N/A')}")
            
            # Show element breakdown
            element_types = {}
            for element in elements:
                elem_type = element.get("type", "unknown")
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
            
            print(f"   📊 Element breakdown: {element_types}")
            
            # Show first few elements
            print(f"   🎯 Sample elements:")
            for i, elem in enumerate(elements[:3]):
                print(f"      {i+1}. {elem.get('type')} - '{elem.get('label', 'No label')}' at {elem.get('bbox')}")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown')}")
        
        self.test_results.append({
            "test": "analysis",
            "success": success,
            "elements_found": len(result.get("elements", [])),
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_input_action(self):
        """Test perform_input_action tool."""
        print("\n" + "="*50)
        print("🧪 TESTING INPUT ACTION")
        print("="*50)
        
        # First analyze to find input fields
        analysis = await self.tool_handler.execute_tool("analyze_viewport_screenshot", {
            "element_types": ["input"]
        })
        
        if not analysis.get("success"):
            print("❌ Could not analyze page for input fields")
            return
        
        inputs = [e for e in analysis.get("elements", []) if e["type"] == "input"]
        
        if not inputs:
            print("❌ No input fields found on page")
            return
        
        print(f"📝 Found {len(inputs)} input fields")
        
        # Test inputting text into the first input field
        test_input = inputs[0]
        test_text = "Test Input Text"
        
        print(f"🎯 Testing input into: {test_input.get('label', 'Unknown field')}")
        print(f"📍 Bbox: {test_input['bbox']}")
        print(f"✏️  Text to input: '{test_text}'")
        
        result = await self.tool_handler.execute_tool("perform_input_action", {
            "bbox": test_input["bbox"],
            "text": test_text,
            "verbose": True
        })
        
        success = result.get("success", False)
        print(f"   ✅ Success: {success}")
        
        if success:
            print(f"   📍 Clicked at: {result.get('coordinates', 'N/A')}")
            verification = result.get("input_verification", {})
            if verification:
                print(f"   🔍 Verification:")
                print(f"      Expected: '{verification.get('expected_text', 'N/A')}'")
                print(f"      Actual: '{verification.get('actual_value', 'N/A')}'")
                print(f"      Matches: {verification.get('text_matches', 'N/A')}")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown')}")
        
        self.test_results.append({
            "test": "input_action",
            "field": test_input.get('label', 'Unknown'),
            "text": test_text,
            "success": success,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        await asyncio.sleep(2)  # Wait to see the result
    
    async def test_click_action(self):
        """Test perform_click_action tool."""
        print("\n" + "="*50)
        print("🧪 TESTING CLICK ACTION")
        print("="*50)
        
        # First analyze to find clickable elements
        analysis = await self.tool_handler.execute_tool("analyze_viewport_screenshot", {
            "element_types": ["button", "link"]
        })
        
        if not analysis.get("success"):
            print("❌ Could not analyze page for clickable elements")
            return
        
        clickables = [e for e in analysis.get("elements", []) if e["type"] in ["button", "link"]]
        
        if not clickables:
            print("❌ No clickable elements found on page")
            return
        
        print(f"🖱️  Found {len(clickables)} clickable elements")
        
        # Test clicking the first button or link
        test_element = clickables[0]
        
        print(f"🎯 Testing click on: {test_element.get('label', 'Unknown element')}")
        print(f"📍 Bbox: {test_element['bbox']}")
        print(f"🔘 Type: {test_element['type']}")
        
        # Record current URL before click
        url_before = self.page.url
        print(f"🌐 URL before click: {url_before}")
        
        result = await self.tool_handler.execute_tool("perform_click_action", {
            "bbox": test_element["bbox"],
            "verbose": True
        })
        
        success = result.get("success", False)
        print(f"   ✅ Success: {success}")
        
        if success:
            print(f"   📍 Clicked at: {result.get('coordinates', 'N/A')}")
            url_after = result.get("page_url_after_click", self.page.url)
            print(f"   🌐 URL after click: {url_after}")
            
            if url_before != url_after:
                print(f"   🔄 Navigation detected!")
            else:
                print(f"   📄 No navigation (same page)")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown')}")
        
        self.test_results.append({
            "test": "click_action",
            "element": test_element.get('label', 'Unknown'),
            "element_type": test_element['type'],
            "url_before": url_before,
            "url_after": result.get("page_url_after_click", url_before),
            "success": success,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        await asyncio.sleep(3)  # Wait to see the result
    
    async def test_scroll_action(self):
        """Test perform_scroll_action tool."""
        print("\n" + "="*50)
        print("🧪 TESTING SCROLL ACTION")
        print("="*50)
        
        # Navigate to a longer page first
        await self.tool_handler.execute_tool("navigate_to_url", {
            "url": "https://aijobs.ai"
        })
        
        print(f"📜 Testing scroll action...")
        
        result = await self.tool_handler.execute_tool("perform_scroll_action", {
            "x": 0,
            "y": 500,
            "verbose": True
        })
        
        success = result.get("success", False)
        print(f"   ✅ Success: {success}")
        
        if success:
            print(f"   📍 Scrolled to: {result.get('coordinates', 'N/A')}")
        else:
            print(f"   ❌ Error: {result.get('error', 'Unknown')}")
        
        self.test_results.append({
            "test": "scroll_action",
            "coordinates": result.get("coordinates", [0, 0]),
            "success": success,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
        await asyncio.sleep(2)  # Wait to see the scroll
        
        # Test analyzing after scroll
        print(f"📸 Analyzing page after scroll...")
        post_scroll_analysis = await self.tool_handler.execute_tool("analyze_viewport_screenshot", {
            "element_types": ["button", "link"],
            "verbose": False
        })
        
        if post_scroll_analysis.get("success"):
            new_elements = len(post_scroll_analysis.get("elements", []))
            print(f"   🔍 Elements visible after scroll: {new_elements}")
    
    async def run_all_tests(self):
        """Run all tool action tests."""
        print("🧪 Tool Action Testing Suite")
        print("Testing each web automation tool individually")
        print("="*60)
        
        try:
            await self.setup()
            
            # Run individual tests
            await self.test_navigation()
            await self.test_analysis()
            await self.test_input_action()
            await self.test_click_action()
            await self.test_scroll_action()
            
            # Print summary
            self.print_summary()
            
            # Save results
            self.save_results()
            
        except Exception as e:
            print(f"💥 Test suite failed: {str(e)}")
        finally:
            if self.browser:
                print("\n🔍 Browser will remain open for inspection.")
                print("Close manually when done or press Ctrl+C to exit.")
                try:
                    # Keep browser open for inspection
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\n👋 Closing browser...")
                    await self.browser.close()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.get("success", False))
        
        print(f"✅ Tests Passed: {passed_tests}/{total_tests}")
        print(f"❌ Tests Failed: {total_tests - passed_tests}/{total_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "No tests run")
        
        print(f"\n📋 Individual Test Results:")
        for result in self.test_results:
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            test_name = result["test"].replace("_", " ").title()
            print(f"   • {test_name}: {status}")
            
            # Add specific details
            if result["test"] == "navigation":
                print(f"     URL: {result.get('url', 'N/A')}")
            elif result["test"] == "analysis":
                print(f"     Elements found: {result.get('elements_found', 0)}")
            elif result["test"] == "input_action":
                print(f"     Field: {result.get('field', 'N/A')}")
            elif result["test"] == "click_action":
                print(f"     Element: {result.get('element', 'N/A')}")
                if result.get("url_before") != result.get("url_after"):
                    print(f"     🔄 Navigation occurred")
    
    def save_results(self):
        """Save test results to file."""
        results_file = f"tool_action_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            "test_type": "tool_actions",
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r.get("success", False)),
            "test_results": self.test_results
        }
        
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")

async def main():
    """Run the tool action tests."""
    tester = ToolActionTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())