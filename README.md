# Capacity Planning

A driver-based capacity planning tool for contact-center and operations teams. Built with Streamlit, it simulates staffing needs for large FTE operations, accounts for shrinkage when calculating net agent availability, and helps balance utilization rates against SLA targets.

## Features

- **Driver-based staffing model** — Configure FTE, hours per week, contact volume, and average handle time (AHT)
- **Shrinkage-adjusted availability** — Apply a weekly shrinkage rate (default 30%) to derive true net productive capacity
- **Utilization & SLA monitoring** — Compare actual utilization against target and max (SLA-safe) ceilings
- **Staffing gap analysis** — See required gross FTE and the gap vs current headcount
- **What-if scenarios** — Sensitivity heatmap across volume multipliers and shrinkage rates
- **CSV export** — Download model outputs from the Model logic tab

## Quick start

### Prerequisites

- Python 3.9+

### Installation

```bash
cd cap_planning
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run app.py
```

The app opens in your browser (default: http://localhost:8501).

## Project structure

```
cap_planning/
├── app.py              # Streamlit UI
├── capacity_model.py   # Core calculations
├── requirements.txt
└── README.md
```

## Model overview

The model follows a spreadsheet-style capacity plan driven by operational inputs:

| Step | Formula |
|------|---------|
| Gross weekly hours | `FTE × hours per week` |
| Net weekly hours | `Gross hours × (1 − shrinkage)` |
| Net FTE | `FTE × (1 − shrinkage)` |
| Handle-time demand | `Weekly volume × AHT (min) ÷ 60` |
| Actual utilization | `Demand hours ÷ Net available hours` |
| Required net FTE | `Demand ÷ (hours/week × target utilization)` |
| Required gross FTE | `Required net FTE ÷ (1 − shrinkage)` |
| Staffing gap | `Required gross FTE − Current FTE` |

### Shrinkage

Shrinkage represents scheduled time that is not available for handling contacts — breaks, training, coaching, meetings, and absenteeism. A 30% shrinkage rate on 200 FTE yields **140 net productive FTE**.

### Utilization vs SLA

For voice and real-time channels, occupancy above ~85% often degrades service level (e.g. 80% answered in 20 seconds). The app flags when utilization exceeds the configured SLA ceiling and recommends staffing actions.

## Default scenario

Out of the box, the app uses:

| Driver | Default |
|--------|---------|
| Total FTE | 200 |
| Weekly shrinkage | 30% |
| Hours per FTE / week | 40 |
| Weekly contact volume | 42,000 |
| Average handle time | 6.5 min |
| Target SLA | 80% in 20s |
| Target utilization | 80% |
| Max utilization (SLA ceiling) | 85% |

Adjust any value in the sidebar to simulate your operation.

## App tabs

1. **Overview** — Capacity vs demand chart, utilization gauge, SLA status
2. **Capacity waterfall** — FTE and hours breakdown from gross capacity through shrinkage to demand
3. **What-if scenarios** — Utilization heatmap and table for volume × shrinkage combinations
4. **Model logic** — Formula reference and CSV download

## Dependencies

- [Streamlit](https://streamlit.io/) — Web UI
- [Pandas](https://pandas.pydata.org/) — Data handling
- [Plotly](https://plotly.com/python/) — Charts and heatmaps

## License

MIT (or adjust as needed for your organization).
