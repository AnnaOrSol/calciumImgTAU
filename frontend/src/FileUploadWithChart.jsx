import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import annotationPlugin from "chartjs-plugin-annotation";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  annotationPlugin
);

// Configure your API base via .env: VITE_API_URL=http://127.0.0.1:8000
const API_BASE = (import.meta.env?.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_URL = `${API_BASE}/process/roi`;

const DEFAULT_PARAMS = {
  drop_first: 10,
  stim_frame: 44,
  baseline_mode: "pre_stim_median",
  pre_window: 43,
  rolling_window: 101,
  baseline_rolling_window: null,
  detrend_rolling_window: null,
  global_percentile_q: 30,
  rolling_percentile_q: 10,
  detrend: "none",
  normalization_mode: "dff",
  filter_method: "savgol",
  savgol_window: 30,
  savgol_poly: 3,
  gaussian_sigma: 2.0,
};

const STORAGE_KEY = "opcalTAU.params.en.v1";

export default function FileUploadWithChart() {
  // -------- File & params --------
  const [file, setFile] = useState(null);
  const [params, setParams] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      return saved ? { ...DEFAULT_PARAMS, ...saved } : DEFAULT_PARAMS;
    } catch {
      return DEFAULT_PARAMS;
    }
  });

  // -------- Server data --------
  const [roiNames, setRoiNames] = useState([]);
  const [frames, setFrames] = useState([]);
  const [seriesRaw, setSeriesRaw] = useState({});
  const [seriesSub, setSeriesSub] = useState({});
  const [seriesDff, setSeriesDff] = useState({});
  const [seriesDffFilt, setSeriesDffFilt] = useState({});

  // -------- ROI selection --------
  const [selectedROIs, setSelectedROIs] = useState({});
  const [activeROI, setActiveROI] = useState("");
  const [roiQuery, setRoiQuery] = useState("");

  // -------- UI state --------
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // important: toggles come BEFORE any useMemo that uses them
  const [showRAW, setShowRAW] = useState(false);
  const [showSUB, setShowSUB] = useState(false);
  const [showDFF, setShowDFF] = useState(false);
  const [showDFFFilt, setShowDFFFilt] = useState(true);

  // -------- helpers & effects --------
  const debounceRef = useRef(null);
  const hasUploadedOnceRef = useRef(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(params));
    } catch {}
  }, [params]);

  const numOrNull = (v) => {
    const s = String(v ?? "").trim();
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  };

  const updateParam = (key, val) => setParams((p) => ({ ...p, [key]: val }));

  const selectAllROIs = (checked) => {
    const next = {};
    roiNames.forEach((r) => (next[r] = checked));
    setSelectedROIs(next);
    setActiveROI(checked && roiNames.length ? roiNames[0] : "");
  };

  const toggleROI = (roi, checked) => {
    setSelectedROIs((prev) => ({ ...prev, [roi]: checked }));
  };

  const onActiveROIChange = (roi) => {
    setActiveROI(roi);
    const next = {};
    roiNames.forEach((r) => (next[r] = !roi || r === roi));
    setSelectedROIs(next);
  };

  const runPipeline = async () => {
    if (!file) {
      setErrorMsg("Please choose a CSV/XLSX file.");
      return;
    }
    setErrorMsg("");
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("params", JSON.stringify(params));

      const res = await axios.post(API_URL, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const { roi_names, frames, raw, sub, dff, dff_filtered } = res.data;
      setRoiNames(roi_names || []);

      if (!hasUploadedOnceRef.current) {
        const initialSel = {};
        (roi_names || []).forEach((r) => (initialSel[r] = true));
        setSelectedROIs(initialSel);
        setActiveROI(roi_names?.[0] || "");
        hasUploadedOnceRef.current = true;
      }

      setFrames(frames || []);
      setSeriesRaw(raw || {});
      setSeriesSub(sub || {});
      setSeriesDff(dff || {});
      setSeriesDffFilt(dff_filtered || {});
    } catch (err) {
      setErrorMsg(err?.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    await runPipeline();
  };

  // Auto-recompute on param changes (after first upload)
  useEffect(() => {
    if (!file || !hasUploadedOnceRef.current) return;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(runPipeline, 350);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, activeROI]);

  const filteredROINames = useMemo(() => {
    const q = roiQuery.trim().toLowerCase();
    if (!q) return roiNames;
    return roiNames.filter((r) => r.toLowerCase().includes(q));
  }, [roiQuery, roiNames]);

  // -------- Chart data --------
  const chartData = useMemo(() => {
    const datasets = [];
    const pushSet = (dataObj, labelPrefix, hueStart) => {
      const rois = activeROI ? [activeROI] : roiNames;
      rois.forEach((roi, idx) => {
        if (!selectedROIs[roi] || !dataObj?.[roi]) return;
        datasets.push({
          label: `${labelPrefix} — ${roi}`,
          data: dataObj[roi],
          borderColor: `hsl(${(hueStart + idx * 40) % 360}, 70%, 50%)`,
          fill: false,
          pointRadius: 0,
          tension: 0.1,
        });
      });
    };

    if (showRAW) pushSet(seriesRaw, "RAW", 0);
    if (showSUB) pushSet(seriesSub, "F−F0", 120);
    if (showDFF) pushSet(seriesDff, "ΔF/F", 200);
    if (showDFFFilt) pushSet(seriesDffFilt, "ΔF/F (Filt)", 280);

    return { labels: frames, datasets };
  }, [
    frames,
    roiNames,
    selectedROIs,
    activeROI,
    showRAW,
    showSUB,
    showDFF,
    showDFFFilt,
    seriesRaw,
    seriesSub,
    seriesDff,
    seriesDffFilt,
  ]);

  const chartOptions = useMemo(() => {
    const ann = {};
    if (Number.isFinite(params.stim_frame)) {
      const xVal = params.stim_frame;
      ann.stim = {
        type: "line",
        xMin: xVal,
        xMax: xVal,
        borderColor: "rgba(0,0,0,0.6)",
        borderWidth: 1,
        borderDash: [6, 4],
        label: {
          display: true,
          content: `stim ${xVal}`,
          backgroundColor: "rgba(0,0,0,0.6)",
          color: "#fff",
          position: "start",
        },
      };
    }

    return {
      responsive: true,
      plugins: {
        legend: { position: "top" },
        title: {
          display: true,
          text: `Signal Viewer — filter=${params.filter_method} | norm=${params.normalization_mode}`,
        },
        annotation: { annotations: ann },
      },
      elements: { point: { radius: 0 } },
      interaction: { intersect: false, mode: "index" },
      scales: {
        x: { title: { display: true, text: "Frame" } },
        y: { title: { display: true, text: "Value" } },
      },
    };
  }, [params.stim_frame, params.filter_method, params.normalization_mode]);

// -------- CSV export --------
const exportCSV = () => {
  if (!frames.length) return;

  const rows = [];
  const headers = [];
  const activeSeries = [];

  if (showRAW)     activeSeries.push(["RAW",      seriesRaw]);
  if (showSUB)     activeSeries.push(["F-F0",     seriesSub]);
  if (showDFF)     activeSeries.push(["dFF",      seriesDff]);
  if (showDFFFilt) activeSeries.push(["dFF_filt", seriesDffFilt]);

  let rois = roiNames.filter((roi) => !!selectedROIs[roi]);

  if (!rois.length && activeROI) rois = [activeROI];

  if (!rois.length || !activeSeries.length) return;

  activeSeries.forEach(([prefix]) => {
    rois.forEach((roi) => {
      headers.push(`${prefix}:${roi}`);
    });
  });
  rows.push(headers.join(","));

  for (let i = 0; i < frames.length; i++) {
    const cols = [];
    activeSeries.forEach(([_, obj]) => {
      rois.forEach((roi) => {
        const val = obj?.[roi]?.[i];
        cols.push(val ?? "");
      });
    });
    rows.push(cols.join(","));
  }

  const blob = new Blob([rows.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "series_export.csv";
  a.click();
  URL.revokeObjectURL(a.href);
};


  // -------- UI --------
  return (
    <div className="page">
      <header className="page-header">
        <div className="title">
          <h2>Opcal TAU — Live Calcium Signal Processing</h2>
          <p>Upload a CSV/XLSX, choose ROI(s), set parameters. Changes auto-recompute.</p>
        </div>
      </header>

      <div className="layout">
        {/* Control panel */}
        <aside className="panel card">
          <section className="group">
            <label className="label">File (CSV/XLSX)</label>
            <input type="file" onChange={(e) => setFile(e.target.files[0] || null)} disabled={loading} />
            <button className="primary" onClick={handleUpload} disabled={loading || !file}>
              {loading ? "Running…" : "Run"}
            </button>
            {errorMsg && <div className="error">Error: {String(errorMsg)}</div>}
          </section>

          <ParamsGrid params={params} updateParam={updateParam} disabled={loading} />

          {roiNames.length > 0 && (
            <section className="group">
              <div className="row">
                <strong>ROI selection</strong>
                <div className="spacer" />
                <button onClick={() => selectAllROIs(true)} disabled={loading}>Select all</button>
                <button onClick={() => selectAllROIs(false)} disabled={loading}>None</button>
              </div>

              <input
                className="input"
                placeholder="Search ROI…"
                value={roiQuery}
                onChange={(e) => setRoiQuery(e.target.value)}
                disabled={loading}
              />

              <div className="roi-list">
                <label className="roi">
                  <input
                    type="radio"
                    name="activeROI"
                    value=""
                    checked={!activeROI}
                    onChange={() => onActiveROIChange("")}
                    disabled={loading}
                  />
                  Show all
                </label>
                {filteredROINames.map((roi) => (
                  <div className="roi-row" key={roi}>
                    <label className="roi">
                      <input
                        type="checkbox"
                        checked={!!selectedROIs[roi]}
                        onChange={(e) => toggleROI(roi, e.target.checked)}
                        disabled={loading}
                      />
                      {roi}
                    </label>
                    <label className="roi radio">
                      <input
                        type="radio"
                        name="activeROI"
                        value={roi}
                        checked={activeROI === roi}
                        onChange={() => onActiveROIChange(roi)}
                        disabled={loading}
                      />
                      Focus
                    </label>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="group row wrap">
            <label><input type="checkbox" checked={showRAW} onChange={(e) => setShowRAW(e.target.checked)} disabled={loading}/> RAW</label>
            <label><input type="checkbox" checked={showSUB} onChange={(e) => setShowSUB(e.target.checked)} disabled={loading}/> F−F0</label>
            <label><input type="checkbox" checked={showDFF} onChange={(e) => setShowDFF(e.target.checked)} disabled={loading}/> ΔF/F</label>
            <label><input type="checkbox" checked={showDFFFilt} onChange={(e) => setShowDFFFilt(e.target.checked)} disabled={loading}/> Filtered</label>
            <div className="spacer" />
            <button onClick={exportCSV} disabled={!frames.length || loading}>Export CSV</button>
          </section>
        </aside>

        {/* Chart area */}
        <main className="content card">
          {loading && <div className="loader" aria-label="loading" />}
          {frames.length > 0 ? (
            <Line data={chartData} options={chartOptions} />
          ) : (
            <div className="empty">No data yet. Upload a file and click Run.</div>
          )}
        </main>
      </div>
    </div>
  );
}

function ParamsGrid({ params, updateParam, disabled }) {
  const Field = ({ label, children }) => (
    <label className="field">
      <span className="label">{label}</span>
      {children}
    </label>
  );

  const numOrNull = (v) => {
    const s = String(v ?? "").trim();
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  };

  return (
    <section className="group grid">
      <Field label="drop_first">
        <input type="number" value={params.drop_first} onChange={(e) => updateParam("drop_first", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="stim_frame">
        <input type="number" value={params.stim_frame} onChange={(e) => updateParam("stim_frame", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="baseline_mode">
        <select value={params.baseline_mode} onChange={(e) => updateParam("baseline_mode", e.target.value)} disabled={disabled}>
          <option>pre_stim_median</option>
          <option>global_median</option>
          <option>global_percentile</option>
          <option>rolling_median</option>
          <option>rolling_percentile</option>
          <option>rolling_mean</option>
        </select>
      </Field>

      <Field label="pre_window">
        <input type="number" value={params.pre_window} onChange={(e) => updateParam("pre_window", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="rolling_window">
        <input type="number" value={params.rolling_window} onChange={(e) => updateParam("rolling_window", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="baseline_rolling_window (optional)">
        <input
          type="number"
          placeholder="inherit from rolling_window"
          value={params.baseline_rolling_window ?? ""}
          onChange={(e) => updateParam("baseline_rolling_window", numOrNull(e.target.value))}
          disabled={disabled}
        />
      </Field>

      <Field label="detrend_rolling_window (optional)">
        <input
          type="number"
          placeholder="inherit from rolling_window"
          value={params.detrend_rolling_window ?? ""}
          onChange={(e) => updateParam("detrend_rolling_window", numOrNull(e.target.value))}
          disabled={disabled}
        />
      </Field>

      <Field label="global_percentile_q">
        <input type="number" step="0.1" value={params.global_percentile_q} onChange={(e) => updateParam("global_percentile_q", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="rolling_percentile_q">
        <input type="number" step="0.1" value={params.rolling_percentile_q} onChange={(e) => updateParam("rolling_percentile_q", +e.target.value)} disabled={disabled} />
      </Field>

      <Field label="detrend">
        <select value={params.detrend} onChange={(e) => updateParam("detrend", e.target.value)} disabled={disabled}>
          <option>none</option>
          <option>rolling_median</option>
          <option>linear</option>
        </select>
      </Field>

      <Field label="normalization_mode">
        <select value={params.normalization_mode} onChange={(e) => updateParam("normalization_mode", e.target.value)} disabled={disabled}>
          <option value="dff">dff</option>
          <option value="subtract">subtract</option>
        </select>
      </Field>

      <Field label="filter_method">
        <select value={params.filter_method} onChange={(e) => updateParam("filter_method", e.target.value)} disabled={disabled}>
          <option>savgol</option>
          <option>gaussian</option>
        </select>
      </Field>

      <Field label="gaussian_sigma">
        <input type="number" step="0.1" value={params.gaussian_sigma} onChange={(e) => updateParam("gaussian_sigma", +e.target.value)} disabled={disabled || params.filter_method !== "gaussian"} />
      </Field>

      <Field label="savgol_window">
        <input type="number" value={params.savgol_window} onChange={(e) => updateParam("savgol_window", +e.target.value)} disabled={disabled || params.filter_method !== "savgol"} />
      </Field>

      <Field label="savgol_poly">
        <input type="number" value={params.savgol_poly} onChange={(e) => updateParam("savgol_poly", +e.target.value)} disabled={disabled || params.filter_method !== "savgol"} />
      </Field>
    </section>
  );
}
