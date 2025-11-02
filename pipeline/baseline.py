import pandas as pd
import numpy as np


class BaselineComputer:
    def __init__(
        self,
        mode: str = "pre_stim_median",
        stim_frame: int | None = None,
        pre_window: int = 43,
        rolling_window: int = 101,
        global_percentile_q: float = 30.0,
        rolling_percentile_q: float = 10.0,
        roll_min_frac: float = 0.2
    ):
        self.mode = mode
        self.stim_frame = stim_frame
        self.pre_window = pre_window
        self.rolling_window = rolling_window
        self.global_percentile_q = global_percentile_q
        self.rolling_percentile_q = rolling_percentile_q
        self.roll_min_frac = roll_min_frac

    def _validate_positive(self, n: int, name: str):
        if n < 3:
            raise ValueError(f"{name} must be >= 3")

    def _validate_stim_and_window(self, n_rows: int):
        if self.stim_frame is None:
            raise ValueError("STIM_FRAME is None; pre-stim baseline requires a stimulus frame.")
        if self.stim_frame <= 0 or self.stim_frame > n_rows:
            raise ValueError(f"STIM_FRAME={self.stim_frame} out of range [1..{n_rows}] after trimming")
        self._validate_positive(self.pre_window, "BASELINE_PRE_WINDOW")

    def baseline_pre_stim_median(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        n = len(df)
        self._validate_stim_and_window(n)
        start = max(0, self.stim_frame - self.pre_window)
        prestim = df.iloc[start:self.stim_frame]
        f0 = prestim.median(axis=0)
        F0_df = pd.DataFrame(np.tile(f0.values, (n, 1)), index=df.index, columns=df.columns)
        return F0_df, f0

    def baseline_global_median(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        f0 = df.median(axis=0)
        F0_df = pd.DataFrame(np.tile(f0.values, (len(df),1)), index=df.index, columns=df.columns)
        return F0_df, f0

    def baseline_global_percentile(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        if not (0.0 <= self.global_percentile_q <= 100.0):
            raise ValueError("GLOBAL_PERCENTILE_Q must be in [0,100]")
        f0 = df.quantile(self.global_percentile_q/100.0, axis=0)
        F0_df = pd.DataFrame(np.tile(f0.values, (len(df),1)), index=df.index, columns=df.columns)
        return F0_df, f0

    def _rolling_apply_quantile(self, df: pd.DataFrame, window: int, q: float) -> pd.DataFrame:
        self._validate_positive(window, "ROLLING_WINDOW")
        minp = max(3, int(np.ceil(window * self.roll_min_frac)))

        def _q(s: pd.Series) -> float:
            return float(np.nanquantile(s.to_numpy(), q/100.0))
        base = df.rolling(window=window, center=True, min_periods=minp).apply(_q, raw=False)
        return base.bfill().ffill()

    def baseline_rolling_median(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        self._validate_positive(self.rolling_window, "ROLLING_WINDOW")
        minp = max(3, int(np.ceil(self.rolling_window * self.roll_min_frac)))
        base = df.rolling(window=self.rolling_window, center=True, min_periods=minp).median()
        base = base.bfill().ffill()
        f0_repr = base.median(axis=0)
        return base, f0_repr

    def baseline_rolling_percentile(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        base = self._rolling_apply_quantile(df, self.rolling_window, self.rolling_percentile_q)
        f0_repr = base.median(axis=0)
        return base, f0_repr

    def baseline_rolling_mean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        self._validate_positive(self.rolling_window, "ROLLING_WINDOW")
        minp = max(3, int(np.ceil(self.rolling_window * self.roll_min_frac)))
        base = df.rolling(window=self.rolling_window, center=True, min_periods=minp).mean().bfill().ffill()
        f0_repr = base.median(axis=0)
        return base, f0_repr

    def compute(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        mode = self.mode
        if mode == 'pre_stim_median':
            return self.baseline_pre_stim_median(df)
        if mode == 'global_median':
            return self.baseline_global_median(df)
        if mode == 'global_percentile':
            return self.baseline_global_percentile(df)
        if mode == 'rolling_median':
            return self.baseline_rolling_median(df)
        if mode == 'rolling_percentile':
            return self.baseline_rolling_percentile(df)
        if mode == 'rolling_mean':
            return self.baseline_rolling_mean(df)
        raise ValueError(f"Unknown baseline mode: {mode}")
