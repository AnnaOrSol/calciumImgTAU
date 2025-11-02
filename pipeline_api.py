from pathlib import Path
from run_pipeline import run_pipeline


class PipelineAPI:
    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)

    def process_file(self, input_path: Path, config_overrides: dict | None = None, save_plots: bool = False) -> Path:
        
        output_path = run_pipeline(
            input_path=input_path,
            save_excel=True,
            output_dir=self.results_dir,
            config_overrides=config_overrides,
            save_plots=save_plots,
            plots_dir=self.results_dir / "plots" / input_path.stem
        )
        return output_path
