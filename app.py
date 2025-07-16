// server.js (Node.js Backend)

const express = require('express');
const fs = require('fs');
const { google } = require('googleapis');
const bodyParser = require('body-parser');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(bodyParser.json());
app.use(express.urlencoded({ extended: true }));

// Serve frontend HTML directly without public folder
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Gmail OTP Sender</title>
      <style>
        body { font-family: Arial; margin: 20px; }
        textarea, input { width: 100%; padding: 8px; margin: 5px 0; }
        textarea { resize: vertical; }
        .readonly { background: #eee; }
        .counter { font-size: 14px; color: #666; margin-bottom: 10px; }
      </style>
    </head>
    <body>
      <h2>Send OTP via Gmail</h2>
      <form method="POST" action="/send-otps">
        <label>Emails (one per line):</label><br>
        <textarea id="emails" name="emails" rows="10" required></textarea>
        <div class="counter" id="emailCount">0 emails</div>

        <label>Gmail API Credentials JSON:</label><br>
        <textarea name="credentials" rows="6" required></textarea>

        <label>Subject:</label>
        <input type="text" class="readonly" readonly value="Your Verification Code">

        <label>Body:</label>
        <textarea class="readonly" readonly rows="6">
Hi,

Your verification code is: XXXXXX

This code is valid for 5 minutes. Please do not share it with anyone.

If you did not request this code or do not agree with this action, please call us immediately at (202) 254-2100.
Otherwise it will be done itself.

Thank you,
ebay.c0m
        </textarea>

        <button type="submit">Send OTPs</button>
      </form>

      <script>
        const emailBox = document.getElementById('emails');
        const emailCount = document.getElementById('emailCount');
        emailBox.addEventListener('input', () => {
          const lines = emailBox.value.trim().split(/\n+/).filter(Boolean);
          emailCount.textContent = `${lines.length} email${lines.length === 1 ? '' : 's'}`;
        });
      </script>
    </body>
    </html>
  `);
});

app.post('/send-otps', async (req, res) => {
  const { emails, credentials } = req.body;
  try {
    const emailList = emails.trim().split(/\n+/).map(e => e.trim()).filter(Boolean);
    const credObj = JSON.parse(credentials);
    const { client_secret, client_id, redirect_uris } = credObj.installed;
    const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);

    const authUrl = oAuth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: ['https://www.googleapis.com/auth/gmail.send'],
      state: Buffer.from(JSON.stringify({ emailList, credentials })).toString('base64')
    });

    res.redirect(authUrl);
  } catch (err) {
    console.error('Credential parsing error:', err);
    return res.status(400).send('❌ Invalid credentials JSON.');
  }
});

app.get('/oauth2callback', async (req, res) => {
  if (!req.query.code || !req.query.state) {
    return res.status(400).send('❌ Missing code or state in callback.');
  }

  try {
    const { code, state } = req.query;
    const decoded = JSON.parse(Buffer.from(state, 'base64').toString('utf-8'));
    const { emailList, credentials } = decoded;
    const credObj = JSON.parse(credentials);
    const { client_secret, client_id, redirect_uris } = credObj.installed;

    const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);
    const { tokens } = await oAuth2Client.getToken(code);
    oAuth2Client.setCredentials(tokens);

    const gmail = google.gmail({ version: 'v1', auth: oAuth2Client });

    let statusLog = '';
    for (const email of emailList) {
      const otp = Math.floor(100000 + Math.random() * 900000);
      const message = [
        `To: ${email}`,
        'Subject: Your Verification Code',
        'Content-Type: text/plain; charset="UTF-8"',
        '',
        `Hi,\n\nYour verification code is: ${otp}\n\nThis code is valid for 5 minutes. Please do not share it with anyone.\n\nIf you did not request this code or do not agree with this action, please call us immediately at (202) 254-2100.\nOtherwise it will be done itself.\n\nThank you,\nebay.c0m`
      ].join('\n');

      const encodedMessage = Buffer.from(message).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

      try {
        await gmail.users.messages.send({
          userId: 'me',
          requestBody: { raw: encodedMessage }
        });
        statusLog += `✅ Sent to ${email}\n`;
      } catch (err) {
        statusLog += `❌ Failed to send to ${email}: ${err.message}\n`;
      }

      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    res.send(`<pre>${statusLog}</pre>`);
  } catch (err) {
    console.error('OAuth callback error:', err);
    res.status(500).send('❌ Failed to process OAuth callback.');
  }
});

app.listen(PORT, () => console.log(`✅ Server started on http://localhost:${PORT}`));
