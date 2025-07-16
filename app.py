from flask import Flask, request, redirect, render_template_string
import json
import base64
import time
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__)

# Global session data storage
session_store = {}

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
  <title>OTP Sender</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; }
    textarea, input { width: 100%; margin-bottom: 10px; padding: 10px; }
    #status-bar { white-space: pre-wrap; background: #f8f8f8; padding: 10px; border: 1px solid #ccc; }
  </style>
</head>
<body>
  <h2>Bulk OTP Sender via Gmail API</h2>

  <form method="POST" action="/send-otps">
    <label>Email List (one per line):</label><br>
    <textarea name="emails" rows="10" required></textarea><br>

    <label>Gmail API Credentials JSON:</label><br>
    <textarea name="credentials" rows="10" required></textarea><br>

    <button type="submit">Send OTPs</button>
  </form>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_FORM)

@app.route("/send-otps", methods=["POST"])
def send_otps():
    try:
        emails = request.form["emails"].strip().splitlines()
        credentials_str = request.form["credentials"]
        cred_obj = json.loads(credentials_str)

        flow = Flow.from_client_config(
            cred_obj,
            scopes=['https://www.googleapis.com/auth/gmail.send'],
            redirect_uri='https://otp-mqa3.onrender.com/oauth2callback'
        )

        session_id = str(time.time())
        session_store[session_id] = {
            "emails": emails,
            "credentials": cred_obj
        }

        auth_url, _ = flow.authorization_url(prompt='consent')
        return redirect(f"{auth_url}&state={session_id}")
    except Exception as e:
        return f"❌ Error: {str(e)}", 400

@app.route("/oauth2callback")
def oauth2callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        if not code or not state or state not in session_store:
            return "❌ Invalid or expired session."

        session_data = session_store[state]
        flow = Flow.from_client_config(
            session_data["credentials"],
            scopes=['https://www.googleapis.com/auth/gmail.send'],
            redirect_uri='https://otp-mqa3.onrender.com/oauth2callback'
        )

        flow.fetch_token(code=code)
        creds = flow.credentials
        service = build('gmail', 'v1', credentials=creds)

        status_log = ""
        for email in session_data["emails"]:
            otp = str(int(time.time()))[-6:]
            message = f"""To: {email}
Subject: Your Verification Code
Content-Type: text/plain; charset="UTF-8"

Hi,

Your verification code is: {otp}

This code is valid for 5 minutes. Please do not share it with anyone.

If you did not request this code or do not agree with this action, please call us immediately at (202) 254-2100.
Otherwise it will be done itself.

Thank you,
ebay.c0m"""

            raw = base64.urlsafe_b64encode(message.encode()).decode().strip("=")
            try:
                service.users().messages().send(userId='me', body={'raw': raw}).execute()
                status_log += f"✅ Sent to {email}\n"
            except Exception as e:
                status_log += f"❌ Failed to send to {email}: {str(e)}\n"
            time.sleep(1)

        return f"<pre>{status_log}</pre>"
    except Exception as e:
        return f"❌ Error during email send: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
