"""Infrastructure adapters implementing domain ports.

Adapting external systems (NSE Bhavcopy, broker APIs, etc.) to the pure core.
"""

from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

__all__ = ["BhavcopyProvider"]