#!/usr/bin/env python3
"""
Claude Sonnet 3.7 Tools Interface for Viewport Analyzer

This file defines the tool schemas that Claude Sonnet 3.7 can use to interact with web pages
through the viewport analyzer. It provides both the tool definitions and the execution functions.
"""

import json
from typing import Dict, List, Any
from playwright.async_api import Page
from viewport_analyzer import (
    analyze_viewport_screenshot,
    perform_click_action,
    perform_input_action,
    perform_select_action,
    perform_scroll_action
)

# Tool definitions for Claude Sonnet 3.7
SONNET_TOOLS = [
    {
        "name": "analyze_viewport_screenshot",
        "description": "Analyze the current webpage viewport using vision AI to identify interactive elements with their bounding boxes and semantic labels. Takes a screenshot and returns descriptions of buttons, inputs, links, and other clickable elements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_url": {
                    "type": "string",
                    "description": "URL of the current page being analyzed (optional, will be auto-detected)"
                },
                "include_description": {
                    "type": "boolean",
                    "description": "Whether to include a text description of the webpage content",
                    "default": True
                },
                "element_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["button", "input", "link", "clickable", "form", "navigation", "all"]
                    },
                    "description": "Types of elements to detect and analyze",
                    "default": ["button", "input", "link", "clickable"]
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Whether to print debug information",
                    "default": False
                }
            },
            "required": []
        }
    },
    {
        "name": "perform_click_action",
        "description": "Click on an interactive element using its bounding box coordinates. Use this to click buttons, links, or any clickable elements identified by the viewport analyzer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Bounding box coordinates [x, y, width, height] of the element to click"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Whether to print debug information",
                    "default": False
                }
            },
            "required": ["bbox"]
        }
    },
    {
        "name": "perform_input_action",
        "description": "Input text into a text field, search box, or other input element using its bounding box coordinates. Automatically focuses the field and clears existing content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Bounding box coordinates [x, y, width, height] of the input element"
                },
                "text": {
                    "type": "string",
                    "description": "Text to input into the field"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Whether to print debug information",
                    "default": False
                }
            },
            "required": ["bbox", "text"]
        }
    },
    {
        "name": "perform_select_action",
        "description": "Select an option from a dropdown menu or select element using its bounding box coordinates. Works with various dropdown implementations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Bounding box coordinates [x, y, width, height] of the dropdown element"
                },
                "option_value": {
                    "type": "string",
                    "description": "Value or text of the option to select from the dropdown"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Whether to print debug information",
                    "default": False
                }
            },
            "required": ["bbox", "option_value"]
        }
    },
    {
        "name": "perform_scroll_action",
        "description": "Scroll the webpage to specific coordinates. Useful for navigating long pages or bringing elements into view.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate to scroll to (horizontal position)"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate to scroll to (vertical position)"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Whether to print debug information",
                    "default": False
                }
            },
            "required": ["x", "y"]
        }
    }
]


class SonnetWebTools:
    """Tool execution handler for Claude Sonnet 3.7"""
    
    def __init__(self, page: Page):
        """Initialize with a Playwright page object."""
        self.page = page
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call from Claude Sonnet 3.7.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool call
            
        Returns:
            Dict containing the tool execution result
        """
        try:
            if tool_name == "analyze_viewport_screenshot":
                return await analyze_viewport_screenshot(
                    page=self.page,
                    page_url=parameters.get("page_url"),
                    include_description=parameters.get("include_description", True),
                    element_types=parameters.get("element_types", ["button", "input", "link", "clickable"]),
                    verbose=parameters.get("verbose", False)
                )
            
            elif tool_name == "perform_click_action":
                return await perform_click_action(
                    page=self.page,
                    bbox=parameters["bbox"],
                    verbose=parameters.get("verbose", False)
                )
            
            elif tool_name == "perform_input_action":
                return await perform_input_action(
                    page=self.page,
                    bbox=parameters["bbox"],
                    text=parameters["text"],
                    verbose=parameters.get("verbose", False)
                )
            
            elif tool_name == "perform_select_action":
                return await perform_select_action(
                    page=self.page,
                    bbox=parameters["bbox"],
                    option_value=parameters["option_value"],
                    verbose=parameters.get("verbose", False)
                )
            
            elif tool_name == "perform_scroll_action":
                return await perform_scroll_action(
                    page=self.page,
                    x=parameters["x"],
                    y=parameters["y"],
                    verbose=parameters.get("verbose", False)
                )
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": [tool["name"] for tool in SONNET_TOOLS]
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "parameters": parameters
            }


def get_tools_for_sonnet() -> List[Dict]:
    """Get the tool definitions formatted for Claude Sonnet 3.7."""
    return SONNET_TOOLS


def create_tool_handler(page: Page) -> SonnetWebTools:
    """Create a tool handler for the given page."""
    return SonnetWebTools(page)


# Example usage with Claude API
async def example_sonnet_integration():
    """Example of how to integrate these tools with Claude Sonnet 3.7 via API."""
    from playwright.async_api import async_playwright
    
    # This is a conceptual example - you would use the actual Claude API
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Create tool handler
        tool_handler = create_tool_handler(page)
        
        # Navigate to a page
        await page.goto("https://example.com")
        await page.wait_for_load_state("networkidle")
        
        # Example tool calls that Claude might make:
        
        # 1. Analyze the viewport
        analysis_result = await tool_handler.execute_tool(
            "analyze_viewport_screenshot",
            {
                "include_description": True,
                "element_types": ["button", "input", "link"],
                "verbose": True
            }
        )
        print("Analysis Result:", json.dumps(analysis_result, indent=2))
        
        # 2. If there are input fields, fill one out
        if analysis_result.get("success") and analysis_result.get("elements"):
            inputs = [e for e in analysis_result["elements"] if e["type"] == "input"]
            if inputs:
                input_result = await tool_handler.execute_tool(
                    "perform_input_action",
                    {
                        "bbox": inputs[0]["bbox"],
                        "text": "test@example.com",
                        "verbose": True
                    }
                )
                print("Input Result:", json.dumps(input_result, indent=2))
        
        # 3. Scroll down to see more content
        scroll_result = await tool_handler.execute_tool(
            "perform_scroll_action",
            {
                "x": 0,
                "y": 500,
                "verbose": True
            }
        )
        print("Scroll Result:", json.dumps(scroll_result, indent=2))
        
        await browser.close()


# Claude API Integration Template
CLAUDE_API_TEMPLATE = '''
import anthropic
from sonnet_tools_interface import get_tools_for_sonnet, create_tool_handler

async def chat_with_claude_and_tools(page, user_message):
    """
    Example of how to use these tools with Claude Sonnet 3.7 via API.
    
    Args:
        page: Playwright page object
        user_message: Message from user to Claude
    """
    
    client = anthropic.Anthropic(api_key="your-api-key")
    tool_handler = create_tool_handler(page)
    
    # Send message to Claude with tools available
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        tools=get_tools_for_sonnet(),
        messages=[
            {
                "role": "user", 
                "content": user_message
            }
        ]
    )
    
    # Handle tool calls if Claude wants to use them
    if response.stop_reason == "tool_use":
        tool_results = []
        
        for tool_call in response.content:
            if tool_call.type == "tool_use":
                # Execute the tool
                result = await tool_handler.execute_tool(
                    tool_call.name,
                    tool_call.input
                )
                
                tool_results.append({
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(result)
                })
        
        # Send tool results back to Claude
        follow_up_response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            tools=get_tools_for_sonnet(),
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results}
            ]
        )
        
        return follow_up_response.content[0].text
    
    return response.content[0].text
'''

if __name__ == "__main__":
    # Print tool definitions for reference
    print("=== CLAUDE SONNET 3.7 TOOL DEFINITIONS ===")
    print(json.dumps(get_tools_for_sonnet(), indent=2))
    
    print("\n=== CLAUDE API INTEGRATION TEMPLATE ===")
    print(CLAUDE_API_TEMPLATE)