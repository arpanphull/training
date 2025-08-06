#!/usr/bin/env python3
"""
Test the job discovery process with enhanced navigation following.
"""

import asyncio
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path='.envfile')

from playwright.async_api import async_playwright
from job_page_discovery import discover_all_job_pages
from config import get_openai_client, LLM_API_AVAILABLE


async def test_discovery(url: str):
    """Test the discovery process on a given URL."""
    
    if not LLM_API_AVAILABLE:
        print("❌ Error: NEBIUS_API_KEY not found")
        return
    
    client = get_openai_client()
    if not client:
        print("❌ Error: Could not initialize API client")
        return
    
    print(f"🧪 Testing job discovery on: {url}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Show browser for testing
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        try:
            results = await discover_all_job_pages(
                page,
                url,
                client,
                verbose=True
            )
            
            print("\n" + "=" * 60)
            print("📊 TEST RESULTS")
            print("=" * 60)
            print(f"Total pages explored: {results['total_pages_explored']}")
            print(f"Job pages found: {results['total_job_pages_found']}")
            
            if results['job_pages']:
                print("\n🎯 Job Pages Discovered:")
                for i, job_page in enumerate(results['job_pages'], 1):
                    print(f"\n{i}. {job_page['url']}")
                    print(f"   - Depth: {job_page.get('depth', 'N/A')}")
                    print(f"   - Confidence: {job_page['confidence']:.1%}")
                    print(f"   - Type: {job_page['page_type']}")
                    if job_page.get('job_count'):
                        print(f"   - Jobs: ~{job_page['job_count']}")
            else:
                print("\n⚠️ No job pages found")
            
            # Save results
            import json
            with open('test_results.json', 'w') as f:
                json.dump(results, f, indent=2)
            print("\n💾 Results saved to test_results.json")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await browser.close()


if __name__ == "__main__":
    # Test URL (can be passed as argument)
    if len(sys.argv) < 2:
        print("Usage: python test_discovery.py <website_url>")
        print("Example: python test_discovery.py https://example.com")
        sys.exit(1)
    
    test_url = sys.argv[1]
    
    print("Job Discovery Test - Multi-level Navigation")
    print("-" * 60)
    print("This test will:")
    print("1. Start from the homepage")
    print("2. Click through navigation elements (Jobs, Careers, etc.)")
    print("3. Follow the discovery path to job listing pages")
    print("4. Handle intermediate navigation pages")
    print("-" * 60)
    
    asyncio.run(test_discovery(test_url))