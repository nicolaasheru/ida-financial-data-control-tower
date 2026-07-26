"use client";

import { useEffect, useMemo, useState } from "react";

type Alert = {
  row_id: string;
  record_key: string;
  country: string;
  region: string;
  category: string;
  period_type: string;
  time_period: string;
  severity: "critical" | "high" | "medium";
  reason_codes: string;
  detectors: string;
  detector_count: string;
  corroborated: string;
  anomaly_score: string;
  current_amount_usd_m: string;
  comparison_amount_usd_m: string;
  change_amount_usd_m: string;
  change_percent: string;
  materiality_percentile: string;
  materiality_band: string;
  messages: string;
  evidence: string;
  recommended_actions: string;
  review_status: string;
  review_outcome: string;
  review_confidence: string;
  review_notes: string;
  evidence_url: string;
};

type RunSummary = {
  run_timestamp_utc: string;
  source_records: number;
  countries: number;
  periods: number;
  alerts: number;
  corroborated_alerts: number;
  reviewed_alerts: number;
  resolved_alerts: number;
  alerts_by_severity: Record<string, number>;
  alerts_by_detector: Record<string, number>;
};

type EvaluationSummary = {
  injections: number;
  fully_detected: number;
  seed_runs: number;
  trials: number;
  detected_trials: number;
  minimum_seed_recall: number;
  recall_by_layer: Record<string, number>;
  method_note: string;
};

type ReviewSummary = {
  sample_size: number;
  reviewed: number;
  resolved: number;
  legitimate_exceptions: number;
  needs_more_information: number;
  minimum_resolved_for_rate: number;
};

type ReviewRecord = {
  record_key: string;
  row_id: number;
  review_status: "pending" | "in_review" | "resolved";
  review_outcome: string;
  reviewer: string;
  review_notes: string;
  reviewed_at: string;
  review_confidence: string;
  evidence_url: string;
  version: number;
};

type ReviewEvent = {
  event_id: number;
  record_key: string;
  previous_status: string;
  new_status: string;
  previous_outcome: string;
  new_outcome: string;
  actor: string;
  event_note: string;
  created_at: string;
  resulting_version: number;
};

const REVIEW_API_URL =
  process.env.NEXT_PUBLIC_REVIEW_API_URL ?? "http://localhost:8000";
const number = new Intl.NumberFormat("en-US");
const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function parseCsv(text: string): Alert[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === '"' && quoted && text[i + 1] === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      row.push(cell);
      if (row.some(Boolean)) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  const [headers, ...values] = rows;
  return values.map((valuesRow) =>
    Object.fromEntries(headers.map((key, index) => [key, valuesRow[index] ?? ""])),
  ) as Alert[];
}

function formatMoney(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${money.format(parsed)}M` : "—";
}

function formatPercent(value: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "—";
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${(parsed * 100).toFixed(Math.abs(parsed) >= 10 ? 0 : 1)}%`;
}

function label(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function split(value: string) {
  return value.split(" | ").filter(Boolean);
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [run, setRun] = useState<RunSummary | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationSummary | null>(null);
  const [review, setReview] = useState<ReviewSummary | null>(null);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [period, setPeriod] = useState("all");
  const [reviewStatus, setReviewStatus] = useState("all");
  const [selectedId, setSelectedId] = useState("");
  const [sort, setSort] = useState<"priority" | "materiality" | "amount">("priority");
  const [panel, setPanel] = useState<"alerts" | "quality">("alerts");
  const [liveReview, setLiveReview] = useState<ReviewRecord | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewEvent[]>([]);
  const [reviewApiStatus, setReviewApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const [dataLoadError, setDataLoadError] = useState(false);
  const [reviewForm, setReviewForm] = useState({
    review_outcome: "",
    reviewer: "",
    review_notes: "",
    review_confidence: "",
    evidence_url: "",
  });

  useEffect(() => {
    Promise.all([
      fetch("/data/alerts.csv").then((response) => response.text()),
      fetch("/data/run_summary.json").then((response) => response.json()),
      fetch("/data/evaluation_summary.json").then((response) => response.json()),
      fetch("/data/review_summary.json").then((response) => response.json()),
      fetch(`${REVIEW_API_URL}/api/reviews`)
        .then((response) => {
          if (!response.ok) throw new Error("Review API unavailable");
          return response.json() as Promise<ReviewRecord[]>;
        })
        .catch(() => [] as ReviewRecord[]),
    ])
      .then(([csv, runData, evaluationData, reviewData, persistedReviews]) => {
        const parsed = parseCsv(csv);
        const reviewsById = new Map(
          persistedReviews.map((record) => [record.record_key, record]),
        );
        const hydrated = parsed.map((alert) => {
          const persisted = reviewsById.get(alert.record_key);
          return persisted
            ? {
                ...alert,
                review_status: persisted.review_status,
                review_outcome: persisted.review_outcome,
                reviewer: persisted.reviewer,
                review_notes: persisted.review_notes,
                reviewed_at: persisted.reviewed_at,
                review_confidence: persisted.review_confidence,
                evidence_url: persisted.evidence_url,
              }
            : alert;
        });
        setAlerts(hydrated);
        setSelectedId(hydrated[0]?.record_key ?? "");
        setRun(runData);
        setEvaluation(evaluationData);
        setReview(reviewData);
        setDataLoadError(false);
      })
      .catch(() => setDataLoadError(true));
  }, []);

  const filtered = useMemo(() => {
    const priority = { critical: 3, high: 2, medium: 1 };
    return alerts
      .filter((alert) => severity === "all" || alert.severity === severity)
      .filter((alert) => period === "all" || alert.period_type === period)
      .filter((alert) => reviewStatus === "all" || alert.review_status === reviewStatus)
      .filter((alert) => {
        const search = `${alert.country} ${alert.region} ${alert.category} ${alert.reason_codes}`.toLowerCase();
        return search.includes(query.toLowerCase());
      })
      .sort((a, b) => {
        if (sort === "materiality") {
          return Number(b.materiality_percentile) - Number(a.materiality_percentile);
        }
        if (sort === "amount") {
          return Math.abs(Number(b.current_amount_usd_m)) - Math.abs(Number(a.current_amount_usd_m));
        }
        return (
          priority[b.severity] - priority[a.severity] ||
          Number(b.corroborated === "True") - Number(a.corroborated === "True") ||
          Number(b.materiality_percentile) - Number(a.materiality_percentile)
        );
      });
  }, [alerts, severity, period, reviewStatus, query, sort]);

  const selected =
    alerts.find((alert) => alert.record_key === selectedId) ?? filtered[0];

  useEffect(() => {
    if (!selected) return;
    let active = true;
    Promise.all([
      fetch(`${REVIEW_API_URL}/api/reviews/${selected.record_key}`).then((response) => {
        if (!response.ok) throw new Error("Review API unavailable");
        return response.json();
      }),
      fetch(`${REVIEW_API_URL}/api/reviews/${selected.record_key}/history`).then((response) => {
        if (!response.ok) throw new Error("Review history unavailable");
        return response.json();
      }),
    ])
      .then(([record, history]: [ReviewRecord, ReviewEvent[]]) => {
        if (!active) return;
        setLiveReview(record);
        setReviewHistory(history);
        setReviewForm({
          review_outcome: record.review_outcome,
          reviewer: record.reviewer,
          review_notes: record.review_notes,
          review_confidence: record.review_confidence,
          evidence_url: record.evidence_url,
        });
        setReviewError("");
        setReviewApiStatus("online");
      })
      .catch(() => {
        if (!active) return;
        setLiveReview(null);
        setReviewHistory([]);
        setReviewForm({
          review_outcome: selected.review_outcome || "",
          reviewer: selected.reviewer || "",
          review_notes: selected.review_notes || "",
          review_confidence: selected.review_confidence || "",
          evidence_url: selected.evidence_url || "",
        });
        setReviewError("");
        setReviewApiStatus("offline");
      });
    return () => {
      active = false;
    };
  }, [selected]);

  async function saveReview(targetStatus: "in_review" | "resolved") {
    if (!selected || !liveReview) return;
    setReviewSaving(true);
    setReviewError("");
    const isFinalOutcome = [
      "confirmed_data_issue",
      "legitimate_exception",
      "false_positive",
    ].includes(reviewForm.review_outcome);
    const payload = {
      ...reviewForm,
      review_status: targetStatus,
      review_outcome:
        targetStatus === "in_review" && isFinalOutcome
          ? ""
          : reviewForm.review_outcome,
      expected_version: liveReview.version,
    };
    try {
      const response = await fetch(`${REVIEW_API_URL}/api/reviews/${selected.record_key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: "Unable to save review" }));
        throw new Error(body.detail ?? "Unable to save review");
      }
      const updated: ReviewRecord = await response.json();
      setLiveReview(updated);
      setReviewForm({
        review_outcome: updated.review_outcome,
        reviewer: updated.reviewer,
        review_notes: updated.review_notes,
        review_confidence: updated.review_confidence,
        evidence_url: updated.evidence_url,
      });
      setAlerts((current) =>
        current.map((alert) =>
          alert.record_key === selected.record_key
            ? {
                ...alert,
                review_status: updated.review_status,
                review_outcome: updated.review_outcome,
                reviewer: updated.reviewer,
                review_notes: updated.review_notes,
                reviewed_at: updated.reviewed_at,
                review_confidence: updated.review_confidence,
                evidence_url: updated.evidence_url,
              }
            : alert,
        ),
      );
      const historyResponse = await fetch(
        `${REVIEW_API_URL}/api/reviews/${selected.record_key}/history`,
      );
      if (historyResponse.ok) setReviewHistory(await historyResponse.json());
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Unable to save review");
    } finally {
      setReviewSaving(false);
    }
  }
  const liveReviewSummary = useMemo(() => {
    const resolved = alerts.filter((alert) => alert.review_status === "resolved").length;
    const reviewed = alerts.filter((alert) => alert.review_status !== "pending").length;
    const open = alerts.length - resolved;
    const sampleSize = Math.max(review?.sample_size ?? 0, reviewed);
    const openBySeverity = alerts
      .filter((alert) => alert.review_status !== "resolved")
      .reduce(
        (counts, alert) => {
          counts[alert.severity] += 1;
          return counts;
        },
        { critical: 0, high: 0, medium: 0 },
      );
    return {
      open,
      resolved,
      reviewed,
      sampleSize,
      openBySeverity,
      legitimateExceptions: alerts.filter(
        (alert) => alert.review_outcome === "legitimate_exception",
      ).length,
      needsMoreInformation: alerts.filter(
        (alert) => alert.review_outcome === "needs_more_information",
      ).length,
    };
  }, [alerts, review]);
  const resolvedRate = liveReviewSummary.sampleSize
    ? Math.round((liveReviewSummary.resolved / liveReviewSummary.sampleSize) * 100)
    : 0;
  const runAgeDays = run
    ? (Date.now() - new Date(run.run_timestamp_utc).getTime()) / 86_400_000
    : null;
  const pipelineState = dataLoadError
    ? { label: "Data unavailable", tone: "error" }
    : runAgeDays === null
      ? { label: "Loading run metadata", tone: "loading" }
      : runAgeDays > 7
        ? { label: "Pipeline snapshot stale", tone: "stale" }
        : { label: "Latest run available", tone: "healthy" };
  const totalSignals = run
    ? Object.values(run.alerts_by_detector).reduce((sum, current) => sum + current, 0)
    : 0;
  const trendData = useMemo(() => {
    const periods = new Map<string, { critical: number; high: number; medium: number }>();
    alerts
      .filter((alert) => alert.period_type === "annual")
      .forEach((alert) => {
        const current = periods.get(alert.time_period) ?? { critical: 0, high: 0, medium: 0 };
        current[alert.severity] += 1;
        periods.set(alert.time_period, current);
      });
    return [...periods.entries()]
      .sort(([a], [b]) => Number(a.replace("FY", "")) - Number(b.replace("FY", "")))
      .map(([name, values]) => ({ name, ...values, total: values.critical + values.high + values.medium }));
  }, [alerts]);

  const regionalData = useMemo(() => {
    const regions = new Map<string, { critical: number; high: number; amount: number }>();
    alerts.forEach((alert) => {
      const current = regions.get(alert.region) ?? { critical: 0, high: 0, amount: 0 };
      if (alert.severity === "critical") current.critical += 1;
      if (alert.severity === "high") current.high += 1;
      if (alert.severity !== "medium") current.amount += Math.abs(Number(alert.current_amount_usd_m) || 0);
      regions.set(alert.region, current);
    });
    return [...regions.entries()]
      .map(([name, values]) => ({ name, ...values, total: values.critical + values.high }))
      .filter((item) => item.total > 0)
      .sort((a, b) => b.total - a.total || b.amount - a.amount)
      .slice(0, 6);
  }, [alerts]);

  const agreementData = useMemo(() => {
    const groups = new Map<string, number>();
    alerts.forEach((alert) => {
      const detectors = split(alert.detectors);
      let group = "Other combination";
      if (detectors.length === 1) {
        if (detectors[0] === "rule") group = "Rule only";
        else if (detectors[0] === "statistical_process_control") group = "Statistical only";
        else if (detectors[0] === "isolation_forest") group = "ML only";
      } else {
        const hasRule = detectors.includes("rule");
        const hasStat = detectors.includes("statistical_process_control");
        const hasMl = detectors.includes("isolation_forest");
        if (hasStat && hasMl && !hasRule) group = "Statistical + ML";
        else if (hasRule) group = "Rule + another";
      }
      groups.set(group, (groups.get(group) ?? 0) + 1);
    });
    const order = ["Rule only", "Statistical only", "ML only", "Statistical + ML", "Rule + another", "Other combination"];
    return order
      .map((name) => ({ name, value: groups.get(name) ?? 0 }))
      .filter((item) => item.value > 0);
  }, [alerts]);

  const maxTrend = Math.max(...trendData.map((item) => item.total), 1);
  const maxRegion = Math.max(...regionalData.map((item) => item.total), 1);
  const maxAgreement = Math.max(...agreementData.map((item) => item.value), 1);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">IDA</div>
          <div>
            <strong>Control Tower</strong>
            <span>Financial data assurance</span>
          </div>
        </div>
        <nav>
          <button className={panel === "alerts" ? "active" : ""} onClick={() => setPanel("alerts")}>
            <span>⌁</span> Alert operations
            <b>{alerts.length ? liveReviewSummary.open : "—"}</b>
          </button>
          <button className={panel === "quality" ? "active" : ""} onClick={() => setPanel("quality")}>
            <span>◫</span> Model & data quality
          </button>
        </nav>
        <div className="sidebar-section">
          <p>Data source</p>
          <strong>IDA Commitments & Disbursements</strong>
          <span>DS01557 · USD millions</span>
        </div>
        <div className="sidebar-section methodology">
          <p>Control layers</p>
          <span><i className="rule-dot" /> Financial rules</span>
          <span><i className="stat-dot" /> Statistical process control</span>
          <span><i className="ml-dot" /> Isolation Forest</span>
        </div>
        <div className="disclaimer">
          Independent prototype using public WBG data. Not an official World Bank system.
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">IDA financial operations</p>
            <h1>
              {panel === "alerts"
                ? "Financial integrity, at development scale."
                : "Transparent controls. Accountable models."}
            </h1>
            <p className="mission-line">
              {panel === "alerts"
                ? "Monitor commitments and disbursements before unusual records reach downstream reporting."
                : "Evaluate how data, rules, statistics, and machine learning work together to protect report quality."}
            </p>
          </div>
          <div className={`run-status ${pipelineState.tone}`}>
            <i />
            <div>
              <strong>{pipelineState.label}</strong>
              <span>
                Updated {run ? new Date(run.run_timestamp_utc).toLocaleString("en-US", {
                  month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                }) : "—"} UTC
              </span>
            </div>
          </div>
        </header>

        {panel === "alerts" ? (
          <>
            <section className="metrics">
              <article className="metric primary">
                <span>Records monitored</span>
                <strong>{run ? number.format(run.source_records) : "—"}</strong>
                <small>
                  {run
                    ? `${number.format(run.periods)} reporting periods · ${number.format(run.countries)} entities`
                    : "Dataset coverage unavailable"}
                </small>
              </article>
              <article className="metric">
                <span>Open alerts</span>
                <strong>{alerts.length ? liveReviewSummary.open : "—"}</strong>
                <div className="severity-strip">
                  <i className="critical" style={{ flex: liveReviewSummary.openBySeverity.critical }} />
                  <i className="high" style={{ flex: liveReviewSummary.openBySeverity.high }} />
                  <i className="medium" style={{ flex: liveReviewSummary.openBySeverity.medium }} />
                </div>
                <small>
                  <b className="critical-text">{alerts.length ? liveReviewSummary.openBySeverity.critical : "—"} critical</b>
                  {" · "}{alerts.length ? liveReviewSummary.openBySeverity.high : "—"} high
                </small>
              </article>
              <article className="metric">
                <span>Corroborated</span>
                <strong>{run?.corroborated_alerts ?? "—"}</strong>
                <small>Flagged by 2+ detector families</small>
              </article>
              <article className="metric">
                <span>Review progress</span>
                <div className="progress-value">
                  <strong>{alerts.length ? liveReviewSummary.resolved : "—"}</strong>
                  <em>of {alerts.length ? liveReviewSummary.sampleSize : "—"} reviewed sample</em>
                </div>
                <div className="progress"><i style={{ width: `${resolvedRate}%` }} /></div>
                <small>{alerts.length ? liveReviewSummary.needsMoreInformation : "—"} need more information</small>
              </article>
            </section>

            <section className="visual-grid">
              <article className="visual-card trend-card">
                <div className="visual-heading">
                  <div>
                    <p className="eyebrow">Alert trend</p>
                    <h2>Where exceptions concentrate over time</h2>
                  </div>
                  <div className="chart-legend">
                    <span><i className="critical-key" /> Critical</span>
                    <span><i className="high-key" /> High</span>
                    <span><i className="medium-key" /> Medium</span>
                  </div>
                </div>
                <div className="stacked-chart">
                  {trendData.map((item) => (
                    <div className="stack-column" key={item.name}>
                      <div className="stack-value">{item.total}</div>
                      <div className="stack-track">
                        <div
                          className="stack critical-stack"
                          style={{ height: `${(item.critical / maxTrend) * 100}%` }}
                          title={`${item.critical} critical`}
                        />
                        <div
                          className="stack high-stack"
                          style={{ height: `${(item.high / maxTrend) * 100}%` }}
                          title={`${item.high} high`}
                        />
                        <div
                          className="stack medium-stack"
                          style={{ height: `${(item.medium / maxTrend) * 100}%` }}
                          title={`${item.medium} medium`}
                        />
                      </div>
                      <span>{item.name}</span>
                    </div>
                  ))}
                </div>
                <p className="chart-note">Annual observations only · alert count, not financial loss</p>
              </article>

              <article className="visual-card region-card">
                <div className="visual-heading">
                  <div>
                    <p className="eyebrow">Geographic concentration</p>
                    <h2>Priority alerts by region</h2>
                  </div>
                  <span className="chart-unit">Critical + high</span>
                </div>
                <div className="region-bars">
                  {regionalData.map((item) => (
                    <div className="region-row" key={item.name}>
                      <span title={item.name}>{item.name}</span>
                      <div className="region-track">
                        <i className="critical-region" style={{ width: `${(item.critical / maxRegion) * 100}%` }} />
                        <i className="high-region" style={{ width: `${(item.high / maxRegion) * 100}%` }} />
                      </div>
                      <strong>{item.total}</strong>
                      <small>{formatMoney(String(item.amount))}</small>
                    </div>
                  ))}
                </div>
              </article>

              <article className="visual-card agreement-card">
                <div className="visual-heading">
                  <div>
                    <p className="eyebrow">Detector agreement</p>
                    <h2>How independent controls intersect</h2>
                  </div>
                  <strong className="highlight-number">{run?.corroborated_alerts ?? "—"} corroborated</strong>
                </div>
                <div className="agreement-bars">
                  {agreementData.map((item) => (
                    <div key={item.name} className={item.name.includes("+") ? "agreed" : ""}>
                      <span>{item.name}</span>
                      <div><i style={{ width: `${(item.value / maxAgreement) * 100}%` }} /></div>
                      <strong>{item.value}</strong>
                    </div>
                  ))}
                </div>
                <p className="chart-note">Corroboration means at least two detector families flagged the same record.</p>
              </article>

              <article className="visual-card funnel-card">
                <div className="visual-heading">
                  <div>
                    <p className="eyebrow">Review funnel</p>
                    <h2>From detection to disposition</h2>
                  </div>
                  <span className="chart-unit">Current review cycle</span>
                </div>
                <div className="funnel">
                  <div className="funnel-step">
                    <strong>{run?.alerts ?? "—"}</strong>
                    <span>Alerts generated</span>
                  </div>
                  <b>→</b>
                  <div className="funnel-step sampled">
                    <strong>{review?.sample_size ?? "—"}</strong>
                    <span>Sampled for review</span>
                  </div>
                  <b>→</b>
                  <div className="funnel-step resolved">
                    <strong>{alerts.length ? liveReviewSummary.resolved : "—"}</strong>
                    <span>Cases resolved</span>
                  </div>
                </div>
                <div className="funnel-outcomes">
                  <div>
                    <i className="legitimate-outcome" />
                    <span>Legitimate exceptions</span>
                    <strong>{alerts.length ? liveReviewSummary.legitimateExceptions : "—"}</strong>
                  </div>
                  <div>
                    <i className="unresolved-outcome" />
                    <span>Need more information</span>
                    <strong>{alerts.length ? liveReviewSummary.needsMoreInformation : "—"}</strong>
                  </div>
                </div>
                <p className="chart-note">Precision rates remain suppressed until 10 cases are resolved.</p>
              </article>
            </section>

            <section className="operations">
              <div className="queue-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Prioritized queue</p>
                    <h2>Alerts requiring review</h2>
                  </div>
                  <span>{filtered.length} results</span>
                </div>
                <div className="filters">
                  <label className="search">
                    <span>⌕</span>
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search country, region or reason"
                    />
                  </label>
                  <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
                    <option value="all">All severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                  </select>
                  <select value={period} onChange={(event) => setPeriod(event.target.value)}>
                    <option value="all">All periods</option>
                    <option value="annual">Annual</option>
                    <option value="quarterly">Quarterly</option>
                  </select>
                  <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
                    <option value="all">All review states</option>
                    <option value="pending">Pending</option>
                    <option value="in_review">In review</option>
                    <option value="resolved">Resolved</option>
                  </select>
                  <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}>
                    <option value="priority">Sort: priority</option>
                    <option value="materiality">Sort: materiality</option>
                    <option value="amount">Sort: amount</option>
                  </select>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Severity</th>
                        <th>Entity / period</th>
                        <th>Current</th>
                        <th>Change</th>
                        <th>Why flagged</th>
                        <th>Review</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.slice(0, 80).map((alert) => (
                        <tr
                          key={alert.record_key}
                          className={selected?.record_key === alert.record_key ? "selected" : ""}
                          onClick={() => setSelectedId(alert.record_key)}
                        >
                          <td><span className={`severity-pill ${alert.severity}`}>{alert.severity}</span></td>
                          <td>
                            <strong>{alert.country}</strong>
                            <span>{alert.time_period} · {alert.category}</span>
                          </td>
                          <td><strong>{formatMoney(alert.current_amount_usd_m)}</strong></td>
                          <td>
                            <strong className={Number(alert.change_percent) >= 0 ? "up" : "down"}>
                              {formatPercent(alert.change_percent)}
                            </strong>
                            <span>vs. {formatMoney(alert.comparison_amount_usd_m)}</span>
                          </td>
                          <td>
                            <span className="reason">{split(alert.reason_codes)[0]?.replaceAll("_", " ")}</span>
                            {alert.corroborated === "True" && <span className="corroborated">2+ controls</span>}
                          </td>
                          <td><span className={`review-state ${alert.review_status}`}>{label(alert.review_status)}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {selected && (
                <aside className="detail-panel">
                  <div className="detail-top">
                    <span className={`severity-pill ${selected.severity}`}>{selected.severity}</span>
                    <button aria-label="Close selection" onClick={() => setSelectedId("")}>×</button>
                  </div>
                  <p className="eyebrow">Alert #{selected.row_id}</p>
                  <h2>{selected.country}</h2>
                  <p className="detail-subtitle">{selected.region} · {selected.time_period} · {selected.category}</p>

                  <div className="amount-comparison">
                    <div>
                      <span>Current amount</span>
                      <strong>{formatMoney(selected.current_amount_usd_m)}</strong>
                    </div>
                    <div className="change-arrow">→</div>
                    <div>
                      <span>Comparable prior</span>
                      <strong>{formatMoney(selected.comparison_amount_usd_m)}</strong>
                    </div>
                    <b className={Number(selected.change_percent) >= 0 ? "up" : "down"}>
                      {formatPercent(selected.change_percent)}
                    </b>
                  </div>

                  <section className="detail-section">
                    <h3>Why this was flagged</h3>
                    <div className="reason-list">
                      {split(selected.reason_codes).map((reason, index) => (
                        <article key={reason}>
                          <i>{index + 1}</i>
                          <div>
                            <strong>{label(reason)}</strong>
                            <span>{split(selected.messages)[index] ?? selected.messages}</span>
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>

                  <section className="detail-section">
                    <div className="section-title">
                      <h3>Control evidence</h3>
                      {selected.corroborated === "True" && <span className="corroborated">Corroborated</span>}
                    </div>
                    <div className="evidence-box">
                      {split(selected.evidence).map((item) => <p key={item}>{item}</p>)}
                    </div>
                    <div className="mini-metrics">
                      <div>
                        <span>ML score</span>
                        <strong>{selected.anomaly_score ? Number(selected.anomaly_score).toFixed(2) : "N/A"}</strong>
                      </div>
                      <div>
                        <span>Materiality</span>
                        <strong>{Math.round(Number(selected.materiality_percentile) * 100)}th pct.</strong>
                      </div>
                      <div>
                        <span>Detectors</span>
                        <strong>{selected.detector_count}</strong>
                      </div>
                    </div>
                  </section>

                  <section className="detail-section">
                    <h3>Recommended action</h3>
                    <p className="recommended">{split(selected.recommended_actions)[0]}</p>
                  </section>

                  <section className="review-card">
                    <div className="section-title">
                      <h3>Analyst review</h3>
                      <div className="review-card-status">
                        <span className={`api-state ${reviewApiStatus}`}>
                          {reviewApiStatus === "online" ? "Live" : reviewApiStatus === "offline" ? "Read only" : "Connecting"}
                        </span>
                        <span className={`review-state ${liveReview?.review_status ?? selected.review_status}`}>
                          {label(liveReview?.review_status ?? selected.review_status)}
                        </span>
                      </div>
                    </div>
                    {reviewApiStatus === "offline" ? (
                      selected.review_notes ? (
                      <>
                        <p>{selected.review_notes}</p>
                        <div className="review-meta">
                          <span>Outcome <strong>{label(selected.review_outcome)}</strong></span>
                          <span>Confidence <strong>{label(selected.review_confidence)}</strong></span>
                        </div>
                        {selected.evidence_url && (
                          <a href={selected.evidence_url} target="_blank" rel="noreferrer">Open supporting evidence ↗</a>
                        )}
                      </>
                      ) : (
                        <p>No review has been recorded. Start the review API to enable analyst updates.</p>
                      )
                    ) : liveReview ? (
                      <div className="review-editor">
                        <label>
                          Reviewer
                          <input
                            value={reviewForm.reviewer}
                            onChange={(event) => setReviewForm({ ...reviewForm, reviewer: event.target.value })}
                            placeholder="Analyst name"
                          />
                        </label>
                        {liveReview.review_status !== "pending" && (
                          <>
                            <div className="review-editor-grid">
                              <label>
                                Outcome
                                <select
                                  value={reviewForm.review_outcome}
                                  onChange={(event) => setReviewForm({ ...reviewForm, review_outcome: event.target.value })}
                                >
                                  <option value="">No outcome selected</option>
                                  <option value="needs_more_information">Needs more information</option>
                                  <option value="confirmed_data_issue">Confirmed data issue</option>
                                  <option value="legitimate_exception">Legitimate exception</option>
                                  <option value="false_positive">False positive</option>
                                </select>
                              </label>
                              <label>
                                Confidence
                                <select
                                  value={reviewForm.review_confidence}
                                  onChange={(event) => setReviewForm({ ...reviewForm, review_confidence: event.target.value })}
                                >
                                  <option value="">Not selected</option>
                                  <option value="high">High</option>
                                  <option value="medium">Medium</option>
                                  <option value="low">Low</option>
                                </select>
                              </label>
                            </div>
                            <label>
                              Review notes
                              <textarea
                                value={reviewForm.review_notes}
                                onChange={(event) => setReviewForm({ ...reviewForm, review_notes: event.target.value })}
                                placeholder="Document the evidence and analytical judgment."
                              />
                            </label>
                            <label>
                              Evidence URL
                              <input
                                type="url"
                                value={reviewForm.evidence_url}
                                onChange={(event) => setReviewForm({ ...reviewForm, evidence_url: event.target.value })}
                                placeholder="https://"
                              />
                            </label>
                          </>
                        )}
                        {reviewError && <p className="review-error">{reviewError}</p>}
                        <div className="review-actions">
                          {liveReview.review_status === "pending" ? (
                            <button
                              disabled={reviewSaving || !reviewForm.reviewer.trim()}
                              onClick={() => saveReview("in_review")}
                            >
                              Begin review
                            </button>
                          ) : liveReview.review_status === "resolved" ? (
                            <button
                              disabled={reviewSaving || !reviewForm.reviewer.trim()}
                              onClick={() => saveReview("in_review")}
                            >
                              Reopen review
                            </button>
                          ) : (
                            <>
                              <button
                                className="secondary"
                                disabled={reviewSaving || !reviewForm.reviewer.trim()}
                                onClick={() => saveReview("in_review")}
                              >
                                Save progress
                              </button>
                              <button
                                disabled={
                                  reviewSaving ||
                                  !reviewForm.reviewer.trim() ||
                                  !reviewForm.review_notes.trim() ||
                                  !reviewForm.review_confidence ||
                                  !["confirmed_data_issue", "legitimate_exception", "false_positive"].includes(reviewForm.review_outcome)
                                }
                                onClick={() => saveReview("resolved")}
                              >
                                Resolve alert
                              </button>
                            </>
                          )}
                        </div>
                        {reviewHistory.length > 0 && (
                          <div className="audit-history">
                            <strong>Audit history</strong>
                            {reviewHistory.slice(0, 4).map((event) => (
                              <div key={event.event_id}>
                                <span>{event.actor}</span>
                                <p>{label(event.previous_status)} → {label(event.new_status)}</p>
                                <time>{new Date(event.created_at).toLocaleString()}</time>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p>Connecting to the review service…</p>
                    )}
                  </section>
                </aside>
              )}
            </section>
          </>
        ) : (
          <section className="quality-grid">
            <article className="quality-card hero-quality">
              <p className="eyebrow">Controlled fault injection</p>
              <h2>{evaluation?.fully_detected ?? "—"} of {evaluation?.injections ?? "—"} scenarios detected</h2>
              <p className="evaluation-scope">
                {evaluation
                  ? `${evaluation.detected_trials} of ${evaluation.trials} seeded trials · ${Math.round(evaluation.minimum_seed_recall * 100)}% minimum run recall`
                  : "Loading robustness evidence…"}
              </p>
              <p>{evaluation?.method_note}</p>
              <div className="layer-list">
                {evaluation && Object.entries(evaluation.recall_by_layer).map(([layer, recall]) => (
                  <div key={layer}>
                    <span>{label(layer)}</span>
                    <div><i style={{ width: `${recall * 100}%` }} /></div>
                    <strong>{Math.round(recall * 100)}%</strong>
                  </div>
                ))}
              </div>
            </article>
            <article className="quality-card">
              <p className="eyebrow">Detector signal mix</p>
              <h2>{totalSignals} signals</h2>
              <div className="detector-bars">
                {run && Object.entries(run.alerts_by_detector).map(([detector, count]) => (
                  <div key={detector}>
                    <span>{label(detector)}</span>
                    <div><i style={{ width: `${(count / totalSignals) * 100}%` }} /></div>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </article>
            <article className="quality-card">
              <p className="eyebrow">Review evidence</p>
              <h2>{alerts.length ? liveReviewSummary.resolved : "—"} cases resolved</h2>
              <p>
                Precision and false-positive rates remain suppressed until at least{" "}
                {review?.minimum_resolved_for_rate ?? "—"} cases are resolved.
              </p>
              <div className="review-breakdown">
                <span><i className="legitimate" /> {alerts.length ? liveReviewSummary.legitimateExceptions : "—"} legitimate exceptions</span>
                <span><i className="unresolved" /> {alerts.length ? liveReviewSummary.needsMoreInformation : "—"} need more information</span>
              </div>
            </article>
            <article className="quality-card">
              <p className="eyebrow">Current model design</p>
              <h2>Segmented, interpretable controls</h2>
              <ul>
                <li>Annual and quarterly observations modeled separately</li>
                <li>Commitments and disbursements modeled separately</li>
                <li>Country ML models separated from institutional aggregates</li>
                <li>ML-only alerts cannot receive critical severity</li>
              </ul>
            </article>
          </section>
        )}
        <footer className="creator-footer">
          <div className="creator-signature">
            <span className="creator-mark">N/D</span>
            <div>
              <strong>Designed & engineered by Nicolaas</strong>
              <span>Independent financial data engineering prototype</span>
            </div>
          </div>
          <div className="creator-links">
            <a
              href="https://linkedin.com/in/nicolaasheru"
              target="_blank"
              rel="noreferrer"
            >
              LinkedIn ↗
            </a>
            <a href="mailto:nicolaasherud@gmail.com">
              nicolaasherud@gmail.com
            </a>
          </div>
          <span className="creator-watermark" aria-hidden="true">NICOLAAS</span>
        </footer>
      </section>
    </main>
  );
}
