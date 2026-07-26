"use client";

import { useEffect, useMemo, useState } from "react";

type Alert = {
  row_id: string;
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

  useEffect(() => {
    Promise.all([
      fetch("/data/alerts.csv").then((response) => response.text()),
      fetch("/data/run_summary.json").then((response) => response.json()),
      fetch("/data/evaluation_summary.json").then((response) => response.json()),
      fetch("/data/review_summary.json").then((response) => response.json()),
    ]).then(([csv, runData, evaluationData, reviewData]) => {
      const parsed = parseCsv(csv);
      setAlerts(parsed);
      setSelectedId(parsed[0]?.row_id ?? "");
      setRun(runData);
      setEvaluation(evaluationData);
      setReview(reviewData);
    });
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

  const selected = alerts.find((alert) => alert.row_id === selectedId) ?? filtered[0];
  const resolvedRate = review ? Math.round((review.resolved / review.sample_size) * 100) : 0;
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
            <b>{run?.alerts ?? "—"}</b>
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
            <h1>{panel === "alerts" ? "Control overview" : "Model & data quality"}</h1>
          </div>
          <div className="run-status">
            <i />
            <div>
              <strong>Pipeline healthy</strong>
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
                <small>14 reporting periods · 202 entities</small>
              </article>
              <article className="metric">
                <span>Open alerts</span>
                <strong>{run?.alerts ?? "—"}</strong>
                <div className="severity-strip">
                  <i className="critical" style={{ flex: run?.alerts_by_severity.critical ?? 0 }} />
                  <i className="high" style={{ flex: run?.alerts_by_severity.high ?? 0 }} />
                  <i className="medium" style={{ flex: run?.alerts_by_severity.medium ?? 0 }} />
                </div>
                <small>
                  <b className="critical-text">{run?.alerts_by_severity.critical ?? "—"} critical</b>
                  {" · "}{run?.alerts_by_severity.high ?? "—"} high
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
                  <strong>{review?.resolved ?? "—"}</strong>
                  <em>of {review?.sample_size ?? "—"} resolved</em>
                </div>
                <div className="progress"><i style={{ width: `${resolvedRate}%` }} /></div>
                <small>{review?.needs_more_information ?? "—"} need more information</small>
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
                    <strong>{review?.resolved ?? "—"}</strong>
                    <span>Cases resolved</span>
                  </div>
                </div>
                <div className="funnel-outcomes">
                  <div>
                    <i className="legitimate-outcome" />
                    <span>Legitimate exceptions</span>
                    <strong>{review?.legitimate_exceptions ?? "—"}</strong>
                  </div>
                  <div>
                    <i className="unresolved-outcome" />
                    <span>Need more information</span>
                    <strong>{review?.needs_more_information ?? "—"}</strong>
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
                          key={alert.row_id}
                          className={selected?.row_id === alert.row_id ? "selected" : ""}
                          onClick={() => setSelectedId(alert.row_id)}
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
                      <span className={`review-state ${selected.review_status}`}>{label(selected.review_status)}</span>
                    </div>
                    {selected.review_notes ? (
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
                      <p>No review has been recorded for this alert.</p>
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
              <h2>{review?.resolved ?? "—"} cases resolved</h2>
              <p>
                Precision and false-positive rates remain suppressed until at least{" "}
                {review?.minimum_resolved_for_rate ?? "—"} cases are resolved.
              </p>
              <div className="review-breakdown">
                <span><i className="legitimate" /> {review?.legitimate_exceptions ?? "—"} legitimate exceptions</span>
                <span><i className="unresolved" /> {review?.needs_more_information ?? "—"} need more information</span>
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
      </section>
    </main>
  );
}
