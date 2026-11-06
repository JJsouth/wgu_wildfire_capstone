import sqlite3
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Patch
from scipy.stats import mannwhitneyu
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "wildfire_data.sqlite"
GACC_PATH = PROJECT_ROOT / "gacc_boundaries.geojson"


def load_data(filepath=DB_PATH):
    print("querying")
    # Load Raw Dataset
    conn = sqlite3.connect(filepath)

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

def get_gacc(filepath=GACC_PATH):
    # --- clean up gacc names to remove uneeded parts of the label ---------------------------------
    def clean_gacc(s):
        s = s.str.replace(
            r"\s*(Geographic Area|Interagency|Area)?\s*Coordination Center$",
            "", regex=True
        ).str.strip()
        return s.replace({"Eastern": "Eastern Area", "Southern": "Southern Area"})

    # Load the boundaries, clean the names:
    gacc = gpd.read_file(filepath)
    gacc.columns = gacc.columns.str.lower()
    gacc = gacc[["gaccname", "geometry"]].copy()
    gacc["gaccname"] = clean_gacc(gacc["gaccname"])    

    # Drop the islands:
    parts = gacc.explode(index_parts=False)
    pt = parts.geometry.representative_point()
    keep = pt.x.between(-130, -60) & pt.y.between(24, 50)
    gacc = parts[keep | (parts["gaccname"] == "Alaska")].dissolve(by="gaccname").reset_index()

    print(f"GACC Regions: {sorted(gacc["gaccname"].unique())}")  # 10 regions
    print(f"Polygon Bounds: {gacc.total_bounds}")
    return gacc

def join_geo_data(df, gacc=None):
    # Load Regions
    if gacc is None:
            gacc = get_gacc()
    # --- Build points and join to fire dataset --------------------------------------------------
    fires = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    ).to_crs(gacc.crs)

    fires = gpd.sjoin(fires, gacc, how="left", predicate="within")

    
    # sjoin can duplicate rows if a point touches overlapping polygons
    print("Check for Duplicate Rows")
    print(f"Geo Dataset Rows: {len(df)} | Input Dataset Rows: {len(fires)}")


    # --- Find fires outside of any GACC Boundary and join them to nearest boundary ---------------
    
    # Fires that didn't land in any GACC (offshore, bad coordinates, territories)
    print(f"Fires not in any GACC: {fires["gaccname"].isna().sum()}")

    if fires["gaccname"].isna().sum() > 0:
        unmatched = fires[fires["gaccname"].isna()]
        print(unmatched[["fire_name", "fire_year", "state", "latitude", "longitude"]])
        print(unmatched["state"].value_counts())


        # --- Reproject to a metric CRS so distances are in meters, not degrees ----------------------
        gacc_m = gacc.to_crs("EPSG:5070")
        unmatched = fires[fires["gaccname"].isna()].drop(columns=["gaccname", "index_right"])
        unmatched_m = unmatched.to_crs("EPSG:5070")

        nearest = gpd.sjoin_nearest(
            unmatched_m,
            gacc_m[["gaccname", "geometry"]],
            how="left",
            distance_col="dist_m",
        )

        # A point equidistant from two polygons returns two rows, so dedupe
        nearest = nearest[~nearest.index.duplicated(keep="first")]

        # Write the matches back into the main dataframe
        print("Matching fires to nearest GACC boundary")
        fires.loc[nearest.index, "gaccname"] = nearest["gaccname"]
        print(f"Remaining fires outside of GACC: {fires["gaccname"].isna().sum()}")   # should be 0
    
    # --- drop bad rows with placeholder coordinates -------------------------------------
    bad = (
        (fires["state"] == "MO") & (fires["gaccname"] == "Southern Area")
        & (fires["latitude"] % 1 == 0) & (fires["longitude"] % 1 == 0)
    )
    print(f"Bad placeholder coordinate rows dropped: {bad.sum()}")   # expect 2
    fires = fires[~bad].copy()

    return fires

def data_summary(df):
     # --- Statistical summary by fire class ----------------------------------------------------------------
        summary = df.groupby(["nwcg_cause_classification", "fire_size_class"])["fire_size"].agg(
        count="size", median="median", mean="mean", max="max",
        p75=lambda s: s.quantile(0.75), p95=lambda s: s.quantile(0.95),
        )
        print(summary)

def mann_whitney_test(df, alt="two-sided", alpha=0.005, r_min=0.10):
    # --- Split data into independent human and natural groups --------------------------------
    human = df.loc[df["nwcg_cause_classification"] == "Human", "fire_size"].to_numpy()
    natural = df.loc[df["nwcg_cause_classification"] == "Natural", "fire_size"].to_numpy()

    # --- Calculate mann-whitney u comparison statistic and rank-biserial ---------------------
    result = mannwhitneyu(human, natural, alternative=alt)
    r = 2 * result.statistic / (len(human) * len(natural)) - 1 # rank-biserial

    # --- Determine which ignition danger group the region falls into ---------------------------
    # if the result is statistically significant (p-value < alpha) and the difference is meaningful (r > r_min), return which group it falls under based on the rank-biserial calculation. 
    # Otherwise conclude there is no meaninful difference
    if result.pvalue < alpha and abs(r) >= r_min:
        if r > 0:
            conclusion = "Human Larger"
        else:
            conclusion = "Natural Larger"
    else:
        conclusion = "No meaningful difference"

    return pd.Series({
        "n_human": len(human),
        "n_natural": len(natural),
        "median_human": np.median(human),
        "median_natural": np.median(natural),
        "U": result.statistic,
        "p_value": result.pvalue,
        "r_rb": r,  # The rank-biserial rescales the U statistic from -1 to 1 to determine which direction the fire cause leans -1 Natural to 1 Human
        "prob_superiority": (r + 1) / 2, # The prob_superiority calculates the probability of a randomly selected human fire to be larger than a randomly selected natural fire
        "conclusion": conclusion
        })
    

if __name__ == "__main__":
    clean_data = load_data()
    fires = join_geo_data(clean_data)

    national = mann_whitney_test(fires)
    print("National Analysis")
    print(national)

    regional = pd.DataFrame({name: mann_whitney_test(g) for name, g in fires.groupby("gaccname")}).T


    print("\nRegional Analysis")
    print(regional[["n_human", "n_natural", "median_human", "median_natural",
                    "p_value", "r_rb", "prob_superiority", "conclusion"]])

   