"""
Cloud Function — Portfolio Inquiry Handler
GCP Project : job-finder-494904
Dataset     : job_finder
Table       : portfolio_inquiries

Receives form submissions from the portfolio contact form, stores them in
BigQuery, and sends a notification email via Gmail SMTP.
"""
import functions_framework
from google.cloud import bigquery
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
import uuid
from datetime import datetime, timezone


# ── Config (injected as Cloud Run environment variables) ──────────────────────
PROJECT_ID       = os.getenv("BIGQUERY_PROJECT_ID", "job-finder-494904")
DATASET          = os.getenv("BIGQUERY_DATASET", "job_finder")
TABLE            = "portfolio_inquiries"
GMAIL_SENDER     = os.getenv("GMAIL_SENDER")
GMAIL_APP_PW     = os.getenv("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL     = os.getenv("NOTIFY_EMAIL", "badrinath.sanagavaram@gmail.com")

FULL_TABLE       = f"{PROJECT_ID}.{DATASET}.{TABLE}"
CORS_HEADERS     = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _bq_client() -> bigquery.Client:
    key_path = os.getenv("GCP_KEY_PATH")
    if key_path and os.path.exists(key_path):
        creds = Credentials.from_service_account_file(key_path)
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)   # uses ADC in Cloud Run


def _save_to_bq(row: dict):
    client = _bq_client()
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json([row], FULL_TABLE, job_config=job_config)
    job.result()


def _send_email(row: dict):
    if not GMAIL_SENDER or not GMAIL_APP_PW:
        print("WARNING: GMAIL_SENDER or GMAIL_APP_PASSWORD not set — skipping email")
        return

    subject = f"[Portfolio Inquiry] {row['service']} from {row['name']}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;
              box-shadow:0 4px 20px rgba(0,0,0,0.08)">

  <tr>
    <td style="background:linear-gradient(135deg,#0a0a0a 0%,#1a1a2e 100%);padding:28px 32px">
      <div style="font-size:11px;font-weight:600;color:#00d4ff;letter-spacing:1.2px;
                  text-transform:uppercase">Portfolio · New Inquiry</div>
      <div style="font-size:20px;font-weight:700;color:#fff;margin-top:6px">
        {row['service']}
      </div>
      <div style="font-size:12px;color:#a0a0a0;margin-top:4px">
        Received {row['submitted_at'][:19].replace('T', ' ')} UTC
      </div>
    </td>
  </tr>

  <tr>
    <td style="padding:28px 32px">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #f1f5f9">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.8px;
                        color:#94a3b8">Name</div>
            <div style="font-size:15px;color:#1e293b;margin-top:3px;font-weight:600">
              {row['name']}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #f1f5f9">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.8px;
                        color:#94a3b8">Email</div>
            <div style="font-size:15px;color:#2563eb;margin-top:3px">
              <a href="mailto:{row['email']}" style="color:#2563eb">{row['email']}</a>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;border-bottom:1px solid #f1f5f9">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.8px;
                        color:#94a3b8">Phone</div>
            <div style="font-size:15px;color:#1e293b;margin-top:3px">
              {row.get('phone') or '—'}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.8px;
                        color:#94a3b8">Project Details</div>
            <div style="font-size:14px;color:#374151;margin-top:6px;line-height:1.6;
                        background:#f8fafc;border-radius:8px;padding:14px">
              {row['details']}
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <tr>
    <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:14px 32px">
      <div style="font-size:11px;color:#94a3b8;text-align:center">
        Inquiry ID: {row['inquiry_id']} · badrinathsanagavaram.github.io
      </div>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = NOTIFY_EMAIL
    msg["Reply-To"] = row["email"]
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_SENDER, GMAIL_APP_PW)
        smtp.sendmail(GMAIL_SENDER, NOTIFY_EMAIL, msg.as_string())


@functions_framework.http
def handle_inquiry(request):
    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    if request.method != "POST":
        return (json.dumps({"success": False, "message": "Method not allowed"}),
                405, {**CORS_HEADERS, "Content-Type": "application/json"})

    try:
        data    = request.get_json(silent=True) or {}
        name    = str(data.get("name", "")).strip()
        email   = str(data.get("email", "")).strip()
        phone   = str(data.get("phone", "")).strip()
        service = str(data.get("service", "")).strip()
        details = str(data.get("details", "")).strip()

        if not name or not email or not service or not details:
            return (json.dumps({"success": False, "message": "Required fields missing"}),
                    400, {**CORS_HEADERS, "Content-Type": "application/json"})

        row = {
            "inquiry_id":  str(uuid.uuid4()),
            "name":        name,
            "email":       email,
            "phone":       phone or None,
            "service":     service,
            "details":     details,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "ip_address":  request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or None,
            "user_agent":  request.headers.get("User-Agent", None),
        }

        _save_to_bq(row)
        _send_email(row)

        return (json.dumps({"success": True, "inquiry_id": row["inquiry_id"]}),
                200, {**CORS_HEADERS, "Content-Type": "application/json"})

    except Exception as exc:
        print(f"ERROR: {exc}")
        return (json.dumps({"success": False, "message": "Internal server error"}),
                500, {**CORS_HEADERS, "Content-Type": "application/json"})
