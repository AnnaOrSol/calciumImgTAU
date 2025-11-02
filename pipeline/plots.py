import matplotlib.pyplot as plt
from typing import Optional
import pandas as pd
from pathlib import Path


class SignalPlotter:
    def __init__(self, stim_frame: Optional[int] = None, save_dir: Optional[str | Path] = None):
        self.stim_frame = stim_frame
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)

    def _vline_stim(self, ax):
        if self.stim_frame is not None and 0 <= self.stim_frame < 10**9:
            ax.axvline(self.stim_frame, linestyle='--', linewidth=1.0)

    def plot_per_roi(self, roi_name: str, raw_df: pd.DataFrame, sub_df: pd.DataFrame, dff_df: pd.DataFrame,
                     title_suffix: str = "", f0_repr: Optional[float] = None):
        fig, axes = plt.subplots(3, 1, figsize=(14,9), sharex=True)
        axes[0].plot(raw_df[roi_name].values); self._vline_stim(axes[0]); axes[0].set_title("RAW"); axes[0].set_ylabel("Intensity")
        axes[1].plot(sub_df[roi_name].values); self._vline_stim(axes[1]); axes[1].set_title("Baseline | Subtract"); axes[1].set_ylabel("F - F0")
        axes[2].plot(dff_df[roi_name].values); self._vline_stim(axes[2]); axes[2].set_title("Baseline | ΔF/F"); axes[2].set_ylabel("ΔF/F"); axes[2].set_xlabel("Frame")

        if f0_repr is not None:
            fig.suptitle(f"{roi_name} | {title_suffix} | F0~{f0_repr:.1f}", y=0.98)
        else:
            fig.suptitle(f"{roi_name} | {title_suffix}", y=0.98)

        fig.tight_layout(rect=(0,0,1,0.94))

        if self.save_dir:
            out = self.save_dir / f"{roi_name}.png"
            fig.savefig(out, dpi=120)
            plt.close(fig)
        else:
            # on local, not on the server
            plt.show()
