from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Union


Number = Union[int, float]
BaseLike = Union[pd.DataFrame, pd.Series, Number]


class Normalizer:
    """
    Utility class for basic fluorescence normalization steps.

    Key goals:
      1) Provide robust (F - F0) and ΔF/F that gracefully handle edge cases.
      2) Accept baseline as a DataFrame, Series (per-ROI), or a scalar.
      3) Avoid artificial bias: only apply epsilon where F0 is too small.
      4) Keep outputs numeric and clean of NaN/Inf unless the caller wants otherwise.

    Notes on broadcasting:
      - Pandas aligns by axis labels. If you pass a Series as 'baseline', its index
        should match df.columns (per-ROI baseline). If you pass a scalar baseline,
        it will broadcast across all values.
    """

    @staticmethod
    def _to_float_df(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure float dtype (avoids integer division and preserves precision)."""
        if not np.issubdtype(df.dtypes.values[0], np.floating):
            return df.astype(float)
        return df

    @staticmethod
    def _safe_baseline(
        baseline: BaseLike,
        eps: float
    ) -> BaseLike:
        """
        Make baseline safe for division:
          - If DataFrame/Series: replace entries with |F0| < eps by +eps.
          - If scalar: use +eps if |F0| < eps (keeps sign non-negative to prevent surprises).
        Rationale: we only adjust where needed instead of adding eps everywhere.
        """
        if isinstance(baseline, (pd.DataFrame, pd.Series)):
            # Replace too-small values with +eps. Using +eps (not signed) to keep behavior predictable.
            return baseline.where(baseline.abs() >= eps, eps)
        else:
            b = float(baseline)
            return b if abs(b) >= eps else eps

    # ----------------------------
    # Public API
    # ----------------------------
    @staticmethod
    def subtract(
        df: pd.DataFrame,
        baseline: BaseLike
    ) -> pd.DataFrame:
        """
        Pointwise subtraction: (F - F0).
        Accepts F0 as DataFrame, Series (per-ROI), or scalar.
        """
        df = Normalizer._to_float_df(df)
        return df - baseline  # Pandas will handle alignment/broadcasting.

    @staticmethod
    def deltaF_over_F(
        df: pd.DataFrame,
        baseline: BaseLike,
        eps: float = 1e-12,
        as_percent: bool = False,
        clip_negatives: bool = False,
        fillna_value: float | None = 0.0,
    ) -> pd.DataFrame:
        """
        Compute ΔF/F = (F - F0) / F0 with robust epsilon handling.

        Parameters
        ----------
        df : pd.DataFrame
            Raw (or detrended) fluorescence signals (frames x ROIs or ROIs as columns).
        baseline : DataFrame | Series | float
            Baseline F0. If Series, its index should align with df.columns (per-ROI F0).
        eps : float, default 1e-12
            Minimum absolute baseline used to avoid division by zero or near-zero.
            Applied *only* where needed.
        as_percent : bool, default False
            If True, multiply the result by 100 (i.e., return percent ΔF/F).
        clip_negatives : bool, default False
            If True, clip negative values to 0.0 after computation. Some protocols prefer this.
        fillna_value : float | None, default 0.0
            Replace NaN/Inf with this value. If None, leave NaN/Inf as-is.

        Returns
        -------
        pd.DataFrame
            ΔF/F values with the same shape/columns as `df`.
        """
        df = Normalizer._to_float_df(df)

        # Make baseline safe (applies eps only where |F0| is too small)
        safe_base = Normalizer._safe_baseline(baseline, eps=eps)

        # Compute (F - F0) / F0 with alignment/broadcasting handled by pandas
        out = (df - safe_base) / safe_base

        # Optional percent scaling
        if as_percent:
            out = out * 100.0

        # Clean up numeric edge-cases
        out = out.replace([np.inf, -np.inf], np.nan)
        if fillna_value is not None:
            out = out.fillna(fillna_value)

        # Optionally clip negatives (useful for certain downstream analyses)
        if clip_negatives:
            out = out.clip(lower=0.0)

        return out
