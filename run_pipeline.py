from pipeline.loader import SignalLoader
from pipeline.baseline import BaselineComputer
from pipeline.detrend import Detrender
from pipeline.normalizer import Normalizer
from pipeline.filters import FilterApplier
from pipeline.plots import SignalPlotter
from pipeline.saver import SignalSaver
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt

DEFAULT_CONFIG = {
    "drop_first": 10,
    "stim_frame": 44,
    "baseline_mode": "pre_stim_median",
    "pre_window": 43,
    "rolling_window": 101,
    "baseline_rolling_window": None,
    "detrend_rolling_window": None,
    "normalization_mode": "dff",
    "global_percentile_q": 30.0,
    "rolling_percentile_q": 10.0,
    "detrend": "none",
    "filter_method": "savgol",
    "gaussian_sigma": 2.0,
    "savgol_window": 30,
    "savgol_poly": 3,
    "show_baseline_info": True,
}


def run_pipeline(
    input_path: str | Path,
    save_excel: bool = True,
    output_dir: str | Path = "results",
    config_overrides: Optional[dict] = None,
    save_plots: bool = False,
    plots_dir: str | Path = "results/plots"
) -> Path:
    cfg = {**DEFAULT_CONFIG, **(config_overrides or {})}

    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}_dff.xlsx"

    loader = SignalLoader(str(input_path), drop_first=cfg["drop_first"])
    df_raw = loader.load()

    baseline_rw = cfg.get("baseline_rolling_window") or cfg["rolling_window"]
    detrend_rw = cfg.get("detrend_rolling_window") or cfg["rolling_window"]

    baseline = BaselineComputer(
        mode=cfg["baseline_mode"],
        stim_frame=cfg["stim_frame"],
        pre_window=cfg["pre_window"],
        rolling_window=baseline_rw,
        global_percentile_q=cfg["global_percentile_q"],
        rolling_percentile_q=cfg["rolling_percentile_q"],
    )
    F0_df, f0_vec = baseline.compute(df_raw)

    df_detr = Detrender(method=cfg["detrend"], rolling_window=detrend_rw).apply(df_raw)

    # Always compute both, to keep flexibility for plotting & optional saving
    sub_df = Normalizer.subtract(df_detr, F0_df)
    dff_df = Normalizer.deltaF_over_F(df_detr, F0_df)

    # Pick the primary normalization for downstream filtering / saving
    norm_mode = cfg.get("normalization_mode", "dff").lower()
    if norm_mode == "subtract":
        norm_df = sub_df
    elif norm_mode == "dff":
        norm_df = dff_df
    else:
        raise ValueError("Unknown normalization_mode: expected 'dff' or 'subtract'")

    filterer = FilterApplier(
        method=cfg["filter_method"],
        gaussian_sigma=cfg.get("gaussian_sigma", 2.0),
        savgol_window=cfg["savgol_window"],
        savgol_poly=cfg["savgol_poly"],
    )
    filter_df = filterer.apply(norm_df)

    if save_excel:
        saver = SignalSaver(output_path)
        if norm_mode == "dff":
            saver.save_excel(dff_df, sheet_name="DeltaF_over_F")
        else:
            saver.save_excel(sub_df, sheet_name="F_minus_F0")

    if save_plots:
        plots_path = Path(plots_dir)
        plots_path.mkdir(parents=True, exist_ok=True)
        plotter = SignalPlotter(stim_frame=cfg["stim_frame"], save_dir=plots_path)
        for roi in df_raw.columns:
            plotter.plot_per_roi(
                roi, df_raw, sub_df, filter_df,
                title_suffix=cfg["baseline_mode"], f0_repr=f0_vec[roi]
            )
        plt.show()

    return output_path


if __name__ == "__main__":
    output_file = run_pipeline(r"C:\Users\annas\Downloads\wt1.xlsx", save_plots=True )
    print(f"ΔF/F saved to: {output_file}")
