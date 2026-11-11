import { NextResponse } from "next/server";
import { execFile } from "child_process";
import path from "path";
import { adminToken, PAGES_REPO_PATH } from "../../../../lib/env";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

/** JSON 재생성 → pages repo data 갱신 → commit+push (workflow가 배포). */
export async function POST(req: Request) {
  const token = req.headers.get("x-admin-token") ?? "";
  if (!adminToken() || token !== adminToken()) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const py = process.env.COLLECTOR_PYTHON ?? path.join(process.cwd(), "..", "collector", ".venv", "Scripts", "python.exe");
  const script = process.env.PAGES_DEPLOY_SCRIPT ?? path.join(process.cwd(), "..", "collector", "scripts", "pages_deploy.py");
  const repo = process.env.PAGES_REPO_PATH ?? path.join(process.cwd(), "..", "pages");

  return new Promise<Response>((resolve) => {
    execFile(
      py,
      [script, "push", repo],
      { timeout: 540_000, maxBuffer: 10 * 1024 * 1024, cwd: path.dirname(script) },
      (err, stdout, stderr) => {
        if (err) {
          resolve(NextResponse.json(
            { ok: false, error: (stderr || err.message || "deploy 실패").slice(0, 1000) },
            { status: 500 },
          ));
        } else {
          resolve(NextResponse.json({ ok: true, output: String(stdout).slice(-1500) }));
        }
      },
    );
  });
}
