#!/usr/bin/env python3
"""
Real Claude Integration with Web Tools

This script actually calls Claude Sonnet 3.7 via the Anthropic API and lets Claude
autonomously decide which web automation tools to use to complete tasks.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from playwright.async_api import async_playwright
from sonnet_tools_interface import get_tools_for_sonnet, create_tool_handler

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  anthropic package not installed. Run: pip install anthropic")

class ClaudeWebAutomation:
    """Real Claude integration for autonomous web automation."""
    
    def __init__(self, api_key: str = None):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package required. Run: pip install anthropic")
            
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required in environment or as parameter")
            
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.tool_handler = None
        self.browser = None
        self.conversation_history = []
        self.tool_execution_log = []
        
    async def setup_browser(self):
        """Set up browser for tool execution."""
        if not self.browser:
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
    
    async def execute_tool_for_claude(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call from Claude and log the result."""
        if not self.tool_handler:
            await self.setup_browser()
            
        print(f"🔧 Claude requested tool: {tool_name}")
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
            self.tool_execution_log.append(log_entry)
            
            print(f"✅ Tool result: {result.get('success', False)}")
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
            self.tool_execution_log.append(log_entry)
            
            print(f"💥 Tool execution failed: {str(e)}")
            return error_result
    
    async def complete_task_with_claude(self, task_description: str, max_iterations: int = 10) -> Dict[str, Any]:
        """Let Claude autonomously complete a web automation task."""
        
        # Get available tools
        available_tools = get_tools_for_sonnet()
        
        # Initial prompt for Claude
        initial_prompt = f"""You are an AI assistant with access to web automation tools. Complete this task autonomously:

**TASK**: {task_description}

**AVAILABLE TOOLS**: You have access to web automation tools that let you:
- Navigate to URLs
- Analyze webpage content and find interactive elements
- Click buttons and links
- Input text into forms
- Select dropdown options
- Scroll pages

**INSTRUCTIONS**:
1. Break the task down into steps
2. Use the available tools to complete each step
3. Make decisions based on what you find on each page
4. Continue until the task is fully completed
5. Explain your reasoning for each tool call

Start by using the appropriate tools to complete this task. Begin with navigation if you need to visit a website."""

        # Start conversation with Claude
        messages = [{"role": "user", "content": initial_prompt}]
        
        for iteration in range(max_iterations):
            print(f"\n🤖 CLAUDE ITERATION {iteration + 1}/{max_iterations}")
            print("-" * 50)
            
            try:
                # Send message to Claude with tools
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4000,
                    tools=available_tools,
                    messages=messages
                )
                
                # Add Claude's response to conversation
                messages.append({"role": "assistant", "content": response.content})
                
                # Check if Claude wants to use tools
                tool_calls_made = False
                tool_results = []
                
                for content_block in response.content:
                    if content_block.type == "text":
                        print(f"🤖 Claude says: {content_block.text}")
                    
                    elif content_block.type == "tool_use":
                        tool_calls_made = True
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id
                        
                        print(f"\n🔧 Claude wants to use tool: {tool_name}")
                        
                        # Execute the tool
                        tool_result = await self.execute_tool_for_claude(tool_name, tool_input)
                        
                        # Prepare result for Claude
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(tool_result, indent=2)
                        })
                
                # If Claude made tool calls, send the results back
                if tool_calls_made:
                    # Format tool results properly for Claude API
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})
                        print(f"\n📤 Sent tool results back to Claude")
                else:
                    # Claude didn't make any tool calls, task might be complete
                    print(f"\n✅ Claude completed the task (no more tool calls)")
                    break
                    
            except Exception as e:
                print(f"❌ Error in Claude conversation: {str(e)}")
                break
        
        # Task completion verification
        print(f"\n🔍 TASK VERIFICATION")
        print("-" * 50)
        print("Asking Claude to verify if the task has been completed successfully...")
        
        verification_prompt = f"""Please verify if the following task has been completed successfully:

**ORIGINAL TASK**: {task_description}

Look at the current state of the webpage and the actions you've taken. Have you successfully completed all aspects of this task?

Please provide:
1. A clear YES or NO answer about whether the task is complete
2. What you accomplished during this session
3. What (if anything) still needs to be done
4. Any observations about the final state

You can use the analyze_viewport_screenshot tool to check the current page state if needed."""

        try:
            # Add verification prompt to conversation
            messages.append({"role": "user", "content": verification_prompt})
            
            # Get Claude's verification response
            verification_response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                tools=available_tools,
                messages=messages
            )
            
            # Process verification response
            verification_text = ""
            verification_tool_calls = []
            
            for content_block in verification_response.content:
                if content_block.type == "text":
                    verification_text += content_block.text
                    print(f"🤖 Claude's verification: {content_block.text}")
                elif content_block.type == "tool_use":
                    # Claude wants to analyze current state
                    tool_name = content_block.name
                    tool_input = content_block.input
                    tool_use_id = content_block.id
                    
                    print(f"\n🔧 Claude wants to verify using tool: {tool_name}")
                    tool_result = await self.execute_tool_for_claude(tool_name, tool_input)
                    
                    verification_tool_calls.append({
                        "tool_name": tool_name,
                        "result": tool_result
                    })
                    
                    # Send tool result back for final verification
                    tool_result_msg = [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(tool_result, indent=2)
                    }]
                    
                    messages.append({"role": "assistant", "content": verification_response.content})
                    messages.append({"role": "user", "content": tool_result_msg})
                    
                    # Get final verification after tool use
                    final_verification = self.client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        messages=messages
                    )
                    
                    for final_block in final_verification.content:
                        if final_block.type == "text":
                            verification_text += "\n" + final_block.text
                            print(f"🤖 Claude's final verification: {final_block.text}")
            
            # Store verification results
            verification_result = {
                "verification_text": verification_text,
                "verification_tool_calls": verification_tool_calls,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error in task verification: {str(e)}")
            verification_result = {
                "verification_text": f"Verification failed: {str(e)}",
                "verification_tool_calls": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # Convert conversation to serializable format
        serializable_conversation = []
        for msg in messages:
            if msg["role"] == "user":
                if isinstance(msg["content"], str):
                    serializable_conversation.append({"role": "user", "content": msg["content"]})
                elif isinstance(msg["content"], list):
                    # Handle tool results
                    serializable_conversation.append({"role": "user", "content": "Tool results sent"})
            elif msg["role"] == "assistant":
                # Convert Claude's response to text
                text_content = ""
                tool_calls = []
                for block in msg["content"]:
                    if hasattr(block, 'type'):
                        if block.type == "text":
                            text_content += block.text
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "name": block.name,
                                "input": block.input
                            })
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            text_content += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "name": block.get("name"),
                                "input": block.get("input")
                            })
                
                serializable_conversation.append({
                    "role": "assistant",
                    "content": text_content,
                    "tool_calls": tool_calls
                })
        
        # Return summary
        return {
            "task_description": task_description,
            "iterations": iteration + 1,
            "tool_calls": len(self.tool_execution_log),
            "successful_tools": sum(1 for log in self.tool_execution_log if log["success"]),
            "conversation_length": len(messages),
            "task_verification": verification_result,
            "tool_execution_log": self.tool_execution_log,
            "final_conversation": serializable_conversation
        }
    
    async def cleanup(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.tool_handler = None
    
    def keep_browser_open(self):
        """Keep browser open for continued tool usage."""
        # Don't close browser - tools need it to remain open
        pass

# Test tasks for Claude
REAL_TEST_TASKS = [
    "Find product manager jobs in Seattle. Navigate to https://aijobs.ai and search for product manager positions in Seattle.",
    "Go to https://httpbin.org/forms/post and fill out the contact form with sample information, then submit it.",
    "Visit https://example.com and analyze what's on the page, then scroll down to see more content."
]

async def run_real_claude_test():
    """Run a real test with Claude making autonomous decisions."""
    
    if not ANTHROPIC_AVAILABLE:
        print("❌ Cannot run real Claude test - anthropic package not installed")
        print("Run: pip install anthropic")
        return
    
    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment variables")
        print("Please set your Anthropic API key:")
        print("export ANTHROPIC_API_KEY='your-api-key-here'")
        return
    
    print("🤖 Real Claude Web Automation Test")
    print("Claude will autonomously decide which tools to use")
    print("=" * 60)
    
    # Create Claude automation instance
    claude_automation = ClaudeWebAutomation(api_key=api_key)
    
    try:
        # Set up browser
        await claude_automation.setup_browser()
        
        # Let user choose a task
        print("\n📋 Available tasks:")
        for i, task in enumerate(REAL_TEST_TASKS, 1):
            print(f"{i}. {task}")
        
        try:
            choice = input(f"\nChoose a task (1-{len(REAL_TEST_TASKS)}): ").strip()
            task_index = int(choice) - 1
            if task_index < 0 or task_index >= len(REAL_TEST_TASKS):
                raise ValueError("Invalid choice")
        except (ValueError, KeyboardInterrupt):
            print("Using default task...")
            task_index = 0
        
        selected_task = REAL_TEST_TASKS[task_index]
        print(f"\n🎯 Selected task: {selected_task}")
        print("\n🚀 Starting Claude autonomous execution...")
        
        # Let Claude complete the task
        result = await claude_automation.complete_task_with_claude(selected_task)
        
        # Print summary
        print(f"\n📊 EXECUTION SUMMARY:")
        print(f"   • Task: {result['task_description']}")
        print(f"   • Claude iterations: {result['iterations']}")
        print(f"   • Tool calls made: {result['tool_calls']}")
        print(f"   • Successful tools: {result['successful_tools']}")
        print(f"   • Success rate: {(result['successful_tools']/result['tool_calls']*100):.1f}%" if result['tool_calls'] > 0 else "No tools used")
        
        # Print verification summary
        verification = result.get('task_verification', {})
        if verification:
            print(f"\n🔍 TASK VERIFICATION:")
            verification_text = verification.get('verification_text', 'No verification available')
            # Extract YES/NO if present
            if 'YES' in verification_text.upper():
                print(f"   ✅ Status: TASK COMPLETED")
            elif 'NO' in verification_text.upper():
                print(f"   ❌ Status: TASK NOT COMPLETED")
            else:
                print(f"   ❓ Status: UNCLEAR")
            
            print(f"   📝 Claude's assessment: {verification_text[:200]}..." if len(verification_text) > 200 else f"   📝 Claude's assessment: {verification_text}")
        
        # Save detailed results
        results_file = f"claude_real_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")
        
        # Ask if user wants to keep browser open for inspection
        try:
            keep_open = input("\n🔍 Keep browser open for inspection? (y/n): ").strip().lower()
            if keep_open == 'y':
                print("🌐 Browser will remain open. Close manually when done.")
                print("Press Ctrl+C to exit script while keeping browser open.")
                try:
                    # Keep script running but don't close browser
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    print("\n👋 Script ended. Browser remains open.")
                    return
        except KeyboardInterrupt:
            print("\n👋 Script ended.")
        
    finally:
        # Only cleanup if we reach here (user chose to close)
        print("🧹 Closing browser...")
        await claude_automation.cleanup()

async def main():
    """Main entry point."""
    await run_real_claude_test()

if __name__ == "__main__":
    asyncio.run(main())