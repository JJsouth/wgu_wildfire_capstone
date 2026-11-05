import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from data_pipeline import *



# --- Display GACC map -----------------------------------------------------------------------
def gacc_map(gacc=None, save_path="gacc_regions.png"):
    '''
    Create a general map of the GACC regions
    Note: The small bit of Southwest blue in the Southern area in not an error, it is the national grasslands in Texas and Omaha Panhandles that the Southwest Agency is in charge of.
    '''
    if gacc is None:
        gacc = get_gacc()
    
    regions = sorted(gacc["gaccname"].unique())
    colors = dict(zip(regions, plt.cm.tab10.colors))

    lower48 = gacc[gacc["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    alaska  = gacc[gacc["gaccname"] == "Alaska"].to_crs("EPSG:3338")

    fig = plt.figure(figsize=(20, 9))
    gs = fig.add_gridspec(1, 2, width_ratios=[4, 1.4], wspace=0.02)
    ax_main = fig.add_subplot(gs[0])
    ax_ak   = fig.add_subplot(gs[1])

    def draw(ax, g, fontsize):
        g.plot(ax=ax, color=g["gaccname"].map(colors), edgecolor="white", linewidth=1.2)
        for _, row in g.iterrows():
            p = row.geometry.representative_point()
            name = row["gaccname"]
            label = name.replace(" ", "\n", 1) if len(name) > 12 else name
            ax.annotate(
                label,
                (p.x, p.y), ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color="black",
                path_effects=[pe.withStroke(linewidth=3, foreground="white")],
            )
        ax.set_axis_off()

    draw(ax_main, lower48, fontsize=11)
    draw(ax_ak, alaska, fontsize=11)

    ax_main.set_title("NIFC Geographic Area Coordination Centers (GACC)", fontsize=15)
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    print(f"Saved GACC map to {save_path}")
    plt.close(fig)
    
    return fig
    

# --- Display all fires across the nation within their GACCs ----------------------------------------
def gacc_fire_map(fires, gacc=None, save_path="gacc_fires.png"):
    if gacc is None:
        gacc = get_gacc()

    print("Scaling fires")
    fires["log_size"] = np.log10(fires["fire_size"].clip(lower=0.01))
    vmin, vmax = fires["log_size"].min(), fires["log_size"].max()

    print("Sorting fires")
    # Sort once so the biggest fires are drawn last, on top
    fires_sorted = fires.sort_values("fire_size")

    # Split and project each part once
    is_ak = fires_sorted["gaccname"] == "Alaska"
    pts_main = fires_sorted[~is_ak].to_crs("EPSG:5070")
    pts_ak   = fires_sorted[is_ak].to_crs("EPSG:3338")

    poly_main = gacc[gacc["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    poly_ak   = gacc[gacc["gaccname"] == "Alaska"].to_crs("EPSG:3338")

    print("Creating fires map")
    fig = plt.figure(figsize=(22, 10))
    gs = fig.add_gridspec(1, 2, width_ratios=[4, 1.4], wspace=0.02)
    ax_main = fig.add_subplot(gs[0])
    ax_ak   = fig.add_subplot(gs[1])

    for ax, poly, pts, size in [
        (ax_main, poly_main, pts_main, 0.3),
        (ax_ak,   poly_ak,   pts_ak,   0.6),
    ]:
        poly.plot(ax=ax, color="#eeeeee", edgecolor="none")            # base fill
        pts.plot(ax=ax, column="log_size", cmap="viridis",
                vmin=vmin, vmax=vmax, markersize=size, alpha=0.6,
                rasterized=True)                                       # fires
        poly.boundary.plot(ax=ax, color="black", linewidth=0.8)         # borders on top
        ax.set_axis_off()

    ax_main.set_title("Wildfires by GACC region (color = log10 acres burned)", fontsize=15)

    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(vmin, vmax))
    fig.colorbar(sm, ax=[ax_main, ax_ak], shrink=0.6, pad=0.01).set_label("log10(fire size, acres)")

    
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    print(f"Saved GACC fires map to {save_path}")
    plt.close(fig)
    
    return fig


# --- Display test results conclusions by region ----------------------------------------------------
def results_region_map(df, label_fn, legend_title, title, gacc = None, save_path="region_map.png"):
    palette = {
    "Human Larger":             "#D55E00",
    "Natural Larger":           "#0072B2",
    "No meaningful difference": "#D9D9D9",
    }

    # get regional boundaries
    if gacc is None:
        gacc = get_gacc()

    # pull results from mwu testing df
    res = df[["r_rb", "conclusion"]].copy()
    res["r_rb"] = res["r_rb"].astype(float)

    # merge boundaries and results into one dataset
    gmap = gacc.merge(res, left_on="gaccname", right_index=True, how="left")
    gmap["fill"] = gmap["conclusion"].map(palette)

    # split data into lower48 and alaska to use different mapping coordinate systems
    lower48 = gmap[gmap["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    alaska  = gmap[gmap["gaccname"] == "Alaska"].to_crs("EPSG:3338")

    # View windows (meters), with extra room on the left for California labels
    pad = 150_000
    minx, miny, maxx, maxy = lower48.total_bounds
    main_xlim = (minx - 800_000, maxx + pad)
    main_ylim = (miny - pad, maxy + pad)

    ak_parts = alaska.explode(index_parts=False).reset_index(drop=True)
    ak_big = ak_parts.loc[[ak_parts.area.idxmax()]]          # mainland only
    x0, y0, x1, y1 = ak_big.total_bounds
    ak_xlim, ak_ylim = (x0 - pad, x1 + pad), (y0 - pad, y1 + pad)

    # Panel widths proportional to content; Alaska drawn at ~70% scale
    w_main = main_xlim[1] - main_xlim[0]
    w_ak = (ak_xlim[1] - ak_xlim[0]) * 0.7
    h_main = main_ylim[1] - main_ylim[0]

    fig = plt.figure(figsize=(18, 18 * h_main / (w_main + w_ak)))
    gs = fig.add_gridspec(1, 2, width_ratios=[w_main, w_ak], wspace=0.0)
    ax_main, ax_ak = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    offsets = {"Northern California": (-650_000, 100_000),
               "Southern California": (-600_000, -450_000)}
    halo = [pe.withStroke(linewidth=3, foreground="white")]

    def draw(ax, g, xlim, ylim):
        g.plot(ax=ax, color=g["fill"], edgecolor="white", linewidth=1.2)
        for _, row in g.iterrows():
            name = row["gaccname"]
            p = row.geometry.representative_point()
            wrapped = name.replace(" ", "\n", 1) if len(name) > 12 else name
            label = f"{wrapped}\n{label_fn(row)}"
            if name in offsets:
                dx, dy = offsets[name]
                ax.annotate(label, xy=(p.x, p.y), xytext=(p.x + dx, p.y + dy),
                            ha="center", va="center", fontsize=11, fontweight="bold",
                            path_effects=halo,
                            arrowprops=dict(arrowstyle="-", color="black", lw=1))
            else:
                ax.annotate(label, (p.x, p.y), ha="center", va="center",
                            fontsize=11, fontweight="bold", path_effects=halo)
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_axis_off()

    draw(ax_main, lower48, main_xlim, main_ylim)
    draw(ax_ak, alaska, ak_xlim, ak_ylim)

    handles = [Patch(facecolor=c, edgecolor="gray", label=k) for k, c in palette.items()]
    fig.legend(handles=handles, loc="lower right", title=legend_title,
                 frameon=False, fontsize=11, title_fontsize=11)

    fig.suptitle(title, fontsize=15, y=0.95)
    plt.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.01)
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
        
    return fig

def monthly_fires(fires, file_path="monthly_fires.png"):
    pass
    

if __name__ == "__main__":
    gacc = get_gacc()
    fires = join_geo_data(load_data())
    gacc_map(gacc)
    gacc_fire_map(fires, gacc)

    results_region_map(
        regional,
        label_fn=lambda row: f"r = {row['r_rb']:+.2f}",
        legend_title="Which fires are larger?\n(Mann-Whitney U: p < 0.005 and |r| ≥ 0.10)",
        title="Human vs. Natural Ignition: Fire Size by GACC Region",
        )
        