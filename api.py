# api.py
import shutil
import uuid
import json
from pathlib import Path
import io
import pandas as pd
from fastapi.responses import JSONResponse

from pipeline.baseline import BaselineComputer
from pipeline.detrend import Detrender
from pipeline.normalizer import Normalizer
from pipeline.filters import FilterApplier
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline_api import PipelineAPI
from schemas import ProcessParams, ProcessResponse

app = FastAPI(title="Opcal TAU Pipeline API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_api = PipelineAPI(results_dir="results")
UPLOADS_DIR = Path("results") / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _cleanup_file(p: Path):
    try:
        p.unlink(missing_ok=True)
    except Exception:
        pass


def _parse_params(params_str: str | None) -> dict:

    if not params_str:
        return {}
    try:
        model = ProcessParams.model_validate_json(params_str)
        return {k: v for k, v in model.model_dump().items() if v is not None}
    except Exception:
        obj = json.loads(params_str)
        model = ProcessParams.model_validate(obj)
        return {k: v for k, v in model.model_dump().items() if v is not None}


@app.post("/process/roi")
async def process_roi(
    file: UploadFile = File(...),
    params: str | None = Form(None),
):
    try:
        contents = await file.read()
        if file.filename.lower().endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(contents), header=None)
        else:
            df_raw = pd.read_excel(io.BytesIO(contents), header=None)

        df_raw.columns = [f"ROI_{i+1}" for i in range(df_raw.shape[1])]

        cfg = _parse_params(params)

        drop_first = int(cfg.get("drop_first", 10))
        stim_frame = cfg.get("stim_frame", 44)
        baseline_mode = cfg.get("baseline_mode", "pre_stim_median")
        pre_window = int(cfg.get("pre_window", 43))
        rolling_window = int(cfg.get("rolling_window", 101))
        global_percentile_q = float(cfg.get("global_percentile_q", 30.0))
        rolling_percentile_q = float(cfg.get("rolling_percentile_q", 10.0))
        detrend_method = cfg.get("detrend", "none")
        norm_mode = (cfg.get("normalization_mode") or "dff").lower()
        gaussian_sigma = float(cfg.get("gaussian_sigma", 2.0))
        filter_method = cfg.get("filter_method", "savgol")
        savgol_window = int(cfg.get("savgol_window", 30))
        savgol_poly = int(cfg.get("savgol_poly", 3))

        if drop_first > 0:
            df_raw = df_raw.iloc[drop_first:].reset_index(drop=True)

        baseline = BaselineComputer(
            mode=baseline_mode,
            stim_frame=stim_frame,
            pre_window=pre_window,
            rolling_window=rolling_window,
            global_percentile_q=global_percentile_q,
            rolling_percentile_q=rolling_percentile_q,
        )
        F0_df, f0_vec = baseline.compute(df_raw)

        detrender = Detrender(method=detrend_method, rolling_window=rolling_window)
        df_detr = detrender.apply(df_raw)

        # SUB = (F - F0)
        sub_df = Normalizer.subtract(df_detr, F0_df)

        # ΔF/F
        dff_df = Normalizer.deltaF_over_F(df_detr, F0_df)

        norm_df = dff_df if norm_mode == "dff" else sub_df

        filterer = FilterApplier(
            method=filter_method,
            savgol_window=savgol_window,
            savgol_poly=savgol_poly,
            gaussian_sigma=gaussian_sigma,
        )
        filter_norm_df = filterer.apply(norm_df)

        return JSONResponse(
            content={
                "roi_names": list(df_raw.columns),
                "frames": list(range(len(df_raw))),
                "raw": {roi: df_raw[roi].astype(float).tolist() for roi in df_raw.columns},
                "sub": {roi: sub_df[roi].astype(float).tolist() for roi in df_raw.columns},
                "dff": {roi: dff_df[roi].astype(float).tolist() for roi in df_raw.columns},
                "dff_filtered": {roi: filter_norm_df[roi].astype(float).tolist() for roi in df_raw.columns},
                "f0": {k: float(v) for k, v in f0_vec.to_dict().items()},
                "config_used": cfg,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/process/json", response_model=ProcessResponse)
async def process_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    params: str | None = Form(None),
):

    ext = Path(file.filename).suffix or ".xlsx"
    tmp_path = UPLOADS_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        cfg = _parse_params(params)
        out_path = pipeline_api.process_file(tmp_path, config_overrides=cfg, save_plots=True)
        background_tasks.add_task(_cleanup_file, tmp_path)

        plots_dir = str((pipeline_api.results_dir / "plots" / tmp_path.stem).resolve())
        return ProcessResponse(ok=True, output_excel=str(out_path.resolve()), plots_dir=plots_dir)
    except Exception as e:
        background_tasks.add_task(_cleanup_file, tmp_path)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/process/download")
async def process_download(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    params: str | None = Form(None),
):
    ext = Path(file.filename).suffix or ".xlsx"
    tmp_path = UPLOADS_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        cfg = _parse_params(params)
        out_path = pipeline_api.process_file(tmp_path, config_overrides=cfg, save_plots=False)
        background_tasks.add_task(_cleanup_file, tmp_path)
        return FileResponse(
            path=out_path,
            filename=out_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        background_tasks.add_task(_cleanup_file, tmp_path)
        raise HTTPException(status_code=400, detail=str(e))
