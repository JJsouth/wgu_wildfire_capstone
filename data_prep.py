import sqlite3
import pandas as pd
import geopandas as gpd

def load_data():
    print("querying")
    # Load Raw Dataset
    conn = sqlite3.connect("wildfire_data.sqlite")

    relevant_columns = [
        'fire_name',
        'fire_year',
        'discovery_date',
        'discovery_doy',
        'discovery_time',
        'nwcg_cause_classification',
        'nwcg_general_cause',
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


    # --- Convert Dates ------------------------------------------------------------------
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


    # --- Drop Unknown Ignitions ------------------------------------------------------------------
    predrop_rows = raw_data.shape[0]
    print("dropping unknown fires")

    raw_data = raw_data[raw_data['nwcg_cause_classification'] != 'Missing data/not specified/undetermined']
    postdrop_rows = raw_data.shape[0]

    print(f"dropped {predrop_rows - postdrop_rows} unknown ignition fires")
    print(f"fire cause classifications: {raw_data['nwcg_cause_classification'].unique()}")

    # --- Drop Island Fires ------------------------------------------------------------------
    keep_states = {
        "AL","AZ","AR","CA","CO","CT","DE","DC","FL","GA","ID","IL","IN","IA","KS",
        "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM",
        "NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA",
        "WA","WV","WI","WY","AK",
    }

    n0 = len(raw_data)
    raw_data = raw_data[raw_data["state"].isin(keep_states)].copy()
    print(f"Dropped {n0 - len(raw_data):,} fires outside AK + lower 48")

    clean_data = raw_data
    return clean_data

def join_geo_data(df):
    # --- clean up gacc names to remove uneeded parts of the label ----------------------------------------
    def clean_gacc(s):
        s = s.str.replace(
            r"\s*(Geographic Area|Interagency|Area)?\s*Coordination Center$",
            "", regex=True
        ).str.strip()
        return s.replace({"Eastern": "Eastern Area", "Southern": "Southern Area"})

    # Load the boundaries, clean the names:
    gacc = gpd.read_file("gacc_boundaries.geojson")
    gacc.columns = gacc.columns.str.lower()
    gacc = gacc[["gaccname", "geometry"]].copy()
    gacc["gaccname"] = clean_gacc(gacc["gaccname"])    

    # Drop the islands:
    parts = gacc.explode(index_parts=False)
    pt = parts.geometry.representative_point()
    keep = pt.x.between(-130, -60) & pt.y.between(24, 50)
    gacc = parts[keep | (parts["gaccname"] == "Alaska")].dissolve(by="gaccname").reset_index()

    print(f"Regions: {sorted(gacc["gaccname"].unique())}")  # 10 regions
    print(f"Polygon Bounds: {gacc.total_bounds}")
    
    # --- Build points and join to fire dataset --------------------------------------------------
    fires = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    ).to_crs(gacc.crs)

    n_points = len(fires)
    fires = gpd.sjoin(fires, gacc, how="left", predicate="within")

    print(n_points, len(fires))                  # equal = no duplicated rows
    print(fires["gaccname"].isna().sum())        
    
    
    # Fires that didn't land in any GACC (offshore, bad coordinates, territories)
    print(fires["gaccname"].isna().sum())

    # sjoin can duplicate rows if a point touches overlapping polygons
    print(len(df), len(fires))

    unmatched = fires[fires["gaccname"].isna()]
    print(unmatched[["fire_name", "fire_year", "state", "latitude", "longitude"]])
    print(unmatched["state"].value_counts())


    # Reproject to a metric CRS so distances are in meters, not degrees
    gacc_m = gacc.to_crs("EPSG:5070")
    unmatched = fires[fires["gaccname"].isna()].drop(columns=["gaccname", "index_right"])
    unmatched_m = unmatched.to_crs("EPSG:5070")

    nearest = gpd.sjoin_nearest(
        unmatched_m,
        gacc_m[["gaccname", "geometry"]],
        how="left",
        distance_col="dist_m",
    )

    # 28 fires located on the international border fell outside GACC polygons 
    # and are assigned to the nearest GACC.

    # A point equidistant from two polygons returns two rows, so dedupe
    nearest = nearest[~nearest.index.duplicated(keep="first")]

    # Sanity check: these should all be small
    print(nearest["dist_m"].describe())

    # Write the matches back into the main frame
    fires.loc[nearest.index, "gaccname"] = nearest["gaccname"]
    print(fires["gaccname"].isna().sum())   # should be 0

    # drop bad rows with placeholder coordinates
    bad = (
        (fires["state"] == "MO") & (fires["gaccname"] == "Southern Area")
        & (fires["latitude"] % 1 == 0) & (fires["longitude"] % 1 == 0)
    )
    print(bad.sum())   # expect 2
    fires = fires[~bad].copy()

    



if __name__ == "__main__":
    clean_data = load_data()
    join_geo_data(clean_data)
