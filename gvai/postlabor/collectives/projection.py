from __future__ import annotations

from dataclasses import dataclass
from typing import List

from gvai.postlabor.collectives.schema import (
    CollectiveCost,
    CollectiveMember,
    CollectiveModel,
)
from gvai.postlabor.collectives.comparison import (
    compare_structures,
)


@dataclass(frozen=True)
class CollectiveProjectionYear:
    year: int

    gross_member_revenue: float

    traditional_fees: float

    cooperative_revenue: float
    operating_costs: float

    reserve_added: float
    reinvestment_added: float
    patronage_returned: float

    effective_member_cost: float
    member_savings: float

    cumulative_traditional_fees: float
    cumulative_member_savings: float
    cumulative_reserves: float
    cumulative_reinvestment: float
    cumulative_patronage: float
    cumulative_collective_capital: float


@dataclass(frozen=True)
class CollectiveProjectionResult:
    years: int

    revenue_growth_rate: float
    operating_cost_growth_rate: float
    traditional_fee_rate: float

    annual_results: List[CollectiveProjectionYear]

    total_traditional_fees: float
    total_cooperative_revenue: float
    total_member_savings: float

    total_patronage_returned: float
    total_reserves: float
    total_reinvestment: float
    total_collective_capital: float


def project_collective(
    *,
    model: CollectiveModel,
    traditional_fee_rate: float,
    years: int,
    revenue_growth_rate: float = 0.0,
    operating_cost_growth_rate: float = 0.0,
) -> CollectiveProjectionResult:
    """
    Multi-year projection comparing traditional fee leakage
    against an owned collective structure.

    v0.1 assumptions:
    - member revenue grows at one shared annual rate
    - operating costs grow at one shared annual rate
    - reserve and reinvestment balances are accumulated
      without investment returns
    - member count remains constant
    """

    years = max(1, years)

    cumulative_traditional_fees = 0.0
    cumulative_member_savings = 0.0
    cumulative_reserves = 0.0
    cumulative_reinvestment = 0.0
    cumulative_patronage = 0.0

    total_cooperative_revenue = 0.0

    annual_results = []

    for year in range(1, years + 1):
        revenue_multiplier = (
            1.0 + revenue_growth_rate
        ) ** (year - 1)

        cost_multiplier = (
            1.0 + operating_cost_growth_rate
        ) ** (year - 1)

        year_members = [
            CollectiveMember(
                name=member.name,
                member_type=member.member_type,
                annual_gross_revenue=(
                    member.annual_gross_revenue
                    * revenue_multiplier
                ),
                annual_direct_costs=(
                    member.annual_direct_costs
                    * revenue_multiplier
                ),
                ownership_share=member.ownership_share,
                patronage_weight=member.patronage_weight,
            )
            for member in model.members
        ]

        year_costs = [
            CollectiveCost(
                name=cost.name,
                annual_cost=(
                    cost.annual_cost
                    * cost_multiplier
                ),
                category=cost.category,
            )
            for cost in model.operating_costs
        ]

        year_model = CollectiveModel(
            name=model.name,
            members=year_members,
            revenue_share_rate=model.revenue_share_rate,
            operating_costs=year_costs,
            reserve_rate=model.reserve_rate,
            reinvestment_rate=model.reinvestment_rate,
            patronage_distribution_rate=(
                model.patronage_distribution_rate
            ),
        )

        comparison = compare_structures(
            model=year_model,
            traditional_fee_rate=traditional_fee_rate,
        )

        cumulative_traditional_fees += (
            comparison.traditional_total_fees
        )

        cumulative_member_savings += (
            comparison.annual_member_savings
        )

        cumulative_reserves += (
            comparison.cooperative_reserves
        )

        cumulative_reinvestment += (
            comparison.cooperative_reinvestment
        )

        cumulative_patronage += (
            comparison.cooperative_patronage
        )

        total_cooperative_revenue += (
            comparison.cooperative_total_revenue
        )

        cumulative_collective_capital = (
            cumulative_reserves
            + cumulative_reinvestment
        )

        annual_results.append(
            CollectiveProjectionYear(
                year=year,
                gross_member_revenue=round(
                    comparison.total_gross_revenue,
                    2,
                ),
                traditional_fees=round(
                    comparison.traditional_total_fees,
                    2,
                ),
                cooperative_revenue=round(
                    comparison.cooperative_total_revenue,
                    2,
                ),
                operating_costs=round(
                    comparison.cooperative_operating_costs,
                    2,
                ),
                reserve_added=round(
                    comparison.cooperative_reserves,
                    2,
                ),
                reinvestment_added=round(
                    comparison.cooperative_reinvestment,
                    2,
                ),
                patronage_returned=round(
                    comparison.cooperative_patronage,
                    2,
                ),
                effective_member_cost=round(
                    comparison.cooperative_effective_member_cost,
                    2,
                ),
                member_savings=round(
                    comparison.annual_member_savings,
                    2,
                ),
                cumulative_traditional_fees=round(
                    cumulative_traditional_fees,
                    2,
                ),
                cumulative_member_savings=round(
                    cumulative_member_savings,
                    2,
                ),
                cumulative_reserves=round(
                    cumulative_reserves,
                    2,
                ),
                cumulative_reinvestment=round(
                    cumulative_reinvestment,
                    2,
                ),
                cumulative_patronage=round(
                    cumulative_patronage,
                    2,
                ),
                cumulative_collective_capital=round(
                    cumulative_collective_capital,
                    2,
                ),
            )
        )

    return CollectiveProjectionResult(
        years=years,
        revenue_growth_rate=revenue_growth_rate,
        operating_cost_growth_rate=(
            operating_cost_growth_rate
        ),
        traditional_fee_rate=traditional_fee_rate,
        annual_results=annual_results,
        total_traditional_fees=round(
            cumulative_traditional_fees,
            2,
        ),
        total_cooperative_revenue=round(
            total_cooperative_revenue,
            2,
        ),
        total_member_savings=round(
            cumulative_member_savings,
            2,
        ),
        total_patronage_returned=round(
            cumulative_patronage,
            2,
        ),
        total_reserves=round(
            cumulative_reserves,
            2,
        ),
        total_reinvestment=round(
            cumulative_reinvestment,
            2,
        ),
        total_collective_capital=round(
            cumulative_reserves
            + cumulative_reinvestment,
            2,
        ),
    )
