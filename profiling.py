from data_profiling import ProfileReport
import sqlite3
import pandas as pd
from pathlib import Path


conn = sqlite3.connect("wildfire_data.sqlite")

relevant_columns = [
    'fire_name',
    'fire_year',
    'discovery_date',
    'discovery_doy',
    'discovery_time',
    'nwcg_cause_classification',
    'nwcg_general_cause',
    'nwcg_cause_age_category',
    'cont_date',
    'cont_doy',
    'cont_time',
    'fire_size',
    'fire_size_class',
    'latitude',
    'longitude',
    'state',
    'fips_name',  # County name
]

query = f"SELECT {', '.join(relevant_columns)} FROM FIRES"

raw_data = pd.read_sql_query(query, conn)
raw_data.columns = raw_data.columns.str.lower()
conn.close()

# remove incorrectly classified fire that was part of a different complex
raw_data = raw_data[raw_data['fire_name'] != 'ZION 3']

profile = ProfileReport(raw_data, title="Wildfire EDA")
output_path = Path(__file__).parent / "wildfire_eda.html"
profile.to_file(output_path)