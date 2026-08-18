"""Streamlit app: driver-based capacity planning for contact-center operations."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from capacity_model import CapacityInputs, calculate_capacity, scenario_matrix

st.set_page_config(
    page_title="Capacity Planning",
    page_icon="📊",
    layout="wide",
)

st.title("Driver-Based Capacity Planning")
st.caption(
    "Simulate staffing needs for contact-center operations with shrinkage-adjusted "
    "availability and SLA-safe utilization targets."
)

# --- Sidebar: drivers ---
with st.sidebar:
    st.header("Operation drivers")
    total_fte = st.number_input(
        "Total FTE",
        min_value=1,
        value=200,
        step=5,
        help="Full-time equivalent headcount in the operation.",
    )
    shrinkage_pct = st.slider(
        "Weekly shrinkage (%)",
        min_value=0,
        max_value=60,
        value=30,
        step=1,
        help="Non-productive time: breaks, training, meetings, absenteeism.",
    )
    hours_per_week = st.number_input(
        "Hours per FTE / week",
        min_value=1.0,
        value=40.0,
        step=1.0,
    )

    st.divider()
    st.header("Demand drivers")
    weekly_volume = st.number_input(
        "Weekly contact volume",
        min_value=0,
        value=42000,
        step=1000,
        help="Calls, chats, tickets, or other handled contacts per week.",
    )
    aht_minutes = st.number_input(
        "Average handle time (minutes)",
        min_value=0.1,
        value=6.5,
        step=0.1,
        format="%.1f",
    )

    st.divider()
    st.header("SLA & utilization targets")
    target_sla = st.slider(
        "Target SLA (%)",
        min_value=50,
        max_value=99,
        value=80,
        step=1,
        help="e.g. 80% of contacts answered within threshold.",
    )
    sla_seconds = st.number_input(
        "SLA threshold (seconds)",
        min_value=5,
        value=20,
        step=5,
    )
    target_util_pct = st.slider(
        "Target utilization (%)",
        min_value=50,
        max_value=95,
        value=80,
        step=1,
        help="Ideal occupancy of net available capacity.",
    )
    max_util_pct = st.slider(
        "Max utilization — SLA ceiling (%)",
        min_value=60,
        max_value=98,
        value=85,
        step=1,
        help="Do not exceed this level if SLA must be protected.",
    )

inputs = CapacityInputs(
    total_fte=float(total_fte),
    shrinkage_rate=shrinkage_pct / 100,
    hours_per_fte_week=float(hours_per_week),
    weekly_contact_volume=float(weekly_volume),
    avg_handle_time_minutes=float(aht_minutes),
    target_utilization=target_util_pct / 100,
    max_utilization=max_util_pct / 100,
    target_sla_pct=target_sla / 100,
    sla_seconds=int(sla_seconds),
)

results = calculate_capacity(inputs)

# --- KPI row ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Gross FTE", f"{inputs.total_fte:.0f}")
col2.metric(
    "Net FTE (after shrinkage)",
    f"{results.net_fte:.0f}",
    delta=f"-{shrinkage_pct}% shrinkage",
    delta_color="off",
)
col3.metric(
    "Actual utilization",
    f"{results.actual_utilization:.1%}",
    delta=results.utilization_status,
    delta_color="inverse" if results.actual_utilization > inputs.max_utilization else "normal",
)
col4.metric(
    "Required gross FTE",
    f"{results.required_gross_fte:.0f}",
    delta=f"{results.staffing_gap_fte:+.0f} vs current",
)
col5.metric("Net hours / week", f"{results.net_weekly_hours:,.0f}")

st.info(results.recommended_action)

tab_overview, tab_waterfall, tab_scenarios, tab_formula = st.tabs(
    ["Overview", "Capacity waterfall", "What-if scenarios", "Model logic"]
)

with tab_overview:
    left, right = st.columns(2)

    with left:
        st.subheader("Capacity vs demand")
        capacity_df = pd.DataFrame(
            {
                "Category": [
                    "Gross capacity",
                    "Lost to shrinkage",
                    "Net available",
                    "Workload demand",
                    "Idle / buffer",
                ],
                "Hours": [
                    results.gross_weekly_hours,
                    -results.gross_weekly_hours * inputs.shrinkage_rate,
                    results.net_weekly_hours,
                    -results.required_handle_hours,
                    max(
                        0,
                        results.net_weekly_hours - results.required_handle_hours,
                    ),
                ],
            }
        )
        fig_cap = px.bar(
            capacity_df,
            x="Category",
            y="Hours",
            color="Hours",
            color_continuous_scale=["#ef553b", "#636efa", "#00cc96"],
            title="Weekly hours: gross → net → demand",
        )
        fig_cap.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_cap, use_container_width=True)

    with right:
        st.subheader("Utilization gauge")
        util_pct = results.actual_utilization * 100
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=util_pct,
                delta={"reference": target_util_pct, "suffix": "%"},
                title={"text": "Utilization vs targets"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#636efa"},
                    "steps": [
                        {"range": [0, target_util_pct], "color": "#d4edda"},
                        {
                            "range": [target_util_pct, max_util_pct],
                            "color": "#fff3cd",
                        },
                        {"range": [max_util_pct, 100], "color": "#f8d7da"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": max_util_pct,
                    },
                },
            )
        )
        fig_gauge.update_layout(height=320)
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(f"**SLA status:** {results.sla_status}")

with tab_waterfall:
    st.subheader("Shrinkage-adjusted availability breakdown")

    breakdown = pd.DataFrame(
        {
            "Metric": [
                "Scheduled FTE",
                "Shrinkage loss",
                "Net productive FTE",
                "Required gross FTE (demand)",
                "Staffing gap",
            ],
            "Value": [
                inputs.total_fte,
                -inputs.total_fte * inputs.shrinkage_rate,
                results.net_fte,
                results.required_gross_fte,
                results.staffing_gap_fte,
            ],
            "Unit": ["FTE", "FTE", "FTE", "FTE", "FTE"],
        }
    )
    st.dataframe(
        breakdown.style.format({"Value": "{:,.1f}"}),
        use_container_width=True,
        hide_index=True,
    )

    hours_breakdown = pd.DataFrame(
        {
            "Driver": [
                "Gross hours (FTE × hrs/week)",
                f"Shrinkage ({shrinkage_pct}%)",
                "Net available hours",
                "Handle-time demand",
                "Utilization (demand ÷ net)",
            ],
            "Calculation": [
                f"{inputs.total_fte:.0f} × {inputs.hours_per_fte_week:.0f}",
                f"× (1 − {shrinkage_pct/100:.2f})",
                f"{results.net_weekly_hours:,.0f} hrs",
                f"{weekly_volume:,.0f} × {aht_minutes:.1f} min",
                f"{results.required_handle_hours:,.0f} ÷ {results.net_weekly_hours:,.0f}",
            ],
            "Result": [
                f"{results.gross_weekly_hours:,.0f} hrs",
                f"−{results.gross_weekly_hours * inputs.shrinkage_rate:,.0f} hrs",
                f"{results.net_weekly_hours:,.0f} hrs",
                f"{results.required_handle_hours:,.0f} hrs",
                f"{results.actual_utilization:.1%}",
            ],
        }
    )
    st.dataframe(hours_breakdown, use_container_width=True, hide_index=True)

with tab_scenarios:
    st.subheader("What-if: volume & shrinkage sensitivity")

    volume_range = st.multiselect(
        "Volume multipliers",
        options=[0.8, 0.9, 1.0, 1.1, 1.2, 1.3],
        default=[0.9, 1.0, 1.1, 1.2],
        format_func=lambda x: f"{x:.0%} of base",
    )
    shrinkage_range = st.multiselect(
        "Shrinkage rates to test (%)",
        options=[20, 25, 30, 35, 40],
        default=[25, 30, 35],
        format_func=lambda x: f"{x}%",
    )

    if volume_range and shrinkage_range:
        scenarios = scenario_matrix(
            inputs,
            volume_multipliers=volume_range,
            shrinkage_rates=[s / 100 for s in shrinkage_range],
        )
        scen_df = pd.DataFrame(scenarios)
        scen_df["shrinkage_pct"] = scen_df["shrinkage_rate"].apply(lambda x: f"{x:.0%}")
        scen_df["volume_label"] = scen_df["volume_multiplier"].apply(
            lambda x: f"{x:.0%}"
        )

        heatmap = scen_df.pivot(
            index="shrinkage_pct",
            columns="volume_label",
            values="utilization",
        )
        st.markdown("**Utilization heatmap** (green = within SLA ceiling)")
        st.dataframe(
            heatmap.map(lambda v: f"{v:.1%}"),
            use_container_width=True,
        )

        fig_heat = px.imshow(
            heatmap.values * 100,
            x=heatmap.columns,
            y=heatmap.index,
            color_continuous_scale="RdYlGn_r",
            labels={"color": "Utilization %"},
            title="Utilization by volume × shrinkage",
            aspect="auto",
        )
        fig_heat.update_traces(text=heatmap.values * 100, texttemplate="%{text:.1f}%")
        st.plotly_chart(fig_heat, use_container_width=True)

        scen_df["staffing_gap_fte"] = scen_df["staffing_gap_fte"].round(1)
        st.dataframe(
            scen_df[
                [
                    "volume_multiplier",
                    "shrinkage_rate",
                    "weekly_volume",
                    "utilization",
                    "required_gross_fte",
                    "staffing_gap_fte",
                    "sla_ok",
                ]
            ].rename(
                columns={
                    "volume_multiplier": "Volume mult.",
                    "shrinkage_rate": "Shrinkage",
                    "weekly_volume": "Weekly volume",
                    "utilization": "Utilization",
                    "required_gross_fte": "Req. gross FTE",
                    "staffing_gap_fte": "Gap (FTE)",
                    "sla_ok": "SLA OK?",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_formula:
    st.subheader("Model logic (driver-based)")
    st.markdown(
        """
        This model mirrors a spreadsheet capacity plan driven by operational inputs:

        | Step | Formula |
        |------|---------|
        | **Gross weekly hours** | `FTE × hours per week` |
        | **Net weekly hours** | `Gross hours × (1 − shrinkage)` |
        | **Net FTE** | `FTE × (1 − shrinkage)` |
        | **Handle-time demand** | `Weekly volume × AHT (min) ÷ 60` |
        | **Actual utilization** | `Demand hours ÷ Net available hours` |
        | **Required net FTE** | `Demand ÷ (hours/week × target utilization)` |
        | **Required gross FTE** | `Required net FTE ÷ (1 − shrinkage)` |
        | **Staffing gap** | `Required gross FTE − Current FTE` |

        **Shrinkage (30%)** reflects time agents are scheduled but not handling contacts —
        breaks, coaching, training, meetings, and absenteeism. Only net availability
        counts toward service delivery.

        **Utilization vs SLA:** Industry practice keeps occupancy below ~85% for voice
        workloads to protect service level (e.g. 80/20). Exceeding the max utilization
        ceiling flags SLA risk even when raw capacity appears sufficient.
        """
    )

    export_row = {
        "total_fte": inputs.total_fte,
        "shrinkage_rate": inputs.shrinkage_rate,
        "net_fte": results.net_fte,
        "weekly_volume": inputs.weekly_contact_volume,
        "aht_minutes": inputs.avg_handle_time_minutes,
        "required_handle_hours": results.required_handle_hours,
        "actual_utilization": results.actual_utilization,
        "required_gross_fte": results.required_gross_fte,
        "staffing_gap_fte": results.staffing_gap_fte,
        "target_sla_pct": inputs.target_sla_pct,
        "sla_seconds": inputs.sla_seconds,
    }
    export_df = pd.DataFrame([export_row])
    st.download_button(
        "Download results (CSV)",
        data=export_df.to_csv(index=False),
        file_name="capacity_plan_results.csv",
        mime="text/csv",
    )
