# GVAI

## Post-Labor Capitalism Intelligence

**GVAI is a geographic intelligence platform for understanding the economic and human impact of automation, AI, robotics, demographic change, and labor displacement.**

The platform combines regional economic data, workforce composition, automation exposure, housing conditions, demographic pressure, and the God Variable (GV) survivability framework into an interactive global intelligence system.

The goal is simple:

> **Understand what happens to places and people as human labor becomes less necessary — and identify where human labor, investment, infrastructure, and adaptation are still needed.**

---

## The Platform

GVAI is being built around an interactive 3D Earth.

Users can explore the world, select a region, and examine local conditions including:

- Population
- Labor-force size
- Unemployment
- Workforce composition
- Median household income
- Housing values
- Demographic and aging pressure
- Automation exposure
- Employment vulnerability
- Industry concentration
- Regional resilience
- Transition and displacement risk

GVAI is designed to move from **global → national → state/province → county/region → local community** intelligence.

---

## Regional Intelligence

For supported U.S. locations, GVAI can resolve geographic coordinates into real county-level economic and workforce information.

Current regional data includes:

- Population
- Civilian labor force
- Unemployment rate
- Median household income
- Median home value
- Median age
- Broad occupational composition

Current occupational groups include:

- Management, business, science, and arts
- Service occupations
- Sales and office occupations
- Natural resources, construction, and maintenance
- Production, transportation, and material moving

Regional demographic and workforce information is currently sourced from the **U.S. Census Bureau American Community Survey (ACS)**.

Additional labor-market, industry, automation, and international data sources are being integrated.

---

## Post-Labor Intelligence

GVAI is intended to answer questions such as:

### For businesses

- Where is labor becoming difficult to find?
- Which occupations are most exposed to automation?
- What happens to a community when a company automates part of its workforce?
- Where should a company expand, automate, hire, or invest?
- Which regions are economically resilient enough to absorb technological disruption?

### For workers and individuals

- Where are my skills needed?
- Which occupations are growing or declining?
- How exposed is my current work to AI or robotics?
- What skills could transfer into more resilient work?
- Where might better opportunities exist?

### For communities and policymakers

- Which regions face the greatest displacement pressure?
- Where could automation create severe local economic instability?
- Which communities have enough economic diversity to adapt?
- Where will aging populations create labor shortages?
- Where should infrastructure, training, housing, or investment be directed?

---

## God Variable (GV)

GVAI grew from the **God Variable (GV)** research project.

GV is a survivability-oriented framework for measuring constraint strain, drift, instability, irreversibility risk, and recovery across changing systems.

Within GVAI, GV serves as an underlying analytical layer for asking a broader question:

> **Can this system, organization, economy, or community remain viable as its constraints change?**

GV research remains part of the project, but GVAI's primary product direction is now **Post-Labor Capitalism Intelligence**.

---

## Architecture

GVAI currently includes:

- Interactive Cesium-based 3D Earth
- Geographic coordinate selection
- Regional intelligence API
- U.S. Census geocoding
- ACS demographic and workforce data
- Occupational workforce profiles
- Automation and labor-transition modeling
- GV survivability analysis
- AI-assisted regional analysis
- Simulation infrastructure
- Privacy and outbound-model controls

The platform is being designed so additional national and international datasets can be added as geographic intelligence layers.

---

## API

The GVAI API provides services used by the interactive platform.

Example regional lookup:

```text
GET /api/region?lat=<latitude>&lon=<longitude>
```

A supported U.S. coordinate can return regional information including:

```json
{
  "state": "Tennessee",
  "county": "Rutherford County",
  "population": 360646,
  "labor_force": 201582,
  "unemployment_rate": 3.6,
  "median_household_income": 85470,
  "median_home_value": 382600,
  "median_age": 34.2
}
```

Regional responses can also contain occupational workforce composition.

---

## CLI

The original GVAI command-line interface remains available:

```bash
python -m gvai.cli "your input here"
```

---

## Conversation GV Demo

Build the conversation GV demonstration data:

```bash
PYTHONPATH=. python3 scripts/build_conversation_gv_demo.py
```

---

## Development Status

GVAI is under active development.

The current build establishes the foundation for a larger geographic intelligence system combining:

**Economics + Labor + Automation + Demographics + Geography + AI + GV**

Future development will expand:

- Labor-market time series
- Occupation-level automation exposure
- Business and industry intelligence
- Corporate automation tracking
- Regional labor shortages
- Aging-population pressure
- International datasets
- Geographic heat maps
- Scenario simulation
- AI-assisted workforce transition planning
- Community-level automation impact modeling

---

## Vision

AI and robotics may fundamentally change the relationship between human labor, production, income, and economic value.

That transition will not affect every person or every place equally.

Some regions may experience labor shortages.

Some may experience rapid displacement.

Some industries may become extraordinarily productive with very little human labor.

Some communities may struggle to adapt.

GVAI exists to make those changes **visible, measurable, geographic, and understandable**.

---

# GVAI

### Post-Labor Capitalism Intelligence
