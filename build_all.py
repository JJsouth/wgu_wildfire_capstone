import sys
import pandas as pd

from data_pipeline import load_data, get_gacc, join_geo_data, mann_whitney_test
from visuals import (gacc_map, gacc_fire_map, results_region_map, plot_r_bars,
                     plot_monthly_fires, human_cause_breakdown, chart_path, CHARTS_DIR)
from segments import SEGMENTS

MIN_N = 30                           # min fires per cause group to run the test
FIRE_MAP_SEGMENTS = {"all", "tail", "body", "class_A", 
                     "class_B", "class_C", "class_D",
                     "class_E", "class_F", "class_g"
                     }  # the fire scatter maps are slow, so limit them
LEGEND_TITLE = "Which fires are larger?\n(Mann-Whitney U: p < 0.005 and |r| ≥ 0.10)"


def safe_test(df):
    n_h = (df["nwcg_cause_classification"] == "Human").sum()
    n_n = (df["nwcg_cause_classification"] == "Natural").sum()
    if min(n_h, n_n) < MIN_N:
        return None
    return mann_whitney_test(df)


def build_segment(key, fires, gacc):
    label, pick = SEGMENTS[key]
    seg = pick(fires)

    results = {name: safe_test(g) for name, g in seg.groupby("gaccname")}
    regional = pd.DataFrame({k: v for k, v in results.items() if v is not None}).T
    national = safe_test(seg)

    rows = []
    for region in ["National"] + sorted(gacc["gaccname"].unique()):
        is_nat = region == "National"
        data = (seg if is_nat else seg[seg["gaccname"] == region]).copy()
        result = national if is_nat else results.get(region)

        rows.append({"region": region, "n_fires": len(data),
                     **(result.to_dict() if result is not None
                        else {"conclusion": "Insufficient data"})})
        if data.empty:
            continue

        out = lambda name: chart_path(key, region, name)
        print(f"{key} | {region} | {len(data):,} fires")

        if key == "all":   # locator map, once per region
            gacc_map(gacc, highlight=None if is_nat else region,
                     save_path=out("gacc_highlight.png"))

        if result is not None and not regional.empty:
            results_region_map(regional, gacc=gacc,
                               highlight=None if is_nat else region,
                               legend_title=LEGEND_TITLE,
                               title=f"{region}: {label}",
                               save_path=out("region_map.png"))

        if result is not None:
            with_nat = (not is_nat) and national is not None
            plot_r_bars(pd.DataFrame([result], index=[region]),
                        national_r=float(national["r_rb"]) if with_nat else None,
                        figsize=(6, 0.6 * (2 if with_nat else 1) + 1.2),
                        save_path=out("r_bars.png"))

        plot_monthly_fires(data, f"{region} ({label})", save_path=out("monthly_fires.png"))

        if (data["nwcg_cause_classification"] == "Human").any():
            human_cause_breakdown(data, f"{region} ({label})", save_path=out("human_causes.png"))

        if key in FIRE_MAP_SEGMENTS:
            try:
                gacc_fire_map(data, gacc, save_path=out("fires_map.png"))
            except Exception as e:     # e.g. a single-region map with an empty panel
                print(f"  fires map skipped for {region}: {e}")

    pd.DataFrame(rows).to_csv(CHARTS_DIR / key / "results.csv", index=False)


if __name__ == "__main__":
    gacc = get_gacc()
    fires = join_geo_data(load_data(), gacc)
    for key in (sys.argv[1:] or SEGMENTS):
        build_segment(key, fires, gacc)