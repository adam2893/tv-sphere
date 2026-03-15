"""
TV Sphere Scrapers Package
Collection of scrapers for various TV streaming sources
"""

from .daddylive import DaddyLiveScraper, scrape_daddylive

__all__ = [
    'DaddyLiveScraper',
    'scrape_daddylive',
]
