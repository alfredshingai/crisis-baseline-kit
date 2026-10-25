"""Adapter registry. Add a source by adding a module and importing it here."""

from __future__ import annotations

from .base import Adapter, BuildContext, LayerResult
from .codab import CodabAdapter
from .healthsites import HealthsitesAdapter
from .roads import RoadsAdapter
from .worldpop import WorldPopAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    cls.name: cls
    for cls in (CodabAdapter, WorldPopAdapter, HealthsitesAdapter, RoadsAdapter)
}
