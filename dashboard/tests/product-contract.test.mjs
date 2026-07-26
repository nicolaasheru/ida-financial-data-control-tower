import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


async function renderDashboard() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
      IMAGES: {
        input() {
          throw new Error("Image transformation is not expected in this test.");
        },
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}


test("renders the real IDA product metadata and interface", async () => {
  const response = await renderDashboard();
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  assert.match(html, /IDA Financial Data Control Tower/i);
  assert.match(html, /Financial integrity, at development scale/i);
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
