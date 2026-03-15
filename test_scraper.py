#!/usr/bin/env python3
"""
Test Script for TV Sphere Scrapers
Run this to test the scrapers and see what data they extract
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from bs4 import BeautifulSoup
    import httpx
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install beautifulsoup4 httpx")
    sys.exit(1)


async def test_daddylive_scraper():
    """Test the DaddyLive scraper."""
    print("=" * 70)
    print("📺 TESTING DADDYLIVE SCRAPER")
    print("=" * 70)
    
    from scrapers.daddylive import DaddyLiveScraper
    
    scraper = DaddyLiveScraper()
    await scraper.initialize()
    
    try:
        # Test 1: Get schedule
        print("\n📅 Test 1: Fetching Schedule Page...")
        print("-" * 40)
        
        events = await scraper.get_events()
        
        if events:
            print(f"✅ Found {len(events)} events!\n")
            
            # Group by category
            by_category = {}
            for event in events:
                cat = event['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(event)
            
            # Display results
            for category, cat_events in sorted(by_category.items()):
                print(f"\n🏆 {category} ({len(cat_events)} events):")
                print("-" * 40)
                for event in cat_events[:5]:
                    print(f"   ⏰ [{event['time']}] {event['title']}")
                if len(cat_events) > 5:
                    print(f"   ... and {len(cat_events) - 5} more")
        else:
            print("⚠️ No events found. The site structure may have changed.")
        
        # Test 2: Get homepage links
        print("\n" + "=" * 70)
        print("🏠 Test 2: Checking Homepage Links...")
        print("-" * 40)
        
        channels = await scraper.get_channels_from_homepage()
        
        if channels:
            print(f"✅ Found {len(channels)} links:\n")
            for ch in channels[:10]:
                print(f"   📌 {ch['name']}")
                print(f"      URL: {ch['url']}")
        else:
            print("⚠️ No links found on homepage.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()
    
    print("\n" + "=" * 70)


async def test_raw_html():
    """Test raw HTML fetching to understand the structure."""
    print("=" * 70)
    print("🔍 RAW HTML ANALYSIS")
    print("=" * 70)
    
    url = "https://daddylivehd.net/en/daddy-live-schedule"
    
    print(f"\n📡 Fetching: {url}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"
                },
                timeout=30.0
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find content div
            content = soup.find('div', class_='content')
            
            if content:
                print("\n✅ Found content div!")
                
                # Count elements
                bold_count = len(content.find_all('b'))
                div_count = len(content.find_all('div'))
                
                print(f"   - {bold_count} <b> elements")
                print(f"   - {div_count} <div> elements")
                
                # Show first 10 bold texts
                print("\n📝 First 10 bold texts:")
                for i, b in enumerate(content.find_all('b')[:10]):
                    text = b.get_text(strip=True)
                    print(f"   {i+1}. {text}")
            else:
                print("⚠️ Could not find content div")
                
        except Exception as e:
            print(f"❌ Error fetching page: {e}")
    
    print("\n" + "=" * 70)


async def main():
    """Run all tests."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║           TV SPHERE - SCRAPER TEST SUITE                         ║")
    print("║           Educational Web Scraping Demo                          ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    
    # Run tests
    await test_raw_html()
    await test_daddylive_scraper()
    
    print("\n✅ All tests complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
