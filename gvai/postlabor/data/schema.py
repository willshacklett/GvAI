from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DataSource:
    source_id: str
    name: str
    publisher: str | None = None
    dataset: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Geography:
    geo_id: str
    name: str
    level: str = "country"


@dataclass(frozen=True)
class Observation:
    variable_id: str
    geography: Geography
    value: float
    observed_at: str
    source: DataSource
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeographicSnapshot:
    geography: Geography
    as_of: str
    observations: dict[str, Observation] = field(default_factory=dict)

    def add(self, observation: Observation) -> None:
        if observation.geography.geo_id != self.geography.geo_id:
            raise ValueError("Observation geography must match the snapshot.")
        self.observations[observation.variable_id] = observation

    def get(self, variable_id: str) -> Observation | None:
        return self.observations.get(variable_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)