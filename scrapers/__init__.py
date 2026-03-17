"""
TV Sphere Scrapers Package
Collection of scrapers for various TV streaming sources
"""

from .daddylive import DaddyLiveScraper, scrape_daddylive
from .thai_tv import ThaiTVScraper, Ch7Scraper, scrape_thai_channels
from .australian_tv import (
    FreeviewScraper, 
    ABCiViewScraper, 
    SBSOnDemandScraper,
    TenPlayScraper,
    scrape_australian_channels
)

__all__ = [
    # DaddyLive
    'DaddyLiveScraper',
    'scrape_daddylive',
    
    # Thai TV
    'ThaiTVScraper',
    'Ch7Scraper',
    'scrape_thai_channels',
    
    # Australian TV
    'FreeviewScraper',
    'ABCiViewScraper',
    'SBSOnDemandScraper',
    'TenPlayScraper',
    'scrape_australian_channels',
]
