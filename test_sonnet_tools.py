#!/usr/bin/env python3
"""
Test Script for Claude Sonnet Web Tools Integration

This script demonstrates how Claude Sonnet 3.7 can use the viewport analyzer tools
to complete various web automation tasks. It includes multiple test scenarios and
shows how to integrate with the Claude API.
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright
from sonnet_tools_interface import get_tools_for_sonnet, create_tool_handler

# Test scenarios that Sonnet can complete
TEST_SCENARIOS = [
    {
        "name": "Navigation and Search",
        "description": "Navigate a website and perform search",
        "url": "https://aijobs.ai",
        "tasks": [
            "Break the following task into subtasks: find product manager jobs in seattle and use the tools to gather more information by capturing site structure using screenshots and take action",
        ]
    }
]

class SonnetTestRunner:
    """Test runner that simulates Claude Sonnet using the web tools."""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.test_results = []
        
    async def run_all_tests(self):
        """Run all test scenarios."""
        print("🚀 Starting Claude Sonnet Web Tools Test Suite")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,  # Set to True for headless testing
                args=['--disable-blink-features=AutomationControlled']
            )
            
            for i, scenario in enumerate(TEST_SCENARIOS, 1):
                print(f"\n📋 Test {i}/{len(TEST_SCENARIOS)}: {scenario['name']}")
                print(f"📄 Description: {scenario['description']}")
                print(f"🌐 URL: {scenario['url']}")
                print("-" * 40)
                
                try:
                    result = await self._run_scenario(browser, scenario)
                    self.test_results.append(result)
                    
                    if result["success"]:
                        print(f"✅ Test {i} PASSED")
                    else:
                        print(f"❌ Test {i} FAILED: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"💥 Test {i} CRASHED: {str(e)}")
                    self.test_results.append({
                        "scenario": scenario["name"],
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Wait between tests
                await asyncio.sleep(2)
            
            await browser.close()
            
        # Print final summary
        self._print_summary()
        
    async def _run_scenario(self, browser, scenario):
        """Run a single test scenario."""
        page = await browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        tool_handler = create_tool_handler(page)
        scenario_result = {
            "scenario": scenario["name"],
            "url": scenario["url"],
            "success": False,
            "tasks_completed": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Navigate to the test URL
            print(f"🔗 Navigating to {scenario['url']}")
            await page.goto(scenario["url"], wait_until="networkidle", timeout=3000)
            await page.wait_for_timeout(2000)
            
            if scenario["name"] == "Navigation and Search":
                await self._test_navigation_search(tool_handler, scenario_result)
                
            
            
            scenario_result["success"] = len(scenario_result["errors"]) == 0
            
        except Exception as e:
            scenario_result["errors"].append(f"Scenario execution failed: {str(e)}")
            
        finally:
            await page.close()
            
        return scenario_result
    
    async def _test_basic_analysis(self, tool_handler, result):
        """Test basic webpage analysis capabilities."""
        print("🔍 Analyzing webpage structure...")
        
        # Analyze viewport
        analysis = await tool_handler.execute_tool(
            "analyze_viewport_screenshot",
            {
                "include_description": True,
                "element_types": ["all"],
                "verbose": self.verbose
            }
        )
        
        if analysis.get("success"):
            elements = analysis.get("elements", [])
            result["tasks_completed"].append(f"Found {len(elements)} interactive elements")
            
            # Categorize elements
            element_types = {}
            for element in elements:
                elem_type = element.get("type", "unknown")
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
            
            result["tasks_completed"].append(f"Element breakdown: {element_types}")
            
            if analysis.get("description"):
                result["tasks_completed"].append(f"Page description captured: {len(analysis['description'])} chars")
                
        else:
            result["errors"].append(f"Analysis failed: {analysis.get('error', 'Unknown error')}")
    
    async def _test_form_filling(self, tool_handler, result):
        """Test form filling automation."""
        print("📝 Testing form filling automation...")
        
        # First analyze the page
        analysis = await tool_handler.execute_tool(
            "analyze_viewport_screenshot",
            {"element_types": ["input", "button"], "verbose": self.verbose}
        )
        
        if not analysis.get("success"):
            result["errors"].append("Failed to analyze form")
            return
            
        elements = analysis.get("elements", [])
        inputs = [e for e in elements if e["type"] == "input"]
        buttons = [e for e in elements if e["type"] == "button"]
        
        result["tasks_completed"].append(f"Found {len(inputs)} input fields and {len(buttons)} buttons")
        
        # Fill form fields based on their semantic roles or labels
        form_data = {
            "custname": "John Doe",
            "custtel": "555-123-4567", 
            "custemail": "john.doe@example.com",
            "size": "medium",
            "comments": "This is a test comment from Claude Sonnet automation."
        }
        
        for input_elem in inputs:
            label = input_elem.get("label", "").lower()
            semantic_role = input_elem.get("semantic_role", "").lower()
            
            # Determine what to fill based on label/role
            text_to_fill = None
            if any(word in label + semantic_role for word in ["name", "custname"]):
                text_to_fill = form_data["custname"]
            elif any(word in label + semantic_role for word in ["email", "custemail"]):
                text_to_fill = form_data["custemail"]
            elif any(word in label + semantic_role for word in ["phone", "tel", "custtel"]):
                text_to_fill = form_data["custtel"]
            elif any(word in label + semantic_role for word in ["comment", "message"]):
                text_to_fill = form_data["comments"]
            
            if text_to_fill:
                fill_result = await tool_handler.execute_tool(
                    "perform_input_action",
                    {
                        "bbox": input_elem["bbox"],
                        "text": text_to_fill,
                        "verbose": self.verbose
                    }
                )
                
                if fill_result.get("success"):
                    result["tasks_completed"].append(f"Filled field: {input_elem.get('label', 'Unknown')}")
                else:
                    result["errors"].append(f"Failed to fill field: {fill_result.get('error')}")
                
                await asyncio.sleep(1)  # Wait between actions
        
        # Try to submit the form
        submit_buttons = [b for b in buttons if "submit" in b.get("label", "").lower()]
        if submit_buttons:
            click_result = await tool_handler.execute_tool(
                "perform_click_action",
                {
                    "bbox": submit_buttons[0]["bbox"],
                    "verbose": self.verbose
                }
            )
            
            if click_result.get("success"):
                result["tasks_completed"].append("Form submitted successfully")
            else:
                result["errors"].append(f"Failed to submit form: {click_result.get('error')}")
    
    async def _test_navigation_search(self, tool_handler, result):
        """Test navigation and search functionality."""
        print("🧭 Testing navigation and search...")
        
        # Analyze the page
        analysis = await tool_handler.execute_tool(
            "analyze_viewport_screenshot",
            {"element_types": ["all"], "verbose": self.verbose}
        )
        
        if analysis.get("success"):
            elements = analysis.get("elements", [])
            result["tasks_completed"].append(f"Analyzed page with {len(elements)} elements")
            
            # Look for search elements
            search_elements = [
                e for e in elements 
                if "search" in e.get("label", "").lower() or "search" in e.get("semantic_role", "").lower()
            ]
            
            if search_elements:
                result["tasks_completed"].append(f"Found {len(search_elements)} search-related elements")
            else:
                result["tasks_completed"].append("No search functionality detected")
            
            # Test scrolling
            scroll_result = await tool_handler.execute_tool(
                "perform_scroll_action",
                {"x": 0, "y": 500, "verbose": self.verbose}
            )
            
            if scroll_result.get("success"):
                result["tasks_completed"].append("Successfully scrolled page")
                
                # Analyze after scroll
                post_scroll_analysis = await tool_handler.execute_tool(
                    "analyze_viewport_screenshot",
                    {"element_types": ["link"], "verbose": self.verbose}
                )
                
                if post_scroll_analysis.get("success"):
                    new_elements = post_scroll_analysis.get("elements", [])
                    result["tasks_completed"].append(f"Found {len(new_elements)} links after scrolling")
            else:
                result["errors"].append(f"Scroll failed: {scroll_result.get('error')}")
        else:
            result["errors"].append("Failed to analyze navigation page")
    
    async def _test_ecommerce_simulation(self, tool_handler, result):
        """Test e-commerce website interaction."""
        print("🛒 Testing e-commerce simulation...")
        
        # Analyze homepage
        analysis = await tool_handler.execute_tool(
            "analyze_viewport_screenshot",
            {"element_types": ["input", "button", "link"], "verbose": self.verbose}
        )
        
        if not analysis.get("success"):
            result["errors"].append("Failed to analyze e-commerce homepage")
            return
            
        elements = analysis.get("elements", [])
        result["tasks_completed"].append(f"Analyzed homepage with {len(elements)} interactive elements")
        
        # Look for search box
        search_inputs = [
            e for e in elements 
            if e["type"] == "input" and "search" in e.get("label", "").lower()
        ]
        
        if search_inputs:
            # Perform search
            search_result = await tool_handler.execute_tool(
                "perform_input_action",
                {
                    "bbox": search_inputs[0]["bbox"],
                    "text": "laptop",
                    "verbose": self.verbose
                }
            )
            
            if search_result.get("success"):
                result["tasks_completed"].append("Successfully entered search term")
                
                # Look for search button
                search_buttons = [
                    e for e in elements 
                    if e["type"] == "button" and "search" in e.get("label", "").lower()
                ]
                
                if search_buttons:
                    click_result = await tool_handler.execute_tool(
                        "perform_click_action",
                        {
                            "bbox": search_buttons[0]["bbox"],
                            "verbose": self.verbose
                        }
                    )
                    
                    if click_result.get("success"):
                        result["tasks_completed"].append("Successfully clicked search button")
                        await asyncio.sleep(3)  # Wait for results to load
                        
                        # Scroll through results
                        scroll_result = await tool_handler.execute_tool(
                            "perform_scroll_action",
                            {"x": 0, "y": 800, "verbose": self.verbose}
                        )
                        
                        if scroll_result.get("success"):
                            result["tasks_completed"].append("Scrolled through search results")
                    else:
                        result["errors"].append("Failed to click search button")
            else:
                result["errors"].append("Failed to enter search term")
        else:
            result["tasks_completed"].append("No search functionality found on homepage")
    
    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r.get("success", False))
        total = len(self.test_results)
        
        print(f"✅ Tests Passed: {passed}/{total}")
        print(f"❌ Tests Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {(passed/total*100):.1f}%" if total > 0 else "No tests run")
        
        print("\n📋 Detailed Results:")
        for i, result in enumerate(self.test_results, 1):
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            print(f"\n{i}. {result['scenario']} - {status}")
            
            if result.get("tasks_completed"):
                print("   Tasks completed:")
                for task in result["tasks_completed"]:
                    print(f"     • {task}")
            
            if result.get("errors"):
                print("   Errors:")
                for error in result["errors"]:
                    print(f"     ⚠️  {error}")
        
        # Save detailed results
        results_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": total,
                    "passed": passed,
                    "failed": total - passed,
                    "success_rate": (passed/total*100) if total > 0 else 0
                },
                "detailed_results": self.test_results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")


async def main():
    """Run the test suite."""
    print("🤖 Claude Sonnet Web Tools Test Suite")
    print("This script demonstrates how Claude Sonnet can use web automation tools")
    print("to complete various tasks on different websites.\n")
    
    # Show available tools
    tools = get_tools_for_sonnet()
    print("🔧 Available Tools:")
    for tool in tools:
        print(f"   • {tool['name']}: {tool['description']}")
    
    print(f"\n📋 Test Scenarios: {len(TEST_SCENARIOS)}")
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"   {i}. {scenario['name']}")
    
    print("\n" + "=" * 60)
    
    # Run tests
    runner = SonnetTestRunner(verbose=True)
    await runner.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())