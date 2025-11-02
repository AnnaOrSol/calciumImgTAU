from pydantic import BaseModel, Field
from typing import Optional


class ProcessParams(BaseModel):
    drop_first: Optional[int] = Field(None, ge=0)
    stim_frame: Optional[int] = Field(None, ge=1)
    baseline_mode: Optional[str] = Field(None, description="pre_stim_median | global_median | global_percentile | rolling_median | rolling_percentile | rolling_mean")
    pre_window: Optional[int] = Field(None, ge=1)
    rolling_window: Optional[int] = Field(None, ge=3)
    baseline_rolling_window: Optional[int] = Field(None, ge=3)
    detrend_rolling_window: Optional[int] = Field(None, ge=3)
    global_percentile_q: Optional[float] = Field(None, ge=0, le=100)
    gaussian_sigma: Optional[float] = Field(None, gt=0)
    rolling_percentile_q: Optional[float] = Field(None, ge=0, le=100)
    detrend: Optional[str] = Field(None, description="none | rolling_median | linear")
    normalization_mode: Optional[str] = Field(None, description="dff | subtract")
    filter_method: Optional[str] = Field(None, description="savgol | gaussian")
    savgol_window: Optional[int] = Field(None, ge=3)
    savgol_poly: Optional[int] = Field(None, ge=1)


class ProcessResponse(BaseModel):
    ok: bool = True
    output_excel: str
    plots_dir: str | None = None
