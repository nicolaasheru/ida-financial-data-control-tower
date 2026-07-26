#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dashboard_data="$project_root/dashboard/public/data"

mkdir -p "$dashboard_data"
cp "$project_root/artifacts/alerts.csv" "$dashboard_data/alerts.csv"
cp "$project_root/artifacts/run_summary.json" "$dashboard_data/run_summary.json"
cp "$project_root/artifacts/evaluation_summary.json" "$dashboard_data/evaluation_summary.json"
cp "$project_root/artifacts/review_summary.json" "$dashboard_data/review_summary.json"

echo "Dashboard data synchronized from the latest pipeline artifacts."
