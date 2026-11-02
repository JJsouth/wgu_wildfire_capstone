import sqlite3
import pandas as pd

def load_data():
    print("querying")
    # Load Raw Dataset
    conn = sqlite3.connect("wildfire_data.sqlite")

    # Load raw data set
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
        'upper(state) as state'
    ]

    query = f"SELECT {', '.join(relevant_columns)} FROM FIRES WHERE fire_name IS NULL OR fire_name != 'ZION 3'"

    try:
        raw_data = pd.read_sql_query(query, conn)
        raw_data.columns = raw_data.columns.str.lower()
    finally:
        conn.close()

    print("data read")
    print(raw_data.shape)


    # Convert Dates
    def add_datetime(df, date_col, time_col, new_col):
        # Julian date -> datetime (midnight of that day)
        dates = pd.to_datetime(df[date_col], unit="D", origin="julian")

        # HHMM -> hours and minutes (to_numeric handles '0845' strings and NaNs)
        t = pd.to_numeric(df[time_col], errors="coerce")
        offset = pd.to_timedelta(t // 100, unit="h") + pd.to_timedelta(t % 100, unit="m")

        df[new_col] = dates + offset
        return df

    print("converting discovery date")
    raw_data = add_datetime(raw_data, "discovery_date", "discovery_time", "discovery_dt")
    print("converting contained date")
    raw_data = add_datetime(raw_data, "cont_date", "cont_time", "cont_dt")

    raw_data = raw_data.drop(columns=["discovery_date", "discovery_doy", "discovery_time", "cont_date", "cont_doy", "cont_time"])

    print("calculating duration")
    raw_data["duration_hours"] = (
        raw_data["cont_dt"] - raw_data["discovery_dt"]
    ).dt.total_seconds() / 3600


    # Drop Unknown Ignitions
    predrop_rows = raw_data.shape[0]
    print("dropping unknown fires")
    raw_data = raw_data[raw_data['nwcg_cause_classification'] != 'Missing data/not specified/undetermined']
    postdrop_rows = raw_data.shape[0]
    print(f"dropped {predrop_rows - postdrop_rows} unknown ignition fires")
    print(raw_data['nwcg_cause_classification'].unique())

    clean_data = raw_data
    return clean_data

if __name__ == "__main__":
    clean_data = load_data()
