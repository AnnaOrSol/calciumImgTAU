from pathlib import Path
import pandas as pd


class SignalSaver:
    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def save_excel(self, df: pd.DataFrame, sheet_name: str = "DeltaF_over_F"):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        engine = "openpyxl"
        df.to_excel(self.output_path, sheet_name=sheet_name, index=False, engine=engine)
        print(f"[OK] Excel saved successfully → {self.output_path}")
