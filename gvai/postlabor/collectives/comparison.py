from __future__ import annotations

from dataclasses import dataclass
from typing import List

from gvai.postlabor.collectives.schema import (
    CollectiveModel,
)
from gvai.postlabor.collectives.simulator import (
    simulate_collective,
)


@dataclass(frozen=True)
class MemberStructureComparison:
    name: str

    annual_gross_revenue: float

    traditional_fee: float

    cooperative_gross_fee: float
    patronage_return: float
    cooperative_effective_cost: float

    annual_member_savings: float

    traditional_effective_rate: float
    cooperative_effective_rate: float


@dataclass(frozen=True)
class StructureComparisonResult:
    total_gross_revenue: float

    traditional_total_fees: float

    cooperative_total_revenue: float
    cooperative_operating_costs: float
    cooperative_reserves: float
    cooperative_reinvestment: float
    cooperative_patronage: float

    cooperative_effective_member_cost: float

    annual_member_savings: float

    member_comparisons: List[
        MemberStructureComparison
    ]


def compare_structures(
    *,
    model: CollectiveModel,
    traditional_fee_rate: float,
) -> StructureComparisonResult:
    """
    Compare a conventional percentage-fee structure
    against an owned collective structure.

    The traditional structure assumes the fee leaves
    the member economy.

    The cooperative structure accounts for patronage
    returned to members after shared costs and capital
    allocations.
    """

    traditional_fee_rate = max(
        0.0,
        traditional_fee_rate,
    )

    result = simulate_collective(model)

    traditional_total_fees = (
        result.gross_member_revenue
        * traditional_fee_rate
    )

    member_comparisons = []

    cooperative_effective_member_cost = 0.0

    for member, outcome in zip(
        model.members,
        result.member_outcomes,
    ):
        revenue = max(
            0.0,
            member.annual_gross_revenue,
        )

        traditional_fee = (
            revenue
            * traditional_fee_rate
        )

        cooperative_gross_fee = (
            revenue
            * model.revenue_share_rate
        )

        cooperative_effective_cost = (
            outcome.effective_collective_cost
        )

        cooperative_effective_member_cost += (
            cooperative_effective_cost
        )

        annual_member_savings = (
            traditional_fee
            - cooperative_effective_cost
        )

        traditional_effective_rate = (
            traditional_fee / revenue
            if revenue > 0
            else 0.0
        )

        cooperative_effective_rate = (
            cooperative_effective_cost / revenue
            if revenue > 0
            else 0.0
        )

        member_comparisons.append(
            MemberStructureComparison(
                name=member.name,
                annual_gross_revenue=round(
                    revenue,
                    2,
                ),
                traditional_fee=round(
                    traditional_fee,
                    2,
                ),
                cooperative_gross_fee=round(
                    cooperative_gross_fee,
                    2,
                ),
                patronage_return=round(
                    outcome.patronage_distribution,
                    2,
                ),
                cooperative_effective_cost=round(
                    cooperative_effective_cost,
                    2,
                ),
                annual_member_savings=round(
                    annual_member_savings,
                    2,
                ),
                traditional_effective_rate=round(
                    traditional_effective_rate,
                    6,
                ),
                cooperative_effective_rate=round(
                    cooperative_effective_rate,
                    6,
                ),
            )
        )

    annual_member_savings = (
        traditional_total_fees
        - cooperative_effective_member_cost
    )

    return StructureComparisonResult(
        total_gross_revenue=round(
            result.gross_member_revenue,
            2,
        ),
        traditional_total_fees=round(
            traditional_total_fees,
            2,
        ),
        cooperative_total_revenue=round(
            result.collective_revenue,
            2,
        ),
        cooperative_operating_costs=round(
            result.operating_costs,
            2,
        ),
        cooperative_reserves=round(
            result.reserve_allocation,
            2,
        ),
        cooperative_reinvestment=round(
            result.reinvestment_allocation,
            2,
        ),
        cooperative_patronage=round(
            result.distributable_surplus,
            2,
        ),
        cooperative_effective_member_cost=round(
            cooperative_effective_member_cost,
            2,
        ),
        annual_member_savings=round(
            annual_member_savings,
            2,
        ),
        member_comparisons=member_comparisons,
    )
