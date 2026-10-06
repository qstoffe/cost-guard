"""Model pricing provider protocol."""
from __future__ import annotations

from typing import Protocol, Sequence

from src.domain import IntegrationHealth, ModelPricing, ProviderCapabilities

from .catalog import PricingCatalog


class PricingProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def probe(self) -> IntegrationHealth: ...

    def get_model_pricing(self) -> Sequence[ModelPricing]: ...

    def get_catalog(self, *, force: bool = False) -> PricingCatalog: ...
