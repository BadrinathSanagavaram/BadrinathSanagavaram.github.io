"""
Run once to create the portfolio_inquiries table in BigQuery.
Usage: python create_table.py
Requires BIGQUERY_PROJECT_ID env var or defaults to job-finder-494904.
"""
from google.cloud import bigquery
from google.oauth2.service_account import Credentials
import os, sys

PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "job-finder-494904")
DATASET    = os.getenv("BIGQUERY_DATASET", "job_finder")
TABLE      = "portfolio_inquiries"
KEY_PATH   = os.getenv("GCP_KEY_PATH", "../job-finder/backend/service_account.json")

if os.path.exists(KEY_PATH):
    creds  = Credentials.from_service_account_file(KEY_PATH)
    client = bigquery.Client(project=PROJECT_ID, credentials=creds)
else:
    client = bigquery.Client(project=PROJECT_ID)

schema = [
    bigquery.SchemaField("inquiry_id",   "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("name",         "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("email",        "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("phone",        "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("service",      "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("details",      "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("submitted_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("ip_address",   "STRING",    mode="NULLABLE"),
    bigquery.SchemaField("user_agent",   "STRING",    mode="NULLABLE"),
]

table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"
table_obj = bigquery.Table(table_ref, schema=schema)
table_obj = client.create_table(table_obj, exists_ok=True)
print(f"Table ready: {table_ref}")
