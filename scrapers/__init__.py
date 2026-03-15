"""
TV Sphere Scrapers Package
Collection of scrapers for various TV streaming sources
"""

from .daddylive import DaddyLiveScraper, scrape_daddylive_events

__all__ = [
    'DaddyLiveScraper',
    'scrape_daddylive_events',
]
