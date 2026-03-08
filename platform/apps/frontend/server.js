const express = require("express");

const app = express();
const host = process.env.HOST || "0.0.0.0";
const port = Number(process.env.PORT || 3000);
const apiUrl = process.env.API_URL || "http://api:4000";
const adminUrl = process.env.ADMIN_URL || "http://admin:4100";
const appEnv = process.env.APP_ENV || "development";
const trustProxy = String(process.env.TRUST_PROXY || "false").toLowerCase() === "true";

app.set("trust proxy", trustProxy);

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "frontend", env: appEnv, trustProxy });
});

app.get("/", (_req, res) => {
  res.type("html").send(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Platform Frontend</title>
        <style>
          :root {
            color-scheme: dark;
            --bg: #08111b;
            --panel: #0f1b2b;
            --border: rgba(148, 163, 184, 0.24);
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #f59e0b;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            font-family: Arial, sans-serif;
            background:
              radial-gradient(circle at top left, rgba(245, 158, 11, 0.18), transparent 28%),
              linear-gradient(180deg, #08111b 0%, #050914 100%);
            color: var(--text);
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
          }
          main {
            width: min(720px, 100%);
            background: rgba(15, 27, 43, 0.86);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 32px;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
          }
          h1 { margin: 0 0 12px; font-size: 2rem; }
          p { color: var(--muted); line-height: 1.6; }
          .pill {
            display: inline-block;
            margin-top: 12px;
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(245, 158, 11, 0.14);
            color: var(--accent);
            font-weight: 700;
          }
          code {
            background: rgba(15, 23, 42, 0.9);
            padding: 2px 6px;
            border-radius: 6px;
          }
          ul { padding-left: 18px; }
          a { color: var(--accent); text-decoration: none; }
        </style>
      </head>
      <body>
        <main>
          <span class="pill">Frontend service</span>
          <h1>Platform frontend is running</h1>
          <p>This is the customer-facing entrypoint for the SaaS platform monorepo.</p>
          <ul>
            <li>API internal URL: <code>${apiUrl}</code></li>
            <li>Admin internal URL: <code>${adminUrl}</code></li>
            <li>Environment: <code>${appEnv}</code></li>
          </ul>
        </main>
      </body>
    </html>
  `);
});

app.listen(port, host, () => {
  console.log(`frontend listening on ${host}:${port}`);
});
