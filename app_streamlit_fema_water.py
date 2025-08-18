#!/usr/bin/env python3
# app_streamlit_fema_water.py (enhanced)
# Streamlit app: FEMA PA (v2) – Find wildfire-related funding to water utilities.
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import urllib.parse
from typing import List, Dict, Any, Optional

API_BASE = "https://www.fema.gov/api/open/v2/PublicAssistanceGrantAwardActivities"

DEFAULT_INCLUDE = [
    "water", "water district", "water dept", "water department", "water authority",
    "water utility", "municipal water", "water & sewer", "water and sewer",
    "wastewater", "waste water", "sanitation", "sanitary", "sewer",
    "wtp", "water treatment", "waterworks", "water works", "aqueduct",
    "water supply", "water system", "irrigation district"
]

DEFAULT_EXCLUDE = [
]

ALL_CATEGORIES = ["A","B","C","D","E","F","G"]

def build_filter(states: Optional[List[str]], start: Optional[str], end: Optional[str],
                 categories: List[str], incident_contains: bool) -> str:
    parts = []
    if incident_contains:
        parts.append("(substringof('Fire',incidentType) or substringof('Wildfire',incidentType))")
    else:
        parts.append("incidentType eq 'Fire'")
    
    if categories:
        cat_or = " or ".join([f"damageCategoryCode eq '{c.strip().upper()}'" for c in categories if c.strip()])
        if cat_or:
            parts.append("(" + cat_or + ")")

    if states:
        state_filters = [f"stateAbbreviation eq '{s.strip().upper()}'" for s in states if s.strip()]
        if state_filters:
            parts.append("(" + " or ".join(state_filters) + ")")
    if start:
        parts.append(f"dateObligated ge '{start}'")
    if end:
        parts.append(f"dateObligated le '{end}'")
    return " and ".join(parts)

def fetch_all(filters: str, select_fields: Optional[List[str]] = None, progress=None, debug=False) -> pd.DataFrame:
    records = []
    top = 1000
    skip = 0
    base_params = {
        "$filter": filters,
        "$top": str(top),
        "$skip": str(skip),
        "$format": "json",
        "$count": "true"
    }
    if select_fields:
        base_params["$select"] = ",".join(select_fields)
    session = requests.Session()
    total_count = None
    last_url = ""
    while True:
        params = dict(base_params)
        params["$skip"] = str(skip)
        url = API_BASE + "?" + urllib.parse.urlencode(params, safe="(),':")
        last_url = url
        resp = session.get(url, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        payload = resp.json()
        data_key = None
        for k, v in payload.items():
            if isinstance(v, list):
                data_key = k
                break
        rows = payload.get(data_key, [])
        if total_count is None:
            md = payload.get("metadata", {})
            total_count = md.get("count", 0)
        if not rows:
            break
        records.extend(rows)
        skip += top
        if progress and total_count:
            progress.progress(min(1.0, len(records)/max(total_count,1)))
        if len(rows) < top:
            break
    df = pd.DataFrame.from_records(records)
    return df, last_url, total_count or 0

def is_water_utility(row: pd.Series, include: List[str], exclude: List[str]) -> bool:
    name = str(row.get("applicantName") or "").lower()
    title = str(row.get("projectTitle") or "").lower()
    if any(x in name for x in exclude):
        return False
    text = f"{name} {title}"
    return any(x in text for x in include)

def summarize(df: pd.DataFrame, include: List[str], exclude: List[str]) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df.apply(lambda r: is_water_utility(r, include, exclude), axis=1)
    sdf = df.loc[mask].copy()
    sdf["federalShareObligated"] = pd.to_numeric(sdf["federalShareObligated"], errors="coerce").fillna(0.0)
    sdf["dateObligated"] = pd.to_datetime(sdf["dateObligated"], errors="coerce")
    grp = sdf.groupby(["stateAbbreviation","applicantId","applicantName"], dropna=False).agg(
        projectCount=("applicantId","count"),
        totalFederalShareObligated=("federalShareObligated","sum"),
        firstDateObligated=("dateObligated","min"),
        lastDateObligated=("dateObligated","max")
    ).reset_index().rename(columns={"stateAbbreviation":"state"})
    grp = grp.sort_values(["state","totalFederalShareObligated"], ascending=[True, False])
    grp["firstDateObligated"] = grp["firstDateObligated"].dt.date.astype(str)
    grp["lastDateObligated"] = grp["lastDateObligated"].dt.date.astype(str)
    return grp

st.set_page_config(page_title="FEMA → Water Utility Funding (Wildfire)", layout="wide")
st.title("FEMA PA (v2) – Wildfire Funding Finder for Water Utilities")

with st.sidebar:
    st.header("Filters")
    states_input = st.text_input("States (comma-separated 2-letter codes)", value="")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date (≥)", value=None)
    with col2:
        end_date = st.date_input("End date (≤)", value=None)
    cats = st.multiselect("Damage categories", options=ALL_CATEGORIES, default=[])
    incident_contains = st.toggle("Match incidentType by contains('Fire'/'Wildfire')", value=True)
    include = st.text_area("Include keywords (comma-separated)", value=",".join(DEFAULT_INCLUDE))
    exclude = st.text_area("Exclude keywords (comma-separated)", value=",".join(DEFAULT_EXCLUDE))
    run = st.button("Run search", type="primary")

select_fields = [
    "stateAbbreviation","applicantId","applicantName","dateObligated","federalShareObligated",
    "projectTitle","pwNumber","versionNumber","disasterNumber","county","damageCategoryCode","incidentType"
]

if run:
    states = [s.strip().upper() for s in states_input.split(",") if s.strip()] if states_input else None
    s = start_date.isoformat() if start_date else None
    e = end_date.isoformat() if end_date else None
    flt = build_filter(states, s, e, cats, incident_contains)
    st.caption(f"API filter: `{flt}`")
    progress = st.progress(0.0)
    try:
        df, last_url, total_count = fetch_all(flt, select_fields=select_fields, progress=progress)
        progress.progress(1.0)
        st.caption(f"Records found (API count): {total_count} | Last page URL used (copy into browser to debug):")
        st.code(last_url, language="text")
    except Exception as ex:
        st.error(f"API error: {ex}")
        st.stop()

    include_list = [x.strip().lower() for x in include.split(",") if x.strip()]
    exclude_list = [x.strip().lower() for x in exclude.split(",") if x.strip()]

    if df.empty:
        st.warning("No results. Tips: remove state/date filters; include more categories (B/E often have wildfire water costs); use 'contains' for incidentType.")
        st.stop()

    st.subheader("Detailed results (project-level) – filtered to water utilities")
    mask = df.apply(lambda r: is_water_utility(r, include_list, exclude_list), axis=1)
    water_df = df.loc[mask].copy()
    st.write(f"Matched **{len(water_df)}** water-utility project rows out of **{len(df)}** API rows.")
    st.dataframe(water_df.head(100))
    st.download_button("Download detailed CSV", water_df.to_csv(index=False).encode("utf-8"),
                       file_name="fema_water_pa_fire_detailed.csv", mime="text/csv")

    st.subheader("Summary by utility")
    sum_df = summarize(df, include_list, exclude_list)
    st.dataframe(sum_df.head(100))
    st.download_button("Download summary CSV", sum_df.to_csv(index=False).encode("utf-8"),
                       file_name="fema_water_pa_fire_summary.csv", mime="text/csv")

    st.subheader("Top utilities by total federal share (net)")
    toplist = sum_df.sort_values("totalFederalShareObligated", ascending=False).head(20)
    st.table(toplist[["state","applicantName","projectCount","totalFederalShareObligated","firstDateObligated","lastDateObligated"]])

st.markdown("""---
***Instructions***
- This app helps identify water utilities with Public Assistance (PA) projects funded in response to fires and wildfires.
- Use the filters to narrow results by date and keywords (include or exclude).
- The “Match incident type by contains (Fire/Wildfire)” option broadens the search to capture incidents labeled either Fire or Wildfire. These categories may overlap.
- The Damage Category filter is not currently functional.

**Docs**  
- OpenFEMA API filter syntax (including `substringof`, `in`, `eq`): https://www.fema.gov/about/openfema/api  
- Category F covers utilities – water, power, wastewater, communications: https://www.fema.gov/openfema-data-page/public-assistance-grant-award-activities-v2
""")
