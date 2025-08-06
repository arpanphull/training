#!/usr/bin/env python3
"""
Test job discovery on multiple websites.
"""

import asyncio
import json
from datetime import datetime
from simple_job_discovery import SimpleJobDiscovery
from playwright.async_api import async_playwright
from config import get_openai_client, LLM_API_AVAILABLE

TEST_SITES = [
    "https://www.microsoft.com",
    "https://www.apple.com", 
    "https://www.google.com",
    "https://www.amazon.com",
    "https://www.meta.com",
    "https://www.netflix.com",
    "https://www.spotify.com",
    "https://www.airbnb.com",
    "https://www.uber.com",
    "https://www.shopify.com"
]

async def test_site(page, url, client):
    """Test a single site."""
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    
    discovery = SimpleJobDiscovery(client, verbose=True)
    
    try:
        results = await discovery.discover(page, url, max_depth=3)
        
        # Save individual results
        domain = url.replace('https://', '').replace('http://', '').replace('www.', '').replace('.com', '')
        filename = f"test_results/{domain}_discovery.json"
        
        import os
        os.makedirs("test_results", exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        return {
            'url': url,
            'success': True,
            'job_pages_found': len(results['job_pages']),
            'pages_visited': len(results['visited_urls']),
            'elements_discovered': len(results['discovered_elements']),
            'job_pages': results['job_pages']
        }
        
    except Exception as e:
        print(f"❌ Error testing {url}: {e}")
        return {
            'url': url,
            'success': False,
            'error': str(e)
        }


async def main():
    """Run tests on multiple sites."""
    
    if not LLM_API_AVAILABLE:
        print("❌ Error: NEBIUS_API_KEY not found")
        return
    
    client = get_openai_client()
    
    print("🧪 Testing Job Discovery on Multiple Sites")
    print(f"Testing {len(TEST_SITES)} websites...")
    
    all_results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Run headless for faster testing
        
        for site in TEST_SITES:
            # Create new page for each site
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            result = await test_site(page, site, client)
            all_results.append(result)
            
            await page.close()
        
        await browser.close()
    
    # Print summary
    print("\n" + "="*60)
    print("📊 SUMMARY RESULTS")
    print("="*60)
    
    successful = [r for r in all_results if r.get('success')]
    found_jobs = [r for r in successful if r.get('job_pages_found', 0) > 0]
    
    print(f"\nTotal sites tested: {len(TEST_SITES)}")
    print(f"Successful tests: {len(successful)}")
    print(f"Sites with job pages found: {len(found_jobs)}")
    
    print("\n✅ Sites with job pages found:")
    for result in found_jobs:
        print(f"  - {result['url']}")
        print(f"    • Job pages: {result['job_pages_found']}")
        print(f"    • Pages visited: {result['pages_visited']}")
        print(f"    • Elements clicked: {result['elements_discovered']}")
        for jp in result['job_pages']:
            print(f"    • Found: {jp['url']}")
    
    print("\n❌ Sites without job pages:")
    for result in successful:
        if result.get('job_pages_found', 0) == 0:
            print(f"  - {result['url']} (visited {result['pages_visited']} pages)")
    
    # Save combined results
    with open('test_results/all_sites_summary.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_sites': len(TEST_SITES),
            'successful': len(successful),
            'with_job_pages': len(found_jobs),
            'results': all_results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to test_results/")


if __name__ == "__main__":
    asyncio.run(main())