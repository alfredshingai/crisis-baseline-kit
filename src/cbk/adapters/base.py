"""Adapter interface: one module per public data source.

An adapter is responsible for fetching a layer, normalizing it into the
kit's canonical form, and reporting full provenance (license, source URL,
version, retrieval time). The pipeline composes adapter outputs into the
final bundle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass
class BuildContext:
    """Paths and profile handed to every adapter during a build."""

    profile: Any                  # cbk.profile.Profile
    bundle_dir: Path              # final bundle root
    raw_dir: Path                 # raw downloads (kept inside the bundle)
    data_dir: Path                # normalized outputs


@dataclass
class LayerResult:
    """What an adapter produced, plus everything needed for provenance."""

    layer: str                    # canonical layer name, e.g. "admin_boundaries"
    adapter: str                  # adapter name
    kind: str                     # "vector" | "raster"
    license: str
    attribution: str
    source_urls: list[str] = field(default_factory=list)
    source_version: str | None = None
    retrieved_at: str | None = None       # ISO-8601 UTC timestamp
    outputs: dict[str, Path] = field(default_factory=dict)  # normalized outputs by name
    raw: list[Path] = field(default_factory=list)           # original files, kept for reuse
    extra: dict[str, Any] = field(default_factory=dict)     # stats/metadata for the manifest


class Adapter(ABC):
    """Base class for source adapters. Subclasses set `name`/`description`."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, ctx: BuildContext, params: Mapping[str, Any]) -> LayerResult:
        """Fetch + normalize the layer described by `params`."""
