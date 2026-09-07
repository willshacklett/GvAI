from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class CollectiveMember:
    """
    A person, act, team, business, or other economic participant
    contributing value to a collective structure.
    """

    name: str
    member_type: str

    annual_gross_revenue: float = 0.0
    annual_direct_costs: float = 0.0

    ownership_share: Optional[float] = None
    patronage_weight: Optional[float] = None


@dataclass(frozen=True)
class CollectiveCost:
    name: str
    annual_cost: float
    category: str


@dataclass(frozen=True)
class CollectiveModel:
    """
    Generic collective economic structure.

    This is intentionally not music-specific.
    """

    name: str

    members: List[CollectiveMember]

    revenue_share_rate: float

    operating_costs: List[CollectiveCost] = field(
        default_factory=list
    )

    reserve_rate: float = 0.0
    reinvestment_rate: float = 0.0
    patronage_distribution_rate: float = 1.0


@dataclass(frozen=True)
class CollectiveMemberOutcome:
    name: str

    contributed_revenue: float
    economic_share: float
    patronage_distribution: float

    effective_collective_cost: float
    effective_rate_after_patronage: float


@dataclass(frozen=True)
class CollectiveSimulationResult:
    gross_member_revenue: float

    collective_revenue: float
    operating_costs: float

    reserve_allocation: float
    reinvestment_allocation: float

    distributable_surplus: float

    member_outcomes: List[CollectiveMemberOutcome]

    collective_surplus_before_distribution: float
