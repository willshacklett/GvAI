from __future__ import annotations

from gvai.postlabor.collectives.schema import (
    CollectiveMemberOutcome,
    CollectiveModel,
    CollectiveSimulationResult,
)


def simulate_collective(
    model: CollectiveModel,
) -> CollectiveSimulationResult:
    """
    Transparent v0.1 collective economics model.

    The collective receives a percentage of member gross revenue,
    pays shared operating expenses, reserves/reinvests capital,
    and distributes remaining surplus according to member patronage.

    No industry-specific assumptions are embedded here.
    """

    gross_member_revenue = sum(
        max(0.0, member.annual_gross_revenue)
        for member in model.members
    )

    collective_revenue = (
        gross_member_revenue
        * max(0.0, model.revenue_share_rate)
    )

    operating_costs = sum(
        max(0.0, cost.annual_cost)
        for cost in model.operating_costs
    )

    surplus_before_allocations = max(
        0.0,
        collective_revenue - operating_costs,
    )

    reserve_allocation = (
        surplus_before_allocations
        * max(0.0, model.reserve_rate)
    )

    reinvestment_allocation = (
        surplus_before_allocations
        * max(0.0, model.reinvestment_rate)
    )

    remaining_surplus = max(
        0.0,
        surplus_before_allocations
        - reserve_allocation
        - reinvestment_allocation,
    )

    distributable_surplus = (
        remaining_surplus
        * max(
            0.0,
            min(
                1.0,
                model.patronage_distribution_rate,
            ),
        )
    )

    weights = []

    for member in model.members:
        weight = (
            member.patronage_weight
            if member.patronage_weight is not None
            else member.annual_gross_revenue
        )

        weights.append(
            max(0.0, weight)
        )

    total_weight = sum(weights)

    outcomes = []

    for member, weight in zip(
        model.members,
        weights,
    ):
        economic_share = (
            weight / total_weight
            if total_weight > 0
            else 0.0
        )

        patronage_distribution = (
            distributable_surplus
            * economic_share
        )

        gross_collective_charge = (
            member.annual_gross_revenue
            * model.revenue_share_rate
        )

        effective_collective_cost = max(
            0.0,
            gross_collective_charge
            - patronage_distribution,
        )

        effective_rate = (
            effective_collective_cost
            / member.annual_gross_revenue
            if member.annual_gross_revenue > 0
            else 0.0
        )

        outcomes.append(
            CollectiveMemberOutcome(
                name=member.name,
                contributed_revenue=(
                    member.annual_gross_revenue
                ),
                economic_share=round(
                    economic_share,
                    6,
                ),
                patronage_distribution=round(
                    patronage_distribution,
                    2,
                ),
                effective_collective_cost=round(
                    effective_collective_cost,
                    2,
                ),
                effective_rate_after_patronage=round(
                    effective_rate,
                    6,
                ),
            )
        )

    return CollectiveSimulationResult(
        gross_member_revenue=round(
            gross_member_revenue,
            2,
        ),
        collective_revenue=round(
            collective_revenue,
            2,
        ),
        operating_costs=round(
            operating_costs,
            2,
        ),
        reserve_allocation=round(
            reserve_allocation,
            2,
        ),
        reinvestment_allocation=round(
            reinvestment_allocation,
            2,
        ),
        distributable_surplus=round(
            distributable_surplus,
            2,
        ),
        member_outcomes=outcomes,
        collective_surplus_before_distribution=round(
            surplus_before_allocations,
            2,
        ),
    )
