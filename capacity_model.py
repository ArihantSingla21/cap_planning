"""Driver-based capacity planning calculations for contact-center operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapacityInputs:
    total_fte: float
    shrinkage_rate: float  # 0–1, e.g. 0.30 for 30%
    hours_per_fte_week: float
    weekly_contact_volume: float
    avg_handle_time_minutes: float
    target_utilization: float  # 0–1, e.g. 0.85
    max_utilization: float  # SLA-safe ceiling, e.g. 0.85
    target_sla_pct: float  # e.g. 0.80 for 80%
    sla_seconds: int  # e.g. 20 for 80/20


@dataclass(frozen=True)
class CapacityResults:
    gross_weekly_hours: float
    net_weekly_hours: float
    net_fte: float
    required_handle_hours: float
    actual_utilization: float
    required_net_fte: float
    required_gross_fte: float
    staffing_gap_fte: float
    utilization_status: str
    sla_status: str
    recommended_action: str


def _clamp_rate(value: float, name: str) -> float:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1 (got {value})")
    return value


def calculate_capacity(inputs: CapacityInputs) -> CapacityResults:
    """Compute net availability, utilization, and staffing gap from drivers."""
    shrinkage = _clamp_rate(inputs.shrinkage_rate, "shrinkage_rate")
    target_util = _clamp_rate(inputs.target_utilization, "target_utilization")
    max_util = _clamp_rate(inputs.max_utilization, "max_utilization")

    if inputs.total_fte <= 0:
        raise ValueError("total_fte must be positive")
    if inputs.hours_per_fte_week <= 0:
        raise ValueError("hours_per_fte_week must be positive")
    if inputs.weekly_contact_volume < 0:
        raise ValueError("weekly_contact_volume cannot be negative")
    if inputs.avg_handle_time_minutes < 0:
        raise ValueError("avg_handle_time_minutes cannot be negative")

    gross_weekly_hours = inputs.total_fte * inputs.hours_per_fte_week
    net_weekly_hours = gross_weekly_hours * (1 - shrinkage)
    net_fte = inputs.total_fte * (1 - shrinkage)

    required_handle_hours = (
        inputs.weekly_contact_volume * inputs.avg_handle_time_minutes / 60
    )

    actual_utilization = (
        required_handle_hours / net_weekly_hours if net_weekly_hours > 0 else 0.0
    )

    required_net_fte = (
        required_handle_hours / (inputs.hours_per_fte_week * target_util)
        if target_util > 0
        else 0.0
    )
    availability_factor = 1 - shrinkage
    required_gross_fte = (
        required_net_fte / availability_factor if availability_factor > 0 else 0.0
    )
    staffing_gap_fte = required_gross_fte - inputs.total_fte

    if actual_utilization > max_util:
        utilization_status = "Over target — SLA at risk"
    elif actual_utilization > target_util:
        utilization_status = "Above target utilization"
    elif actual_utilization >= target_util * 0.9:
        utilization_status = "Within optimal range"
    else:
        utilization_status = "Under-utilized — capacity surplus"

    # Heuristic SLA check: high utilization erodes service level in Erlang models.
    # Above ~85% occupancy, SLA degradation accelerates for voice workloads.
    sla_util_ceiling = min(max_util, 0.85 + (inputs.target_sla_pct - 0.8) * 0.25)
    if actual_utilization <= sla_util_ceiling:
        sla_status = (
            f"On track for {inputs.target_sla_pct:.0%} in {inputs.sla_seconds}s target"
        )
    elif actual_utilization <= max_util:
        sla_status = "Marginal — monitor closely; SLA may slip"
    else:
        sla_status = "At risk — utilization exceeds SLA-safe ceiling"

    if staffing_gap_fte > 1:
        recommended_action = (
            f"Hire or redeploy ~{staffing_gap_fte:.0f} gross FTE to meet demand "
            f"at {target_util:.0%} utilization without breaching SLA limits."
        )
    elif staffing_gap_fte < -5:
        recommended_action = (
            f"Surplus of ~{abs(staffing_gap_fte):.0f} gross FTE — consider "
            "cross-training, attrition planning, or incremental volume."
        )
    elif actual_utilization > max_util:
        recommended_action = (
            "Reduce shrinkage, increase handle-time efficiency, or add "
            f"~{max(staffing_gap_fte, 0):.0f} FTE to protect SLA."
        )
    else:
        recommended_action = (
            "Current staffing balances utilization and SLA targets. "
            "Re-run when volume or shrinkage drivers change."
        )

    return CapacityResults(
        gross_weekly_hours=gross_weekly_hours,
        net_weekly_hours=net_weekly_hours,
        net_fte=net_fte,
        required_handle_hours=required_handle_hours,
        actual_utilization=actual_utilization,
        required_net_fte=required_net_fte,
        required_gross_fte=required_gross_fte,
        staffing_gap_fte=staffing_gap_fte,
        utilization_status=utilization_status,
        sla_status=sla_status,
        recommended_action=recommended_action,
    )


def scenario_matrix(
    base: CapacityInputs,
    volume_multipliers: list[float],
    shrinkage_rates: list[float],
) -> list[dict]:
    """Build a what-if grid varying volume and shrinkage."""
    rows: list[dict] = []
    for shrinkage in shrinkage_rates:
        for mult in volume_multipliers:
            scenario = CapacityInputs(
                total_fte=base.total_fte,
                shrinkage_rate=shrinkage,
                hours_per_fte_week=base.hours_per_fte_week,
                weekly_contact_volume=base.weekly_contact_volume * mult,
                avg_handle_time_minutes=base.avg_handle_time_minutes,
                target_utilization=base.target_utilization,
                max_utilization=base.max_utilization,
                target_sla_pct=base.target_sla_pct,
                sla_seconds=base.sla_seconds,
            )
            result = calculate_capacity(scenario)
            rows.append(
                {
                    "volume_multiplier": mult,
                    "shrinkage_rate": shrinkage,
                    "weekly_volume": scenario.weekly_contact_volume,
                    "utilization": result.actual_utilization,
                    "required_gross_fte": result.required_gross_fte,
                    "staffing_gap_fte": result.staffing_gap_fte,
                    "sla_ok": result.actual_utilization <= base.max_utilization,
                }
            )
    return rows
