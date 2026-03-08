const express = require("express");

const app = express();
const host = process.env.HOST || "0.0.0.0";
const port = Number(process.env.PORT || 4000);
const appEnv = process.env.APP_ENV || "development";
const logLevel = process.env.LOG_LEVEL || "info";
const databaseUrl = process.env.DATABASE_URL || "";
const redisUrl = process.env.REDIS_URL || "";
const trustProxy = String(process.env.TRUST_PROXY || "false").toLowerCase() === "true";

app.set("trust proxy", trustProxy);

const redactSecret = (value) => {
  if (!value) return "";
  return value.replace(/:\/\/([^:]+):([^@]+)@/, "://$1:****@");
};

app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "api", env: appEnv, logLevel, trustProxy });
});

app.get("/", (_req, res) => {
  res.json({
    service: "api",
    status: "running",
    env: appEnv,
    routes: ["/health", "/v1/status"],
  });
});

app.get("/v1/status", (_req, res) => {
  res.json({
    service: "api",
    status: "ok",
    dependencies: {
      postgres: redactSecret(databaseUrl),
      redis: redactSecret(redisUrl),
    },
  });
});

app.post("/v1/echo", (req, res) => {
  res.json({
    service: "api",
    received: req.body || {},
  });
});

app.listen(port, host, () => {
  console.log(`api listening on ${host}:${port}`);
});
