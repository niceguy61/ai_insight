import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ai_insight — MCP·스킬 포털",
  description:
    "AI 에이전트 생태계의 MCP 서버와 스킬을 수집·요약해 랭킹과 검색으로 보여주는 한국어 포털",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="site">
          <div className="container inner">
            <Link href="/" className="logo">
              ai<span>_</span>insight
            </Link>
            <nav>
              <Link href="/">랭킹</Link>
              <Link href="/search">검색</Link>
            </nav>
          </div>
        </header>
        <main className="container">{children}</main>
        <footer className="site">
          <div className="container">
            원문 출처는 각 항목 상세 페이지에 표기됩니다 · 데이터: GitHub, skills.sh, ClawHub, MCP Registry, npm
          </div>
        </footer>
      </body>
    </html>
  );
}
