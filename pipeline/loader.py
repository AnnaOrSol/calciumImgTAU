import pandas as pd
from pathlib import Path


class SignalLoader:
    def __init__(self, filepath: str | Path, sheet: int | str | None = 0, drop_first: int = 0):
        self.filepath = Path(filepath)
        self.sheet = sheet
        self.drop_first = drop_first

    def load(self) -> pd.DataFrame:
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")

        if self.filepath.suffix.lower() == ".csv":
            df = pd.read_csv(self.filepath, header=None)
        else:
            df = pd.read_excel(self.filepath, sheet_name=self.sheet, header=None)

        df = df.apply(pd.to_numeric, errors='coerce').dropna(how='all').reset_index(drop=True)
        df.columns = [f"ROI_{i+1}" for i in range(df.shape[1])]

        if self.drop_first > 0:
            if self.drop_first >= len(df):
                raise ValueError("Requested to drop more frames than available")
            df = df.iloc[self.drop_first:].reset_index(drop=True)

        return df
