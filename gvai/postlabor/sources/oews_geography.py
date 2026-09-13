"""Packaged OEWS geography crosswalks for runtime-local regional lookup.

County membership is transcribed from the U.S. Bureau of Labor Statistics,
"May 2025 OEWS County Links to Metropolitan and Nonmetropolitan Area Pages":
https://www.bls.gov/oes/2025/may/tn_counties.htm

The BLS page is the authority for county-to-area membership. This module keeps
only its deterministic county FIPS lookup form; it does not fetch BLS at runtime.
"""

from __future__ import annotations


BLS_OEWS_TENNESSEE_COUNTY_SOURCE = (
    "https://www.bls.gov/oes/2025/may/tn_counties.htm"
)
BLS_OEWS_TENNESSEE_COUNTY_VINTAGE = "May 2025"
TENNESSEE_STATE_FIPS = "47"


# Full county FIPS -> BLS OEWS metropolitan/nonmetropolitan area. Statewide
# Tennessee area 4700000 is deliberately absent because county lookup must use
# the BLS county's metro/nonmetro area.
TENNESSEE_COUNTY_TO_OEWS_AREA = {
    "47001": "0028940", "47003": "4700002", "47005": "4700001",
    "47007": "4700004", "47009": "0028940", "47011": "0017420",
    "47013": "0028940", "47015": "0034980", "47017": "4700001",
    "47019": "0027740", "47021": "0034980", "47023": "0027180",
    "47025": "4700003", "47027": "4700003", "47029": "4700004",
    "47031": "4700002", "47033": "0027180", "47035": "4700003",
    "47037": "0034980", "47039": "4700001", "47041": "4700003",
    "47043": "0034980", "47045": "4700001", "47047": "0032820",
    "47049": "4700003", "47051": "4700002", "47053": "0027180",
    "47055": "4700002", "47057": "0028940", "47059": "4700004",
    "47061": "4700002", "47063": "0034100", "47065": "0016860",
    "47067": "4700003", "47069": "4700001", "47071": "4700001",
    "47073": "0028700", "47075": "4700001", "47077": "4700001",
    "47079": "4700001", "47081": "0034980", "47083": "4700001",
    "47085": "4700001", "47087": "4700003", "47089": "0034100",
    "47091": "4700004", "47093": "0028940", "47095": "4700001",
    "47097": "4700001", "47099": "4700002", "47101": "4700002",
    "47103": "4700002", "47105": "0028940", "47107": "4700004",
    "47109": "4700001", "47111": "0034980", "47113": "0027180",
    "47115": "0016860", "47117": "4700002", "47119": "0034980",
    "47121": "4700004", "47123": "4700004", "47125": "0017300",
    "47127": "4700002", "47129": "0028940", "47131": "4700001",
    "47133": "4700003", "47135": "4700002", "47137": "4700003",
    "47139": "0017420", "47141": "4700003", "47143": "4700004",
    "47145": "0028940", "47147": "0034980", "47149": "0034980",
    "47151": "4700003", "47153": "0016860", "47155": "4700004",
    "47157": "0032820", "47159": "0034980", "47161": "0017300",
    "47163": "0028700", "47165": "0034980", "47167": "0032820",
    "47169": "0034980", "47171": "0027740", "47173": "0028940",
    "47175": "4700004", "47177": "4700003", "47179": "0027740",
    "47181": "4700002", "47183": "4700001", "47185": "4700003",
    "47187": "0034980", "47189": "0034980",
}


def resolve_tennessee_county_oews_area(
    state_fips: str | None,
    county_fips: str | None,
) -> str | None:
    if str(state_fips or "").zfill(2) != TENNESSEE_STATE_FIPS:
        return None
    county = str(county_fips or "").zfill(3)
    return TENNESSEE_COUNTY_TO_OEWS_AREA.get(
        TENNESSEE_STATE_FIPS + county
    )