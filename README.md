# FEMA PA Wildfire → Water Utility Funding Finder

A small Streamlit app that uses **OpenFEMA** Public Assistance Grant Award Activities (v2) to find water utilities that received FEMA funding for **wildfire** incidents under **Category F (Public Utilities)**. No API key required.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app_streamlit_fema_water.py
```

## Docker
```bash
docker build -t fema-water-app .
docker run -p 8501:8501 fema-water-app
```

Then open http://localhost:8501

## Notes
- Category F includes water, power, gas, sewer, and communications; keyword filters narrow to water utilities.
- Fields shown: state, applicantId, applicantName, dateObligated, federalShareObligated, projectTitle, pwNumber, versionNumber, disasterNumber, county, damageCategoryCode.
- Outputs include downloadable CSVs (project-level and per-utility summary).
- Data source: OpenFEMA Public Assistance Grant Award Activities (v2).
