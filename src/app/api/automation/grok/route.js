import { NextResponse } from "next/server";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import crypto from "crypto";

export const dynamic = "force-dynamic";

// ─── Grok registration toolkit (grok-regkit) integration ─────────────
// Toolkit: /root/AMRouter/grok-regkit (run_grok.py wrapper)
// State/log files land in DATA_DIR/grok/ so we can poll job status.

const GROK_DIR = path.resolve(process.cwd(), "grok-regkit");
const VENV_PYTHON = path.join(GROK_DIR, ".venv/bin/python");
const WRAPPER = path.join(GROK_DIR, "run_grok.py");

function grokStateDir() {
  const base = process.env.DATA_DIR || path.join(process.env.HOME || "/tmp", ".amrouter");
  const dir = path.join(base, "grok");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function readState(jobId) {
  try {
    const f = path.join(grokStateDir(), `grok_${jobId}.state.json`);
    if (!fs.existsSync(f)) return null;
    return JSON.parse(fs.readFileSync(f, "utf-8"));
  } catch (e) {
    return null;
  }
}

function readLog(jobId) {
  try {
    const f = path.join(grokStateDir(), `grok_${jobId}.log`);
    if (!fs.existsSync(f)) return "";
    return fs.readFileSync(f, "utf-8");
  } catch (e) {
    return "";
  }
}

// ─── GET: status of all jobs (or one) ────────────────────────────────
export async function GET(req) {
  try {
    const url = new URL(req.url);
    const jobId = url.searchParams.get("job_id");
    const action = url.searchParams.get("action") || "";

    if (jobId) {
      const state = readState(jobId);
      if (!state) return NextResponse.json({ error: "Job not found" }, { status: 404 });
      const log = action === "log" ? readLog(jobId) : "";
      return NextResponse.json({ ...state, log });
    }

    // List all jobs (state files)
    const dir = grokStateDir();
    const jobs = fs.readdirSync(dir)
      .filter((f) => f.endsWith(".state.json"))
      .map((f) => {
        try {
          const st = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
          return { job_id: st.job_id, status: st.status, success: st.success, fail: st.fail, progress: st.progress, updated_at: st.updated_at };
        } catch { return null; }
      })
      .filter(Boolean)
      .sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
    return NextResponse.json({ jobs });
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

// ─── POST: start job / stop job ──────────────────────────────────────
export async function POST(req) {
  try {
    const body = await req.json();
    const { action } = body;

    // ── Start registration job ───────────────────────────────────────
    if (action === "start") {
      const count = Math.max(1, parseInt(body.count, 10) || 1);
      const mode = body.mode || "browser";
      const proxy = body.proxy || "";
      const emailBase = body.email_base || "";
      const emailKey = body.email_key || "";
      const jobId = crypto.randomBytes(8).toString("hex");

      if (!fs.existsSync(VENV_PYTHON)) {
        return NextResponse.json({ error: `Grok venv tidak ditemukan: ${VENV_PYTHON}. Jalankan: cd grok-regkit && python3 -m venv .venv && pip install -r requirements.txt` }, { status: 400 });
      }
      if (!fs.existsSync(WRAPPER)) {
        return NextResponse.json({ error: `Wrapper tidak ditemukan: ${WRAPPER}` }, { status: 400 });
      }

      const args = [
        WRAPPER,
        "--job-id", jobId,
        "--count", String(count),
        "--mode", mode,
        "--state-dir", grokStateDir(),
      ];
      if (proxy) args.push("--proxy", proxy);
      if (emailBase) args.push("--email-base", emailBase);
      if (emailKey) args.push("--email-key", emailKey);

      // Spawn on the real X display (Chromium/DrissionPage headed). Root uses
      // xhost on :0 (set at startup), so drop XAUTHORITY like codebuddy does.
      const childEnv = { ...process.env, DISPLAY: ":0", GROK_REGISTER_BROWSER_PATH: "/usr/bin/chromium" };
      delete childEnv.XAUTHORITY;

      const child = spawn(VENV_PYTHON, args, { env: childEnv, cwd: GROK_DIR });

      let stderrAcc = "";
      child.stderr.on("data", (d) => { stderrAcc += d.toString(); });

      child.on("error", (err) => {
        console.error(`[grok] spawn error: ${err.message}`);
        fs.writeFileSync(path.join(grokStateDir(), `grok_${jobId}.state.json`), JSON.stringify({ job_id: jobId, status: "error", error: err.message, updated_at: Date.now() }));
      });

      child.on("exit", (code) => {
        if (code !== 0 && code !== null) {
          console.error(`[grok] job ${jobId} exited code=${code} stderr=${stderrAcc.slice(-500)}`);
        }
      });

      return NextResponse.json({ ok: true, job_id: jobId });
    }

    // ── Stop job ─────────────────────────────────────────────────────
    if (action === "stop") {
      const jobId = body.job_id;
      if (!jobId) return NextResponse.json({ error: "job_id required" }, { status: 400 });
      const stopFile = path.join(grokStateDir(), `grok_${jobId}.stop`);
      fs.writeFileSync(stopFile, new Date().toISOString());
      return NextResponse.json({ ok: true, message: "Stop signal sent" });
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
