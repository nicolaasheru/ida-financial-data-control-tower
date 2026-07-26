from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
ARTIFACT_DIR = ROOT / "artifacts"

DATASET_ID = "DS01557"
RESOURCE_ID = "RS00964"
API_URL = "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"

RAW_FILE = RAW_DIR / "ida_commitments_disbursements.json"
CLEAN_FILE = PROCESSED_DIR / "ida_commitments_disbursements.csv"
FEATURE_FILE = PROCESSED_DIR / "ida_model_features.csv"
ALERT_FILE = ARTIFACT_DIR / "alerts.csv"
RUN_SUMMARY_FILE = ARTIFACT_DIR / "run_summary.json"
SIGNAL_FILE = ARTIFACT_DIR / "alert_signals.csv"
REVIEW_SAMPLE_FILE = ARTIFACT_DIR / "manual_review_sample.csv"
REVIEW_FILE = ARTIFACT_DIR / "reviews.csv"
REVIEW_SUMMARY_FILE = ARTIFACT_DIR / "review_summary.json"
REVIEW_DATABASE_FILE = ROOT / "data" / "reviews.sqlite3"

AMOUNT_COLUMNS = [
    "development_policy",
    "investment_lending",
    "others",
    "program_for_results",
    "total",
]
COMPONENT_COLUMNS = AMOUNT_COLUMNS[:-1]
REQUIRED_COLUMNS = [
    "category",
    "country",
    "organization",
    "region",
    "time_period",
    *AMOUNT_COLUMNS,
]
VALID_CATEGORIES = {"Commitments", "Gross Disbursements"}
GRAIN_COLUMNS = ["organization", "country", "category", "time_period"]

MIN_RATIO_DENOMINATOR_USD_M = 10.0

AGGREGATE_ENTITIES = {
    "Africa",
    "Central Africa",
    "Eastern Africa",
    "Western Africa",
    "East Asia and Pacific",
    "Pacific 1",
    "Pacific Islands",
    "South East Asia",
    "Eastern and Southern Africa",
    "Southern Africa",
    "Central Asia",
    "Caribbean",
    "Central America",
    "Middle East and North Africa",
    "Mid East,NorthAfrica, Afghan, Pakistan",
    "South Asia",
    "Western and Central Africa",
    "IFC",
    "MIGA",
    "World",
}
