"""
Configuration for vision-based web scraping with Qwen2.5-VL-72B
"""

import os
from openai import OpenAI

# Vision model configuration
VISION_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"

# API configuration
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.studio.nebius.ai/v1")

# Check if API is available
LLM_API_AVAILABLE = bool(NEBIUS_API_KEY)

def get_openai_client():
    """Get configured OpenAI client for Nebius/Qwen."""
    if not NEBIUS_API_KEY:
        return None
    
    return OpenAI(
        api_key=NEBIUS_API_KEY,
        base_url=API_BASE_URL
    )