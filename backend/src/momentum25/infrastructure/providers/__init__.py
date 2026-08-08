"""Market-data provider adapters (selected via ``settings.data_provider``)."""

from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

__all__ = ["BhavcopyProvider"]
