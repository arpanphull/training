#!/usr/bin/env python3
"""
Claude Autonomous Web Tools Test

This script provides Claude Sonnet with web automation tools and lets Claude
autonomously decide which tools to invoke and when, to complete given tasks.
Claude makes its own decisions about workflow and tool usage.
"""

import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from sonnet_tools_interface import get_tools_for_sonnet, create_tool_handler

# Test tasks for Claude to complete autonomously
TEST_TASKS = [
    {
        "task_id": "job_search_seattle",
        "description": "Find product manager jobs in Seattle.",
        "starting_url": "https://aijobs.ai",
        "success_criteria": [
            "Successfully navigate to the website",
            "Analyze the page structure", 
            "Find and use search functionality",
            "Locate product manager jobs in Seattle",
            "Gather relevant job information"
        ]
    },
    {
        "task_id": "form_interaction",
        "description": "Navigate to httpbin.org/forms/post and fill out the contact form with sample information, then submit it.",
        "starting_url": "https://httpbin.org/forms/post",
        "success_criteria": [
            "Navigate to the form page",
            "Analyze form fields",
            "Fill out all required fields",
            "Submit the form successfully"
        ]
    }
]

class ClaudeToolExecutor:
    """Handles tool execution for Claude's autonomous decisions."""
    
    def __init__(self):
        self.tool_handler = None
        self.browser = None
        self.execution_log = []
        
    async def setup_browser(self):
        """Set up browser for tool execution."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await self.browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        self.tool_handler = create_tool_handler(page)
        return page
    
    async def execute_tool_call(self, tool_name: str, parameters: dict) -> dict:
        """Execute a tool call and log the result."""
        if not self.tool_handler:
            await self.setup_browser()
            
        print(f"🔧 Executing tool: {tool_name}")
        print(f"📝 Parameters: {json.dumps(parameters, indent=2)}")
        
        try:
            result = await self.tool_handler.execute_tool(tool_name, parameters)
            
            # Log the execution
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result,
                "success": result.get("success", False)
            }
            self.execution_log.append(log_entry)
            
            print(f"✅ Result: {result.get('success', False)}")
            if not result.get("success", False):
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "parameters": parameters,
                "result": error_result,
                "success": False
            }
            self.execution_log.append(log_entry)
            
            print(f"💥 Exception: {str(e)}")
            return error_result
    
    async def cleanup(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
    
    def get_execution_summary(self) -> dict:
        """Get summary of all tool executions."""
        total_calls = len(self.execution_log)
        successful_calls = sum(1 for log in self.execution_log if log["success"])
        
        return {
            "total_tool_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "success_rate": (successful_calls / total_calls * 100) if total_calls > 0 else 0,
            "tools_used": list(set(log["tool_name"] for log in self.execution_log)),
            "execution_log": self.execution_log
        }

def create_claude_prompt(task: dict, available_tools: list) -> str:
    """Create a prompt for Claude with task and available tools."""
    
    tools_description = "\n".join([
        f"- {tool['name']}: {tool['description']}" 
        for tool in available_tools
    ])
    
    prompt = f"""You are an AI assistant with access to web automation tools. Your task is to complete the following web automation task by autonomously deciding which tools to use and when.

**TASK**: {task['description']}

**STARTING URL**: {task['starting_url']}

**SUCCESS CRITERIA**:
{chr(10).join(f"- {criteria}" for criteria in task['success_criteria'])}

**AVAILABLE TOOLS**:
{tools_description}

**INSTRUCTIONS**:
1. Use the available tools to complete the task
2. Make autonomous decisions about which tools to call and when
3. Start by navigating to the starting URL
4. Break the task into subtasks and use the tools to complete the task.
5. Take appropriate actions based on what you find
6. Be methodical and explain your reasoning for each tool call
7. Wait for tool calls to complete before making the next tool call.

Begin by calling the appropriate tools to complete this task. You should start with navigating to the URL and then analyzing the page structure."""

    return prompt

async def run_autonomous_test(task: dict):
    """Run a single autonomous test with Claude."""
    print(f"\n{'='*60}")
    print(f"🎯 AUTONOMOUS TEST: {task['task_id']}")
    print(f"📋 Task: {task['description']}")
    print(f"🌐 Starting URL: {task['starting_url']}")
    print(f"{'='*60}")
    
    # Get available tools
    available_tools = get_tools_for_sonnet()
    
    # Create tool executor
    executor = ClaudeToolExecutor()
    
    try:
        # Set up browser
        await executor.setup_browser()
        
        # Create prompt for Claude
        prompt = create_claude_prompt(task, available_tools)
        print(f"\n📝 CLAUDE PROMPT:")
        print("-" * 40)
        print(prompt)
        print("-" * 40)
        
        # In a real implementation, you would send this prompt to Claude API
        # along with the tool definitions and let Claude make autonomous decisions
        
        print(f"\n🤖 CLAUDE WOULD NOW:")
        print("1. Receive this prompt and the tool definitions")
        print("2. Autonomously decide which tools to call")
        print("3. Make tool calls based on its reasoning")
        print("4. Complete the task using its own workflow")
        
        print(f"\n🔧 AVAILABLE TOOLS FOR CLAUDE:")
        for tool in available_tools:
            print(f"   • {tool['name']}")
        
        # Simulate what Claude might do (for demonstration)
        print(f"\n🎭 DEMONSTRATION - Simulating Claude's autonomous decisions:")
        
        # Claude would autonomously decide to start with navigation
        print(f"\n🤖 Claude decides: 'I should start by navigating to {task['starting_url']}'")
        nav_result = await executor.execute_tool_call("navigate_to_url", {
            "url": task["starting_url"]
        })
        
        if nav_result.get("success"):
            # Claude would then decide to analyze the page
            print(f"\n🤖 Claude decides: 'Now I should analyze the page to understand its structure'")
            analysis_result = await executor.execute_tool_call("analyze_viewport_screenshot", {
                "include_description": True,
                "element_types": ["all"]
            })
            
            if analysis_result.get("success"):
                elements = analysis_result.get("elements", [])
                print(f"\n📊 Claude found {len(elements)} interactive elements")
                
                # Claude would analyze the elements and decide next steps
                print(f"\n🤖 Claude analyzes the elements and decides on next actions based on the task...")
                
                # For job search task, Claude might look for search functionality
                if task["task_id"] == "job_search_seattle":
                    search_elements = [e for e in elements if "search" in e.get("label", "").lower()]
                    if search_elements:
                        print(f"🤖 Claude decides: 'I found search elements, I'll use them to search for jobs'")
                        # Claude would continue with its autonomous workflow...
                
                # For form task, Claude might look for form fields
                elif task["task_id"] == "form_interaction":
                    form_elements = [e for e in elements if e["type"] == "input"]
                    if form_elements:
                        print(f"🤖 Claude decides: 'I found {len(form_elements)} form fields, I'll fill them out'")
                        # Claude would continue with its autonomous workflow...
        
        # Get execution summary
        summary = executor.get_execution_summary()
        print(f"\n📊 EXECUTION SUMMARY:")
        print(f"   • Total tool calls: {summary['total_tool_calls']}")
        print(f"   • Successful calls: {summary['successful_calls']}")
        print(f"   • Success rate: {summary['success_rate']:.1f}%")
        print(f"   • Tools used: {', '.join(summary['tools_used'])}")
        
        return summary
        
    finally:
        await executor.cleanup()

async def main():
    """Run autonomous tests for Claude."""
    print("🤖 Claude Autonomous Web Tools Test")
    print("This demonstrates how Claude would autonomously use web tools to complete tasks")
    print("\nNOTE: In a real implementation, Claude would receive the prompt and tool definitions")
    print("and make completely autonomous decisions about which tools to call and when.")
    
    all_results = []
    
    for task in TEST_TASKS:
        try:
            result = await run_autonomous_test(task)
            all_results.append({
                "task_id": task["task_id"],
                "result": result
            })
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            all_results.append({
                "task_id": task["task_id"],
                "error": str(e)
            })
        
        # Wait between tests
        print("\n⏳ Waiting before next test...")
        await asyncio.sleep(3)
    
    # Save results
    results_file = f"claude_autonomous_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "test_type": "claude_autonomous",
            "timestamp": datetime.now().isoformat(),
            "tasks": TEST_TASKS,
            "results": all_results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    print("\n🎯 NEXT STEPS:")
    print("1. Integrate this with actual Claude API")
    print("2. Send the prompts and tool definitions to Claude")
    print("3. Let Claude make real autonomous tool decisions")
    print("4. Observe Claude's actual reasoning and workflow")

if __name__ == "__main__":
    asyncio.run(main())