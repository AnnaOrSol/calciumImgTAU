# filters.py
from __future__ import annotations

import numpy as np
import pandas as pd

# Optional SciPy dependencies
try:
    from scipy.signal import savgol_filter
    HAVE_SCIPY_SG = True
except Exception:
    HAVE_SCIPY_SG = False

try:
    from scipy.ndimage import gaussian_filter1d
    HAVE_SCIPY_GAUSS = True
except Exception:
    HAVE_SCIPY_GAUSS = False


class FilterApplier:
    """
    Apply 1D smoothing filters column-wise on a DataFrame (frames x ROIs).

    Supported methods:
      - 'savgol'   : Savitzky–Golay (requires SciPy)
      - 'gaussian' : Gaussian smoothing (SciPy preferred; NumPy fallback)

    Design notes:
      * NaN-aware: temporary forward/backward fill to avoid NaN propagation during
        convolution, then restore NaNs at original locations.
      * Validations for Savitzky–Golay window/polyorder to prevent runtime errors.
      * Vectorized Savitzky–Golay over axis=0 for performance.
      * Gaussian uses scipy.ndimage.gaussian_filter1d when available; otherwise
        falls back to NumPy convolution with np.pad.
    """

    def __init__(
        self,
        method: str = "savgol",
        gaussian_sigma: float = 2.0,
        gauss_boundary: str = "reflect",  # 'reflect' | 'nearest' | 'mirror' | 'wrap'
        savgol_window: int = 30,
        savgol_poly: int = 3,
    ):
        self.method = (method or "savgol").lower()
        self.gaussian_sigma = float(gaussian_sigma)
        self.gauss_boundary = gauss_boundary  # passed-through to ndimage or mapped in fallback
        self.savgol_window = int(savgol_window)
        self.savgol_poly = int(savgol_poly)

    # ------------------------
    # Internal helpers
    # ------------------------
    @staticmethod
    def _to_float_df(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure float dtype for numeric stability and correct divisions."""
        if not all(np.issubdtype(dt, np.floating) for dt in df.dtypes):
            return df.astype(float)
        return df

    @staticmethod
    def _restore_nans(filtered: pd.DataFrame, nan_mask: pd.DataFrame) -> pd.DataFrame:
        """Put NaNs back to their original locations after filtering."""
        return filtered.where(~nan_mask, np.nan)

    # ------------------------
    # Gaussian implementations
    # ------------------------
    def _gaussian_ndimage(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gaussian smoothing via scipy.ndimage.gaussian_filter1d (preferred)."""
        # ndimage supports modes: 'reflect', 'nearest', 'mirror', 'wrap', 'constant'
        mode = self.gauss_boundary
        arr = df.to_numpy(dtype=float)
        out = gaussian_filter1d(arr, sigma=self.gaussian_sigma, axis=0, mode=mode)
        return pd.DataFrame(out, index=df.index, columns=df.columns, dtype=float)

    def _gaussian_numpy(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gaussian smoothing via manual kernel + np.pad + np.convolve (fallback)."""
        sigma = float(self.gaussian_sigma)
        if sigma <= 0:
            return df.copy()

        # Build kernel (truncate at ±3σ)
        radius = int(max(1, round(3 * sigma)))
        kx = np.arange(-radius, radius + 1, dtype=float)
        kernel = np.exp(-0.5 * (kx / sigma) ** 2)
        kernel /= kernel.sum()

        # Map boundary mode to np.pad arguments
        mode = self.gauss_boundary
        if mode == "nearest":
            pad_mode = "edge"
        elif mode in ("reflect", "mirror"):
            pad_mode = "reflect"
        else:
            pad_mode = "wrap"

        out = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)
        for c in df.columns:
            a = df[c].to_numpy(dtype=float)
            a_pad = np.pad(a, (radius, radius), mode=pad_mode)
            y = np.convolve(a_pad, kernel, mode="valid")
            out[c] = y
        return out

    def _apply_gaussian(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dispatch to SciPy or NumPy implementation."""
        if self.gaussian_sigma <= 0:
            return df.copy()
        if HAVE_SCIPY_GAUSS:
            return self._gaussian_ndimage(df)
        return self._gaussian_numpy(df)

    # ------------------------
    # Savitzky–Golay implementation
    # ------------------------
    def _apply_savgol(self, df: pd.DataFrame) -> pd.DataFrame:
        if not HAVE_SCIPY_SG:
            raise ImportError("Savitzky–Golay filter requires SciPy. Please install scipy.")

        n = len(df)
        if n < 3:
            # Too short to filter meaningfully; return a copy
            return df.copy()

        # Ensure odd window and bounded by sequence length
        win = int(self.savgol_window) | 1
        # Max valid odd window length that is <= n
        max_odd = n if (n % 2 == 1) else (n - 1)
        win = max(3, min(win, max_odd))

        # Validate polyorder
        if self.savgol_poly >= win:
            raise ValueError("SAVGOL_POLY must be < SAVGOL_WINDOW")
        if win < (self.savgol_poly + 2):
            # Common practical constraint to ensure stable local fits
            raise ValueError("SAVGOL_WINDOW must be at least POLYORDER + 2")

        # Vectorized filter along axis=0 (columns are ROIs, rows are frames)
        arr = df.to_numpy(dtype=float)
        arr_out = savgol_filter(arr, window_length=win, polyorder=self.savgol_poly, axis=0)
        return pd.DataFrame(arr_out, index=df.index, columns=df.columns, dtype=float)

    # ------------------------
    # Public API
    # ------------------------
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the selected smoothing method to each column of df.

        NaN behavior:
          - Temporarily forward/backward fill to prevent NaN propagation inside
            the filter, then restore NaNs to their original positions.
        """
        if df is None or df.empty:
            return df

        df = self._to_float_df(df)

        # Preserve original NaNs and fill them temporarily
        nan_mask = df.isna()
        # If an entire column is NaN, keep it as is
        all_nan_cols = nan_mask.all(axis=0)
        df_filled = df.copy()
        # Forward/backward fill only if the whole column is not NaN
        for c in df.columns:
            if not all_nan_cols[c]:
                df_filled[c] = df[c].bfill().ffill()

        if self.method == "gaussian":
            filtered = self._apply_gaussian(df_filled)
        elif self.method == "savgol":
            filtered = self._apply_savgol(df_filled)
        else:
            raise ValueError("FILTER_METHOD must be 'gaussian' or 'savgol'")

        # Restore NaNs to their original locations
        filtered = self._restore_nans(filtered, nan_mask)

        return filtered
