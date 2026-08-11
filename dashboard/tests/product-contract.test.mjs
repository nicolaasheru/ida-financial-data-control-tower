import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


async function renderDashboard() {
  const html = await readFile(
    new URL("../.next/server/app/index.html", import.meta.url),
    "utf8",
  );
  return new Response(html, {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}


test("renders the real IDA product metadata and interface", async () => {
  const response = await renderDashboard();
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.match(html, /IDA Financial Data Control Tower/i);
  assert.match(html, /Financial integrity and analyst assurance/i);
  assert.doesNotMatch(html, /Starter Project|codex-preview/i);
});


test("published alerts expose unique stable record keys", async () => {
  const csv = await readFile(
    new URL("../public/data/alerts.csv", import.meta.url),
    "utf8",
  );
  const [header, ...rows] = csv.trim().split(/\r?\n/);
  const columns = header.split(",");
  assert.ok(
    columns.includes("record_key"),
    "record_key must be part of the dashboard contract",
  );
  const keys = rows.map(
    (row) => row.match(/(?:^|,)ida_[a-f0-9]{20}(?:,|$)/)?.[0]?.replaceAll(",", ""),
  );
  assert.ok(keys.every(Boolean), "every alert must expose a stable record key");
  assert.equal(new Set(keys).size, keys.length);
});


test("run summary contains derived dataset coverage fields", async () => {
  const summary = JSON.parse(
    await readFile(
      new URL("../public/data/run_summary.json", import.meta.url),
      "utf8",
    ),
  );

  assert.ok(summary.periods > 0);
  assert.ok(summary.countries > 0);
  assert.ok(summary.run_timestamp_utc);
});


test("evaluation artifact reports multi-seed robustness", async () => {
  const evaluation = JSON.parse(
    await readFile(
      new URL("../public/data/evaluation_summary.json", import.meta.url),
      "utf8",
    ),
  );

  assert.equal(evaluation.seed_runs, 5);
  assert.equal(evaluation.trials, 25);
  assert.equal(Object.keys(evaluation.recall_by_seed).length, 5);
  assert.match(evaluation.method_note, /does not estimate production accuracy/i);
});


test("model-quality view exposes governance evidence and live configuration", async () => {
  const source = await readFile(
    new URL("../app/dashboard.tsx", import.meta.url),
    "utf8",
  );
  const run = JSON.parse(
    await readFile(
      new URL("../public/data/run_summary.json", import.meta.url),
      "utf8",
    ),
  );

  assert.match(source, /Evaluation robustness/i);
  assert.match(source, /Evidence readiness/i);
  assert.match(source, /Human-review evidence/i);
  assert.match(source, /Current model run/i);
  assert.match(source, /Machine-learning output cannot receive critical severity/i);
  assert.match(source, /Azure target architecture/i);
  assert.equal(run.model_run.algorithm, "IsolationForest");
  assert.ok(run.model_run.features.length > 0);
});
