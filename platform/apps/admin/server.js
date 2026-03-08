const express = require("express");

const app = express();
const host = process.env.HOST || "0.0.0.0";
const port = Number(process.env.PORT || 4100);
const appEnv = process.env.APP_ENV || "development";
const apiUrl = process.env.API_URL || "http://api:4000";
const frontendUrl = process.env.FRONTEND_URL || "http://frontend:3000";
const trustProxy = String(process.env.TRUST_PROXY || "false").toLowerCase() === "true";

app.set("trust proxy", trustProxy);

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "admin", env: appEnv, trustProxy });
});

app.get("/", (_req, res) => {
  res.type("html").send(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Platform Admin</title>
        <style>
          :root {
            color-scheme: dark;
            --bg: #0b1020;
            --panel: #131b31;
            --border: rgba(148, 163, 184, 0.22);
            --text: #e5eefc;
            --muted: #9fb2d1;
            --accent: #22c55e;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            font-family: Arial, sans-serif;
            background:
              radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 24%),
              linear-gradient(180deg, #0b1020 0%, #060912 100%);
            color: var(--text);
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
          }
          main {
            width: min(780px, 100%);
            background: rgba(19, 27, 49, 0.9);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 32px;
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
          }
          h1 { margin: 0 0 12px; font-size: 2rem; }
          p { color: var(--muted); line-height: 1.6; }
          .pill {
            display: inline-block;
            margin-bottom: 14px;
            padding: 8px 14px;
            border-radius: 999px;
            background: rgba(34, 197, 94, 0.14);
            color: var(--accent);
            font-weight: 700;
          }
          .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 20px;
          }
          .card {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 18px;
            padding: 18px;
          }
          code {
            background: rgba(15, 23, 42, 0.9);
            padding: 2px 6px;
            border-radius: 6px;
          }
        </style>
      </head>
      <body>
        <main>
          <span class="pill">Admin dashboard service</span>
          <h1>Platform admin is running</h1>
          <p>This service is meant for internal dashboards and platform operations behind Coolify routing.</p>
          <div class="grid">
            <section class="card">
              <strong>Environment</strong>
              <p><code>${appEnv}</code></p>
            </section>
            <section class="card">
              <strong>API</strong>
              <p><code>${apiUrl}</code></p>
            </section>
            <section class="card">
              <strong>Frontend</strong>
              <p><code>${frontendUrl}</code></p>
            </section>
          </div>
        </main>
      </body>
    </html>
  `);
});

app.listen(port, host, () => {
  console.log(`admin listening on ${host}:${port}`);
});
