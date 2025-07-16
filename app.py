from flask import Flask, request, redirect, render_template_string
import json
import os
import base64
import time
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = Flask(__name__)

# In-memory session (simple use case)
SESSION = {}

# HTML interface
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gmail OTP Sender (Flask)</title>
  <style>
    body { font-family: Arial; max-width: 600px; margin: auto; padding: 20px; }
    textarea, input, button { width: 100%; padding: 10px; margin-bottom: 10px; font-size: 16px; }
    #status { white-space: pre-wrap; background: #f9f9f9; border: 1px solid #ccc; padding: 10px; min-height: 150px; }
  </style>
</head>
<body>
  <h2>📧 Gmail OTP Sender</h2>
  <form method="POST" action="/authorize">
    <label>Paste Emails (one per line):</label>
    <textarea name="emails" rows="8" placeholder="example1@gmail.com&#10;example2@gmail.com" required></textarea>

    <label>Paste Gmail Credentials JSON:</label>
    <textarea name="credentials" rows="8" required></textarea>

    <button type="submit">🔐 Send OTP</button>
  </form>
  {% if status %}
    <h3>Status:</h3>
    <div id="status">{{ status }}</div>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)

@app.route("/authorize", methods=["POST"])
def authorize():
    emails = request.form["emails"].strip().splitlines()
    credentials_json = request.form["credentials"].strip()

    try:
        cred_dict = json.loads(credentials_json)
        client_config = cred_dict["installed"]

        flow = Flow.from_client_config(
            {"installed": client_config},
            scopes=["https://www.googleapis.com/auth/gmail.send"],
            redirect_uri=client_config["redirect_uris"][0]
        )

        SESSION["emails"] = emails
        SESSION["credentials"] = credentials_json
        SESSION["flow"] = flow

        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        return redirect(auth_url)

    except Exception as e:
        return f"❌ Credential parsing error: {str(e)}"

@app.route("/oauth2callback")
def oauth2callback():
    flow = SESSION.get("flow")
    if not flow:
        return "Session expired. Please go back and try again."

    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        emails = SESSION.get("emails", [])

        service = build("gmail", "v1", credentials=creds)
        log = ""

        for email in emails:
            otp = str(random.randint(100000, 999999))
            body = f"""Hi,

Your verification code is: {otp}

This code is valid for 5 minutes. Please do not share it with anyone.

If you did not request this code or do not agree with this action, please call us immediately at (202) 254-2100.
Otherwise it will be done itself.

Thank you,
ebay.c0m
"""
            message = f"To: {email}\r\nSubject: Your Verification Code\r\n\r\n{body}"
            encoded = base64.urlsafe_b64encode(message.encode()).decode()

            try:
                service.users().messages().send(userId="me", body={"raw": encoded}).execute()
                log += f"✅ Sent to {email}\n"
            except Exception as err:
                log += f"❌ Failed to send to {email}: {err}\n"

            time.sleep(1)

        return render_template_string(HTML_PAGE, status=log)

    except Exception as e:
        return f"❌ Authorization or email sending failed: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
