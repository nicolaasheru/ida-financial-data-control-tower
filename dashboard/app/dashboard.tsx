"use client";

import { useEffect, useMemo, useState } from "react";

const PAGE_LOADED_AT = Date.now();

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
  reviewer: string;
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
  model_run: {
    algorithm: string;
    segments: string;
    features: string[];
    n_estimators: number;
    contamination: number;
    random_state: number;
    score_scope: string;
  };
};

type EvaluationSummary = {
  injections: number;
  fully_detected: number;
  seed_runs: number;
  trials: number;
  detected_trials: number;
  minimum_seed_recall: number;
  seeds: number[];
  recall_by_seed: Record<string, number>;
  recall_by_scenario: Record<string, number>;
  recall_by_layer: Record<string, number>;
  outcomes: Array<{
    seed: number;
    injection: string;
    detected: boolean;
  }>;
  sensitivity_analysis: {
    operating_contamination: number;
    status: string;
    grid: Array<{
      contamination: number;
      ml_alerts: number;
      total_alerts: number;
      alert_rate: number;
      controlled_fault_recall: number;
      ml_spike_recall: number;
      moderate_spike_recall: number;
      severe_spike_recall: number;
      selected: boolean;
      alert_change_vs_selected: number;
    }>;
    selection_rationale: string;
    method_note: string;
  };
  method_note: string;
};

type ReviewSummary = {
  sample_size: number;
  reviewed: number;
  resolved: number;
  confirmed_data_issues: number;
  legitimate_exceptions: number;
  false_positives: number;
  needs_more_information: number;
  minimum_resolved_for_rate: number;
  actionable_precision: number | null;
  false_positive_rate: number | null;
  high_confidence_reviews: number;
  medium_confidence_reviews: number;
  low_confidence_reviews: number;
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
  const [recordModalOpen, setRecordModalOpen] = useState(false);
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
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setRecordModalOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

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
      confirmedDataIssues: alerts.filter(
        (alert) => alert.review_outcome === "confirmed_data_issue",
      ).length,
      falsePositives: alerts.filter(
        (alert) => alert.review_outcome === "false_positive",
      ).length,
      needsMoreInformation: alerts.filter(
        (alert) => alert.review_outcome === "needs_more_information",
      ).length,
      confidence: {
        high: alerts.filter((alert) => alert.review_confidence === "high").length,
        medium: alerts.filter((alert) => alert.review_confidence === "medium").length,
        low: alerts.filter((alert) => alert.review_confidence === "low").length,
      },
    };
  }, [alerts, review]);
  const resolvedRate = liveReviewSummary.sampleSize
    ? Math.round((liveReviewSummary.resolved / liveReviewSummary.sampleSize) * 100)
    : 0;
  const runAgeDays = run
    ? (PAGE_LOADED_AT - new Date(run.run_timestamp_utc).getTime()) / 86_400_000
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
  const controlCoverage = useMemo(() => {
    const mlOnly = alerts.filter(
      (alert) =>
        split(alert.detectors).length === 1 &&
        split(alert.detectors)[0] === "isolation_forest",
    ).length;
    const ruleOnly = alerts.filter(
      (alert) =>
        split(alert.detectors).length === 1 &&
        split(alert.detectors)[0] === "rule",
    ).length;
    const corroborated = alerts.filter(
      (alert) => alert.corroborated === "True",
    ).length;
    return {
      mlOnly,
      ruleOnly,
      corroborated,
      corroborationRate: alerts.length ? corroborated / alerts.length : 0,
    };
  }, [alerts]);
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
      <header className="institutional-header">
        <div className="brand-bar">
          <button className="institution-brand" onClick={() => setPanel("alerts")} aria-label="Open alert operations">
            <span className="institution-mark" aria-hidden="true"><i /><i /><i /></span>
            <span className="institution-title">
              <strong>IDA Financial Data Control Tower</strong>
              <small>Financial integrity and analyst assurance</small>
            </span>
          </button>
          <div className="prototype-identity">
            <span>Independent prototype · Built with public World Bank data</span>
            <a href="https://financesone.worldbank.org/ida-commitments-and-disbursements-country-economy-summary/DS01557" target="_blank" rel="noreferrer">View source ↗</a>
          </div>
        </div>
        <nav className="primary-navigation" aria-label="Primary navigation">
          <div>
            <button className={panel === "alerts" ? "active" : ""} onClick={() => setPanel("alerts")}>Alert operations <b>{alerts.length ? liveReviewSummary.open : "—"}</b></button>
            <button className={panel === "quality" ? "active" : ""} onClick={() => setPanel("quality")}>Model &amp; data quality</button>
          </div>
          <span>IDA commitments and disbursements · DS01557</span>
        </nav>
        <div className="independence-notice">Independent project · Not affiliated with, endorsed by, or operated by the World Bank Group.</div>
      </header>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">IDA commitments and disbursements</p>
            <h1>
              {panel === "alerts"
                ? "Financial data review"
                : "Model performance and control evidence"}
            </h1>
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
            <section className="portfolio-snapshot" aria-label="Portfolio review snapshot">
              <div className="coverage-statement">
                <span>Records monitored</span>
                <strong>{run ? number.format(run.source_records) : "—"}</strong>
                <p>
                  {run
                    ? `Across ${number.format(run.periods)} reporting periods and ${number.format(run.countries)} entities.`
                    : "Dataset coverage unavailable."}
                </p>
              </div>
              <dl className="snapshot-facts">
                <div>
                  <dt>Need analyst attention</dt>
                  <dd>{alerts.length ? liveReviewSummary.open : "—"}</dd>
                  <small><b className="critical-text">{alerts.length ? liveReviewSummary.openBySeverity.critical : "—"} critical</b> and {alerts.length ? liveReviewSummary.openBySeverity.high : "—"} high priority</small>
                </div>
                <div>
                  <dt>Corroborated</dt>
                  <dd>{run?.corroborated_alerts ?? "—"}</dd>
                  <small>Flagged by more than one detector family</small>
                </div>
                <div>
                  <dt>Reviewed</dt>
                  <dd>{alerts.length ? liveReviewSummary.resolved : "—"}<em> of {alerts.length ? liveReviewSummary.sampleSize : "—"}</em></dd>
                  <small>{alerts.length ? liveReviewSummary.needsMoreInformation : "—"} cases still need evidence</small>
                </div>
              </dl>
            </section>

            <section className="analysis-brief">
              <header className="analysis-heading">
                <p>Operational picture</p>
                <h2>Where review attention is accumulating</h2>
                <span>Signals are shown together to support triage, not as isolated performance widgets.</span>
              </header>

              <div className="analysis-layout">
              <article className="trend-card">
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

              <aside className="analysis-rail">
              <article className="region-card">
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

              <article className="funnel-card">
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
              </aside>
              </div>

              <article className="agreement-card">
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
                      {filtered.slice(0, 80).map((alert, index) => (
                        <tr
                          key={alert.record_key}
                          className={selected?.record_key === alert.record_key ? "selected" : ""}
                          tabIndex={0}
                          onClick={() => {
                            setSelectedId(alert.record_key);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedId(alert.record_key);
                            }
                          }}
                        >
                          <td>
                            <span className="case-index">{String(index + 1).padStart(2, "0")}</span>
                            <span className={`severity-pill ${alert.severity}`}>{alert.severity}</span>
                          </td>
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
                            <span className="reason">{label(split(alert.reason_codes)[0] ?? "")}</span>
                            {alert.corroborated === "True" && <span className="corroborated">Corroborated</span>}
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
                    <div>
                      <p className="eyebrow">Selected alert</p>
                      <span className={`severity-pill ${selected.severity}`}>{selected.severity}</span>
                    </div>
                    <button className="open-record-button" onClick={() => setRecordModalOpen(true)}>Open case file ↗</button>
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

                  <section className="review-card review-workbench">
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
            {selected && recordModalOpen && (
              <div className="record-modal-backdrop" onMouseDown={() => setRecordModalOpen(false)}>
                <section
                  className="record-modal"
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="record-modal-title"
                  onMouseDown={(event) => event.stopPropagation()}
                >
                  <header className="record-modal-header">
                    <div>
                      <p>Financial integrity review</p>
                      <span>Record {selected.row_id}</span>
                    </div>
                    <button aria-label="Close record details" onClick={() => setRecordModalOpen(false)}>×</button>
                  </header>
                  <div className="record-modal-body">
                    <div className="record-modal-title">
                      <p>{selected.region}</p>
                      <h2 id="record-modal-title">{selected.country}</h2>
                      <dl>
                        <div><dt>Reporting period</dt><dd>{selected.time_period}</dd></div>
                        <div><dt>Financing measure</dt><dd>{selected.category}</dd></div>
                        <div><dt>Review priority</dt><dd className={`priority-text ${selected.severity}`}>{selected.severity}</dd></div>
                      </dl>
                    </div>
                    <div className="modal-amount-comparison">
                      <div><span>Current amount</span><strong>{formatMoney(selected.current_amount_usd_m)}</strong></div>
                      <div><span>Comparable prior</span><strong>{formatMoney(selected.comparison_amount_usd_m)}</strong></div>
                      <div><span>Period change</span><strong className={Number(selected.change_percent) >= 0 ? "up" : "down"}>{formatPercent(selected.change_percent)}</strong></div>
                    </div>
                    <div className="modal-detail-grid">
                      <section>
                        <h3>Control findings</h3>
                        <div className="reason-list">
                          {split(selected.reason_codes).map((reason, index) => (
                            <article key={reason}>
                              <div><strong>{label(reason)}</strong><span>{split(selected.messages)[index] ?? selected.messages}</span></div>
                            </article>
                          ))}
                        </div>
                      </section>
                      <section>
                        <div className="section-title">
                          <h3>Control evidence</h3>
                          {selected.corroborated === "True" && <span className="evidence-status">Corroborated</span>}
                        </div>
                        <div className="evidence-box">{split(selected.evidence).map((item) => <p key={item}>{item}</p>)}</div>
                        <dl className="evidence-register">
                          <div><dt>ML score</dt><dd>{selected.anomaly_score ? Number(selected.anomaly_score).toFixed(2) : "N/A"}</dd></div>
                          <div><dt>Materiality</dt><dd>{Math.round(Number(selected.materiality_percentile) * 100)}th percentile</dd></div>
                          <div><dt>Independent detectors</dt><dd>{selected.detector_count}</dd></div>
                        </dl>
                      </section>
                    </div>
                    <section className="modal-recommendation">
                      <h3>Next review step</h3>
                      <p>{split(selected.recommended_actions)[0]}</p>
                    </section>
                  </div>
                  <footer className="record-modal-actions">
                    <button onClick={() => setRecordModalOpen(false)}>Return to analyst review</button>
                  </footer>
                </section>
              </div>
            )}
          </>
        ) : (
          <section className="quality-grid">
            <article className="quality-card hero-quality">
              <div className="quality-heading">
                <div>
                  <p className="eyebrow">Evaluation robustness</p>
                  <h2>Controls tested beyond one hand-picked record</h2>
                </div>
                <span className="assurance-label">Control harness · not production accuracy</span>
              </div>
              <div className="quality-statline">
                <div><strong>{evaluation?.injections ?? "—"}</strong><span>Failure modes</span></div>
                <div><strong>{evaluation?.seed_runs ?? "—"}</strong><span>Target selections</span></div>
                <div><strong>{evaluation?.detected_trials ?? "—"}/{evaluation?.trials ?? "—"}</strong><span>Trials detected</span></div>
                <div><strong>{evaluation ? `${Math.round(evaluation.minimum_seed_recall * 100)}%` : "—"}</strong><span>Minimum run recall</span></div>
              </div>
              {evaluation && (
                <div className="validation-matrix">
                  <div className="matrix-header">
                    <span>Failure mode</span>
                    {evaluation.seeds.map((seed) => <b key={seed}>S{seed}</b>)}
                    <b>Recall</b>
                  </div>
                  {Object.entries(evaluation.recall_by_scenario).map(([scenario, recall]) => (
                    <div className="matrix-row" key={scenario}>
                      <span>{label(scenario)}</span>
                      {evaluation.seeds.map((seed) => {
                        const result = evaluation.outcomes.find(
                          (outcome) => outcome.seed === seed && outcome.injection === scenario,
                        );
                        return (
                          <i
                            key={seed}
                            className={result?.detected ? "passed" : "failed"}
                            title={`Seed ${seed}: ${result?.detected ? "detected" : "not detected"}`}
                          />
                        );
                      })}
                      <strong>{Math.round(recall * 100)}%</strong>
                    </div>
                  ))}
                </div>
              )}
              <p className="quality-caveat">{evaluation?.method_note}</p>
            </article>

            <article className="quality-card sensitivity-calibration">
              <div className="quality-heading">
                <div>
                  <p className="eyebrow">Sensitivity calibration</p>
                  <h2>Detection coverage versus analyst workload</h2>
                </div>
                <span className="calibration-status">
                  {evaluation?.sensitivity_analysis.status ?? "—"} operating point
                </span>
              </div>
              {evaluation?.sensitivity_analysis && (
                <>
                  <div className="calibration-table-wrap">
                    <table className="calibration-table">
                      <thead>
                        <tr>
                          <th>Contamination</th>
                          <th>ML alerts</th>
                          <th>Total queue</th>
                          <th>Queue rate</th>
                          <th>5× spike recall</th>
                          <th>10× spike recall</th>
                          <th>Workload Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluation.sensitivity_analysis.grid.map((row) => (
                          <tr className={row.selected ? "selected" : ""} key={row.contamination}>
                            <td>
                              <strong>{(row.contamination * 100).toFixed(row.contamination < 0.01 ? 1 : 0)}%</strong>
                              {row.selected && <span>Operating</span>}
                            </td>
                            <td>{number.format(row.ml_alerts)}</td>
                            <td>{number.format(row.total_alerts)}</td>
                            <td>{(row.alert_rate * 100).toFixed(1)}%</td>
                            <td>{Math.round(row.moderate_spike_recall * 100)}%</td>
                            <td>{Math.round(row.severe_spike_recall * 100)}%</td>
                            <td>{row.alert_change_vs_selected > 0 ? "+" : ""}{number.format(row.alert_change_vs_selected)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="calibration-decision">
                    <strong>Threshold decision</strong>
                    <p>{evaluation.sensitivity_analysis.selection_rationale}</p>
                  </div>
                  <p className="quality-caveat">{evaluation.sensitivity_analysis.method_note}</p>
                </>
              )}
            </article>

            <article className="quality-card evidence-readiness">
              <p className="eyebrow">Evidence readiness</p>
              <div className="readiness-title">
                <h2>{liveReviewSummary.resolved} of {review?.minimum_resolved_for_rate ?? "—"}</h2>
                <span className={liveReviewSummary.resolved >= (review?.minimum_resolved_for_rate ?? Infinity) ? "unlocked" : "locked"}>
                  {liveReviewSummary.resolved >= (review?.minimum_resolved_for_rate ?? Infinity)
                    ? "Rates available"
                    : "Rates suppressed"}
                </span>
              </div>
              <p>Final review outcomes required before precision and false-positive estimates are displayed.</p>
              <div className="readiness-progress">
                <i
                  style={{
                    width: `${Math.min(
                      (liveReviewSummary.resolved / (review?.minimum_resolved_for_rate || 1)) * 100,
                      100,
                    )}%`,
                  }}
                />
              </div>
              <div className="confidence-summary">
                <div className="confidence-bar">
                  <i className="confidence-high" style={{ flex: liveReviewSummary.confidence.high }} />
                  <i className="confidence-medium" style={{ flex: liveReviewSummary.confidence.medium }} />
                  <i className="confidence-low" style={{ flex: liveReviewSummary.confidence.low }} />
                </div>
                <div className="confidence-legend">
                  <span><i className="confidence-high" /> High <b>{liveReviewSummary.confidence.high}</b></span>
                  <span><i className="confidence-medium" /> Medium <b>{liveReviewSummary.confidence.medium}</b></span>
                  <span><i className="confidence-low" /> Low <b>{liveReviewSummary.confidence.low}</b></span>
                </div>
              </div>
            </article>

            <article className="quality-card control-coverage">
              <div className="quality-heading">
                <div>
                  <p className="eyebrow">Control coverage</p>
                  <h2>{totalSignals} detector signals</h2>
                </div>
                <strong className="coverage-rate">{Math.round(controlCoverage.corroborationRate * 100)}% corroborated</strong>
              </div>
              <div className="detector-bars">
                {run && Object.entries(run.alerts_by_detector).map(([detector, count]) => (
                  <div key={detector}>
                    <span>{label(detector)}</span>
                    <div><i style={{ width: `${(count / totalSignals) * 100}%` }} /></div>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
              <div className="coverage-metrics">
                <div><strong>{controlCoverage.corroborated}</strong><span>Multiple control families</span></div>
                <div><strong>{controlCoverage.mlOnly}</strong><span>ML-only alerts</span></div>
                <div><strong>{controlCoverage.ruleOnly}</strong><span>Rule-only alerts</span></div>
              </div>
            </article>

            <article className="quality-card review-evidence">
              <p className="eyebrow">Human-review evidence</p>
              <h2>What analysts concluded</h2>
              <div className="outcome-list">
                <div><span>Legitimate exceptions</span><strong>{liveReviewSummary.legitimateExceptions}</strong></div>
                <div><span>Confirmed data issues</span><strong>{liveReviewSummary.confirmedDataIssues}</strong></div>
                <div><span>False positives</span><strong>{liveReviewSummary.falsePositives}</strong></div>
                <div><span>Need more information</span><strong>{liveReviewSummary.needsMoreInformation}</strong></div>
              </div>
              <div className="evidence-note">
                <strong>Interpretation</strong>
                <p>
                  Unusual does not mean erroneous. Most sampled cases still require
                  stronger evidence, so rates remain intentionally withheld.
                </p>
              </div>
            </article>

            <article className="quality-card model-run-card">
              <div className="quality-heading">
                <div>
                  <p className="eyebrow">Current model run</p>
                  <h2>{run?.model_run?.algorithm ?? "Model configuration unavailable"}</h2>
                </div>
                <span className="model-version">
                  {run ? new Date(run.run_timestamp_utc).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—"}
                </span>
              </div>
              <div className="model-documentation">
                <dl className="model-specification">
                  <div><dt>Segmentation</dt><dd>4 segments</dd><span>Annual and quarterly records, separated by commitments and disbursements.</span></div>
                  <div><dt>Estimator configuration</dt><dd>{run?.model_run?.n_estimators ?? "—"} trees</dd><span>Independent ensemble fitted within each segment.</span></div>
                  <div><dt>Contamination assumption</dt><dd>{run?.model_run ? `${run.model_run.contamination * 100}%` : "—"}</dd><span>Provisional operating point tested against lower and higher sensitivity settings.</span></div>
                  <div><dt>Reproducibility</dt><dd>Seed {run?.model_run?.random_state ?? "—"}</dd><span>Fixed random state for identical-input reruns.</span></div>
                  <div><dt>Scored population</dt><dd>Country records</dd><span>Regional and portfolio aggregates are excluded from model fitting.</span></div>
                  <div><dt>Score interpretation</dt><dd>Batch-relative</dd><span>{run?.model_run?.score_scope ?? "Calculated within each reporting segment."}</span></div>
                </dl>
                <section className="model-feature-register">
                  <header><span>Input register</span><b>{run?.model_run?.features.length ?? "—"} variables</b></header>
                  <ol>
                    {run?.model_run?.features.map((feature) => <li key={feature}>{label(feature)}</li>)}
                  </ol>
                </section>
              </div>
              <aside className="decision-note"><strong>Severity safeguard</strong><p>Machine-learning output cannot receive critical severity without corroboration from an independent control.</p></aside>
            </article>

            <article className="quality-resources">
              <span>Assurance documentation</span>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower/blob/main/docs/model_card.md" target="_blank" rel="noreferrer">Model card ↗</a>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower/blob/main/docs/data_dictionary.md" target="_blank" rel="noreferrer">Data dictionary ↗</a>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower/blob/main/docs/ingestion_reliability.md" target="_blank" rel="noreferrer">Ingestion contract ↗</a>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower/blob/main/docs/critical_alert_review.md" target="_blank" rel="noreferrer">Critical-alert review ↗</a>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower/blob/main/docs/azure_target_architecture.md" target="_blank" rel="noreferrer">Azure target architecture ↗</a>
            </article>
          </section>
        )}
        <footer className="institutional-footer">
          <div className="footer-main">
            <div className="footer-intro">
              <strong>IDA Financial Data Control Tower</strong>
              <p>An independent financial-data engineering prototype for explainable detection, evidence review, and auditable analyst decisions.</p>
              <span>Designed and engineered by Nicolaas Heru Dreandachrista.</span>
            </div>
            <nav className="footer-links" aria-label="Footer navigation">
              <button onClick={() => setPanel("alerts")}>Alert operations</button>
              <button onClick={() => setPanel("quality")}>Model and data quality</button>
              <a href="https://financesone.worldbank.org/ida-commitments-and-disbursements-country-economy-summary/DS01557" target="_blank" rel="noreferrer">Public dataset</a>
              <a href="https://github.com/nicolaasheru/ida-financial-data-control-tower" target="_blank" rel="noreferrer">Source code</a>
              <a href="https://nicolaasheru.com" target="_blank" rel="noreferrer">Portfolio</a>
            </nav>
          </div>
          <div className="footer-legal">
            <span>© 2026 Nicolaas Heru Dreandachrista</span>
            <p><strong>Independent project disclaimer:</strong> This prototype uses public World Bank Group data but is not affiliated with, endorsed by, commissioned by, or operated by the World Bank Group.</p>
          </div>
        </footer>
      </section>
    </main>
  );
}
