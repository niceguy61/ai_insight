import { NextResponse } from "next/server";
import { execFile } from "child_process";
import path from "path";
import { adminToken, PAGES_REPO_PATH } from "../../../../lib/env";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

/** 배포 동시 실행 방지 — 연타 시 git 경합(index.lock, rmtree 경합)으로 깨진다. */
let deployInFlight: Promise<NextResponse> | null = null;

function runDeployOnce(): Promise<NextResponse> {
  if (deployInFlight) {
    return Promise.resolve(
      NextResponse.json(
        { ok: false, error: "배포가 이미 진행 중입니다 — 1~2분 후 완료됩니다." },
        { status: 409 },
      ),
    );
  }
  deployInFlight = doDeploy().finally(() => {
    deployInFlight = null;
  });
  return deployInFlight;
}

function doDeploy(): Promise<NextResponse> {
  const py = process.env.COLLECTOR_PYTHON ?? path.join(process.cwd(), "..", "collector", ".venv", "Scripts", "python.exe");
  const script = process.env.PAGES_DEPLOY_SCRIPT ?? path.join(process.cwd(), "..", "collector", "scripts", "pages_deploy.py");
  const repo = process.env.PAGES_REPO_PATH ?? path.join(process.cwd(), "..", "pages");

  return new Promise<NextResponse>((resolve) => {
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

/** JSON 재생성 + 사이트 소스 동기화 → pages repo commit+push (workflow가 배포). */
export async function POST(req: Request) {
  const token = req.headers.get("x-admin-token") ?? "";
  if (!adminToken() || token !== adminToken()) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  return runDeployOnce();
}
