import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from data_pipeline import *
from pathlib import Path

CHARTS_DIR = Path(__file__).parent / "charts"

def chart_path(segment, region, filename):
    folder = CHARTS_DIR / segment / region
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename

def _resolve_view(view, highlight=None, fires=None):
    '''Decide which panels to draw: 'both', 'lower48', or 'alaska'.'''
    if view is not None:
        return view
    if highlight is not None:
        return "alaska" if highlight == "Alaska" else "lower48"
    if fires is not None:
        regions = set(fires["gaccname"].dropna().unique())
        if regions == {"Alaska"}:
            return "alaska"
        if "Alaska" not in regions:
            return "lower48"
    return "both"


def _view_windows(lower48, alaska, pad=100_000, left_pad=None):
    '''Axis limits (in meters) for the lower 48 panel and the Alaska mainland panel.'''
    minx, miny, maxx, maxy = lower48.total_bounds
    main_xlim = (minx - (left_pad or pad), maxx + pad)
    main_ylim = (miny - pad, maxy + pad)

    ak_parts = alaska.explode(index_parts=False).reset_index(drop=True)
    ak_big = ak_parts.loc[[ak_parts.area.idxmax()]]      # mainland only, skips the Aleutians
    x0, y0, x1, y1 = ak_big.total_bounds
    return main_xlim, main_ylim, (x0 - pad, x1 + pad), (y0 - pad, y1 + pad)


def _map_figure(view, main_xlim, main_ylim, ak_xlim, ak_ylim,
                width=18, ak_scale=0.7, cbar=False):
    '''Create the figure with only the panels the view needs. Returns fig and a dict of axes.'''
    parts = []
    if view in ("both", "lower48"):
        parts.append(("main", main_xlim[1] - main_xlim[0]))
    if view in ("both", "alaska"):
        scale = ak_scale if view == "both" else 1.0     # Alaska full size when it's alone
        parts.append(("ak", (ak_xlim[1] - ak_xlim[0]) * scale))

    height = (ak_ylim[1] - ak_ylim[0]) if view == "alaska" else (main_ylim[1] - main_ylim[0])
    total = sum(w for _, w in parts)
    if cbar:
        parts.append(("cbar", 0.03 * total))
        total = sum(w for _, w in parts)

    fig = plt.figure(figsize=(width, width * height / total))
    gs = fig.add_gridspec(1, len(parts), width_ratios=[w for _, w in parts], wspace=0.0)
    axes = {name: fig.add_subplot(gs[i]) for i, (name, _) in enumerate(parts)}
    return fig, axes


def gacc_map(gacc=None, highlight=None, save_path="gacc_regions.png", ak_scale=0.7, view=None):
    '''
    Create a general map of the GACC regions.
    Note: The small bit of Southwest in the Southern area is not an error, it is the national
    grasslands in Texas and Oklahoma Panhandles that the Southwest Agency is in charge of.
    '''
    if gacc is None:
        gacc = get_gacc()
    view = _resolve_view(view, highlight)

    regions = sorted(gacc["gaccname"].unique())
    colors = dict(zip(regions, plt.cm.tab10.colors))
    if highlight is not None:
        if highlight not in regions:
            raise ValueError(f"Unknown region '{highlight}'. Choose from: {regions}")
        colors = {r: (colors[r] if r == highlight else "#E6E6E6") for r in regions}

    lower48 = gacc[gacc["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    alaska = gacc[gacc["gaccname"] == "Alaska"].to_crs("EPSG:3338")
    main_xlim, main_ylim, ak_xlim, ak_ylim = _view_windows(lower48, alaska)
    fig, axes = _map_figure(view, main_xlim, main_ylim, ak_xlim, ak_ylim, 18, ak_scale)

    def draw(ax, g, xlim, ylim, fontsize):
        g.plot(ax=ax, color=g["gaccname"].map(colors), edgecolor="white", linewidth=1.2)
        for _, row in g.iterrows():
            name = row["gaccname"]
            if highlight is not None and name != highlight:
                continue
            p = row.geometry.representative_point()
            label = name.replace(" ", "\n", 1) if len(name) > 12 else name
            ax.annotate(label, (p.x, p.y), ha="center", va="center",
                        fontsize=fontsize, fontweight="bold", color="black",
                        path_effects=[pe.withStroke(linewidth=3, foreground="white")])
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_axis_off()

    if "main" in axes:
        draw(axes["main"], lower48, main_xlim, main_ylim, 11)
    if "ak" in axes:
        draw(axes["ak"], alaska, ak_xlim, ak_ylim, 14 if view == "alaska" else 11)

    first_ax = axes.get("main", axes.get("ak"))
    first_ax.set_title("NIFC Geographic Area Coordination Centers (GACC)", fontsize=15)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.01)
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return fig


def gacc_fire_map(fires, gacc=None, save_path="gacc_fires.png", ak_scale=0.7, view=None):
    if gacc is None:
        gacc = get_gacc()
    view = _resolve_view(view, None, fires)

    print("Scaling fires")
    fires = fires.assign(log_size=np.log10(fires["fire_size"].clip(lower=0.01)))
    vmin, vmax = fires["log_size"].min(), fires["log_size"].max()

    print("Sorting fires")
    fires_sorted = fires.sort_values("fire_size")      # biggest fires drawn last, on top
    is_ak = fires_sorted["gaccname"] == "Alaska"
    pts_main = fires_sorted[~is_ak].to_crs("EPSG:5070")
    pts_ak = fires_sorted[is_ak].to_crs("EPSG:3338")

    poly_main = gacc[gacc["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    poly_ak = gacc[gacc["gaccname"] == "Alaska"].to_crs("EPSG:3338")
    main_xlim, main_ylim, ak_xlim, ak_ylim = _view_windows(poly_main, poly_ak)

    print("Creating fires map")
    fig, axes = _map_figure(view, main_xlim, main_ylim, ak_xlim, ak_ylim, 22, ak_scale, cbar=True)

    panels = []
    if "main" in axes:
        panels.append((axes["main"], poly_main, pts_main, 0.3, main_xlim, main_ylim))
    if "ak" in axes:
        panels.append((axes["ak"], poly_ak, pts_ak, 0.6 if view == "both" else 1.5, ak_xlim, ak_ylim))

    for ax, poly, pts, size, xlim, ylim in panels:
        poly.plot(ax=ax, color="#eeeeee", edgecolor="none")
        pts.plot(ax=ax, column="log_size", cmap="viridis", vmin=vmin, vmax=vmax,
                 markersize=size, alpha=0.6, rasterized=True)
        poly.boundary.plot(ax=ax, color="black", linewidth=0.8)
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_axis_off()

    first_ax = axes.get("main", axes.get("ak"))
    first_ax.set_title("Wildfires by GACC region (color = log10 acres burned)", fontsize=15)

    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(vmin, vmax))
    fig.colorbar(sm, cax=axes["cbar"]).set_label("log10(fire size, acres)")

    fig.subplots_adjust(left=0.01, right=0.95, top=0.92, bottom=0.05)
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    print(f"Saved GACC fires map to {save_path}")
    plt.close(fig)
    return fig


def results_region_map(df, legend_title, title, gacc=None, highlight=None,
                       save_path="region_map.png", view=None):
    palette = {
        "Human Larger":             "#D55E00",
        "Natural Larger":           "#0072B2",
        "No meaningful difference": "#D9D9D9",
    }
    if gacc is None:
        gacc = get_gacc()
    view = _resolve_view(view, highlight)

    res = df[["conclusion"]].copy()
    gmap = gacc.merge(res, left_on="gaccname", right_index=True, how="left")
    gmap["fill"] = gmap["conclusion"].map(palette).fillna("#F5F5F5")

    if highlight is not None:
        if highlight not in set(gmap["gaccname"]):
            raise ValueError(f"Unknown region '{highlight}'")
        gmap["fill"] = gmap["fill"].where(gmap["gaccname"] == highlight, "#EEEEEE")

    lower48 = gmap[gmap["gaccname"] != "Alaska"].to_crs("EPSG:5070")
    alaska = gmap[gmap["gaccname"] == "Alaska"].to_crs("EPSG:3338")

    # Extra room on the left of the lower 48 for the California labels
    main_xlim, main_ylim, ak_xlim, ak_ylim = _view_windows(lower48, alaska, pad=150_000, left_pad=800_000)
    fig, axes = _map_figure(view, main_xlim, main_ylim, ak_xlim, ak_ylim, 18)

    offsets = {"Northern California": (-650_000, 100_000),
               "Southern California": (-600_000, -450_000)}
    halo = [pe.withStroke(linewidth=3, foreground="white")]

    def draw(ax, g, xlim, ylim):
        g.plot(ax=ax, color=g["fill"], edgecolor="white", linewidth=1.2)
        for _, row in g.iterrows():
            name = row["gaccname"]
            if highlight is not None and name != highlight:
                continue
            p = row.geometry.representative_point()
            label = name.replace(" ", "\n", 1) if len(name) > 12 else name
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

    if "main" in axes:
        draw(axes["main"], lower48, main_xlim, main_ylim)
    if "ak" in axes:
        draw(axes["ak"], alaska, ak_xlim, ak_ylim)

    handles = [Patch(facecolor=c, edgecolor="gray", label=k) for k, c in palette.items()]
    if highlight is None:
        fig.legend(handles=handles, loc="lower right", title=legend_title,
                   frameon=False, fontsize=11, title_fontsize=11)

    fig.suptitle(title, fontsize=15, y=0.95)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.01)
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return fig



# --- Display Count of Fires by month ---------------------------------------------------------------
def plot_monthly_fires(df, region_label="Region", save_path="monthly_fires.png"):
   # Extract the month component as integers (1 through 12)
    df["month"] = df["discovery_dt"].dt.month

    bins = np.arange(1, 14)

    # 4. Plot the histogram
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(
        df["month"],
        bins=bins,
        edgecolor="black",
        align="left",
        rwidth=0.8,
        color="skyblue",
    )

    # Format X-axis with monthly names
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_names)

    ax.set_title(f"Total Fires by Month - {region_label}")
    ax.set_xlabel("Month")
    ax.set_ylabel("Count")
    ax.set_xlim(0.5, 12.5)

    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
            
    return fig


# --- Display how far left or right the rank-biserial skews for a region ----------------------------
def plot_r_bars(results, r_min=0.10, national_r=None, save_path="r_bars.png", figsize=None):
    palette = {
        "Human Larger":             "#D55E00",
        "Natural Larger":           "#0072B2",
        "No meaningful difference": "#D9D9D9",
        }
    
    res = results[["r_rb"]].copy()
    res["r_rb"] = res["r_rb"].astype(float)
    res = res.sort_values("r_rb", ascending=False)   # most human-leaning on top

    rows = list(res.itertuples())
    names = [r.Index for r in rows]
    values = [r.r_rb for r in rows]
    if national_r is not None:
        names.append("National")
        values.append(national_r)

    # (start, width, color) for each zone of the bar
    zones = [
        (-1,     1 - r_min, palette["Natural Larger"]),
        (-r_min, 2 * r_min, palette["No meaningful difference"]),
        (r_min,  1 - r_min, palette["Human Larger"]),
    ]

    fig, ax = plt.subplots(figsize=figsize or (10, 0.6 * len(names) + 1.5))
    bar_h = 0.45

    for i, (name, r) in enumerate(zip(names, values)):
        y = len(names) - 1 - i          # first row at the top
        for start, width, color in zones:
            ax.barh(y, width, left=start, height=bar_h, color=color, edgecolor="white")
        # the marker line, slightly taller than the bar so it stands out
        ax.plot([r, r], [y - bar_h * 0.8, y + bar_h * 0.8], color="black", lw=3,
                solid_capstyle="butt")
        ax.text(1.04, y, f"{r:+.2f}", va="center", fontsize=11, fontweight="bold")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names[::-1])
    ax.set_xlim(-1, 1.15)
    ax.set_xticks([-1, -r_min, 0, r_min, 1])
    ax.set_xticklabels(["-1", f"-{r_min:.2f}", "0", f"+{r_min:.2f}", "+1"])
    ax.set_xlabel("Rank-biserial r\n(negative = natural fires larger, positive = human fires larger)")

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)

    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return fig


# --- Breakdown bar graph of how many fires are caused by sub-categories of human activity ----------
def human_cause_breakdown(fires, region_label="Region", save_path="human_cause_breakdown.png"):
    human = fires[fires["nwcg_cause_classification"] == "Human"]
    counts = human["nwcg_general_cause"].value_counts().sort_values()   # smallest at bottom

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(counts.index, counts.values, color="#D55E00", edgecolor="black")

    ax.set_title(f"Human-Caused Fires by General Cause - {region_label}")
    ax.set_xlabel("Number of fires")
    ax.set_ylabel("")

    # Count label at the end of each bar
    for y, v in enumerate(counts.values):
        ax.text(v, y, f" {v:,}", va="center")
    ax.set_xlim(0, counts.max() * 1.12)       # room for the labels

    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return fig