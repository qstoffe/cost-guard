"""Bounded read-only dependency checks; no source scan or pricing network work."""
import sqlite3
import time

from src.analysis.cache import dependency_signature
from src.config import ConfigError


class DispatchDependencies:
    def __init__(self, configuration, prices, *, clock=time.monotonic):
        self.configuration, self.prices, self.clock = configuration, prices, clock
        self.next_check = 0
        self.config_signature = None
        self.price_signature = None
        self.reference_signature = None
        self.config_status = 'unchecked'

    def check(self, dispatcher, *, baseline=None):
        """False means a verified configuration change needs a fresh host.

        Web preferences remain hot-applicable. Other runtime owners pin their
        configuration, so do not mix newly configured children with old Live.
        Temporary price-cache read failure is not evidence of a price change.
        """
        if self.clock() < self.next_check:
            return True
        self.next_check = self.clock() + 30
        if self.config_signature is None and baseline is not None:
            self.config_signature = dependency_signature({key: value for key, value in baseline.items() if key != 'webSettings'})
        try:
            config = self.configuration()
            signature = dependency_signature({key: value for key, value in config.items() if key != 'webSettings'})
        except (ConfigError, OSError):
            self.config_status = 'configuration_unavailable'
            return True
        if self.config_signature is not None and signature != self.config_signature:
            self.config_status = 'configuration_changed'
            return False
        self.config_signature = signature
        self.config_status = 'verified'
        try:
            catalog = self.prices()
        except (OSError, sqlite3.Error):
            return True
        signature = catalog.analysis_signature if catalog else None
        if self.price_signature is not None and signature != self.price_signature:
            dispatcher.invalidate()
        self.price_signature = signature
        self.reference_signature = getattr(catalog, 'diagnostic_signature', signature)
        return True
