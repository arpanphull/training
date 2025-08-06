#!/usr/bin/env python3
"""
Run job page discovery on websites using Qwen2.5-VL-72B vision model.
"""

import asyncio
import json
import os
from dotenv import load_dotenv

# Load environment variables before importing config
load_dotenv(dotenv_path='.envfile')

from playwright.async_api import async_playwright
from job_page_discovery import discover_all_job_pages
from config import get_openai_client, LLM_API_AVAILABLE
import argparse
from datetime import datetime


async def run_discovery(website_url: str, output_file: str = None, headless: bool = True):
    """Run job page discovery on a single website."""
    
    # Check if API is available
    if not LLM_API_AVAILABLE:
        print("❌ Error: NEBIUS_API_KEY not found in environment variables")
        print("Please set: export NEBIUS_API_KEY='your-api-key'")
        return
    
    client = get_openai_client()
    if not client:
        print("❌ Error: Could not initialize API client")
        return
    
    print(f"🔍 Starting job page discovery for: {website_url}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Create page with realistic viewport
        page = await browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        try:
            # Run discovery
            results = await discover_all_job_pages(
                page,
                website_url,
                client,
                verbose=True
            )
            
            # Save results if output file specified
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"\n💾 Results saved to: {output_file}")
                
                # Also save training data with bboxes
                if results.get('discovered_elements'):
                    training_file = output_file.replace('.json', '_training_data.json')
                    training_data = {
                        'url': website_url,
                        'timestamp': datetime.now().isoformat(),
                        'elements': results['discovered_elements'],
                        'total_elements': len(results['discovered_elements'])
                    }
                    with open(training_file, 'w') as f:
                        json.dump(training_data, f, indent=2)
                    print(f"📦 Training data saved to: {training_file}")
            
            # Print summary
            print("\n" + "="*50)
            print("📊 FINAL SUMMARY")
            print("="*50)
            print(f"Website: {website_url}")
            print(f"Pages explored: {results['total_pages_explored']}")
            print(f"Job pages found: {results['total_job_pages_found']}")
            
            if results['job_pages']:
                print("\n🎯 Job Pages Found:")
                for i, page in enumerate(results['job_pages'], 1):
                    print(f"\n  {i}. {page['url']}")
                    print(f"     - Confidence: {page['confidence']:.1%}")
                    print(f"     - Type: {page['page_type']}")
                    if page.get('job_count'):
                        print(f"     - Estimated jobs: {page['job_count']}")
            else:
                print("\n⚠️ No job pages found")
            
            return results
            
        except Exception as e:
            print(f"\n❌ Error during discovery: {e}")
            return None
            
        finally:
            await browser.close()
            print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def run_batch_discovery(websites_file: str, output_dir: str = "job_discovery_results"):
    """Run discovery on multiple websites from a file."""
    
    # Read websites from file
    with open(websites_file, 'r') as f:
        websites = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📋 Found {len(websites)} websites to process")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each website
    all_results = {}
    for i, website in enumerate(websites, 1):
        print(f"\n{'='*60}")
        print(f"Processing {i}/{len(websites)}: {website}")
        print('='*60)
        
        # Generate output filename
        domain = website.replace('https://', '').replace('http://', '').replace('/', '_')
        output_file = os.path.join(output_dir, f"{domain}_jobs.json")
        
        try:
            results = await run_discovery(website, output_file, headless=True)
            all_results[website] = results
        except Exception as e:
            print(f"❌ Failed to process {website}: {e}")
            all_results[website] = {"error": str(e)}
    
    # Save combined results
    combined_file = os.path.join(output_dir, "all_results.json")
    with open(combined_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ Batch processing complete!")
    print(f"📁 Results saved in: {output_dir}")
    
    # Print summary
    successful = sum(1 for r in all_results.values() if r and 'error' not in r)
    total_job_pages = sum(
        len(r.get('job_pages', [])) 
        for r in all_results.values() 
        if r and 'error' not in r
    )
    
    print(f"\n📊 BATCH SUMMARY:")
    print(f"  - Websites processed: {successful}/{len(websites)}")
    print(f"  - Total job pages found: {total_job_pages}")


def main():
    parser = argparse.ArgumentParser(description='Discover job listing pages on websites using vision AI')
    parser.add_argument('url', help='Website URL to analyze (or path to file with URLs for batch mode)')
    parser.add_argument('-o', '--output', help='Output JSON file path')
    parser.add_argument('-b', '--batch', action='store_true', help='Batch mode: process multiple URLs from file')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    
    args = parser.parse_args()
    
    if args.batch:
        # Batch mode
        asyncio.run(run_batch_discovery(args.url, args.output or "job_discovery_results"))
    else:
        # Single website mode
        asyncio.run(run_discovery(args.url, args.output, args.headless))


if __name__ == "__main__":
    import sys
    
    # Example usage without command line args
    if len(sys.argv) == 1:
        print("Job Page Discovery Tool")
        print("-" * 40)
        print("\nUsage examples:")
        print("  python run_job_discovery.py https://example.com")
        print("  python run_job_discovery.py https://example.com -o results.json")
        print("  python run_job_discovery.py websites.txt --batch")
        print("\nRunning demo on a sample website...")
        
        # Demo run
        asyncio.run(run_discovery(
            "https://careers.google.com",
            "google_jobs.json",
            headless=False
        ))
    else:
        main()