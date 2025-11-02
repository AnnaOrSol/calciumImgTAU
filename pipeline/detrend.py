import pandas as pd
import numpy as np


class Detrender:
    def __init__(self, method: str = 'none', rolling_window: int = 201):
        self.method = method
        self.rolling_window = rolling_window

    def _linear_detrend(self, s: pd.Series) -> pd.Series:
        x = np.arange(len(s), dtype=float)
        A = np.vstack([x, np.ones_like(x)]).T
        m, b = np.linalg.lstsq(A, s.to_numpy(dtype=float), rcond=None)[0]
        return pd.Series(s.to_numpy(dtype=float) - (m*x + b), index=s.index)

    def _rolling_median_detrend(self, df: pd.DataFrame) -> pd.DataFrame:
        med = df.rolling(self.rolling_window, center=True, min_periods=1).median()
        return df - med

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        m = self.method.lower()
        if m == 'none':
            return df.copy()
        if m == 'linear':
            return df.apply(self._linear_detrend, axis=0)
        if m == 'rolling_median':
            if self.rolling_window < 5 or self.rolling_window % 2 == 0:
                raise ValueError("rolling_window must be odd and >=5")
            return self._rolling_median_detrend(df)
        raise ValueError("DETREND_METHOD must be 'none','rolling_median','linear'")
