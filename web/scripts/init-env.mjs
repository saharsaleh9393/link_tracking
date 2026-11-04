import { randomBytes } from "node:crypto";
import { writeFileSync, existsSync } from "node:fs";
if (existsSync(".env.local")) {
  console.log("Existing .env.local preserved.");
} else {
  writeFileSync(
    ".env.local",
    `TRACKER_API_URL=http://127.0.0.1:8000\nDASHBOARD_PASSWORD=${randomBytes(24).toString("base64url")}\nDASHBOARD_SESSION_SECRET=${randomBytes(48).toString("base64url")}\nDASHBOARD_SECURE_COOKIES=false\n`,
    { flag: "wx", mode: 0o600 },
  );
  console.log(
    "Created .env.local. Read DASHBOARD_PASSWORD there to sign in locally; keep it private.",
  );
}
