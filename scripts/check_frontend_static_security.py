from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_SCAN_PATHS = ("frontend", "public")
EXCLUDED_DIRS = {"node_modules", "dist", ".git", ".vite", "__pycache__"}
TEXT_EXTENSIONS = {
    ".css",
    ".env",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mjs",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yml",
    ".yaml",
}

LOCAL_HTTP_RE = re.compile(r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|::1)(:\d+)?(/|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    message: str


@dataclass(frozen=True)
class ScanSummary:
    scanned_files: int
    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return not self.findings

    def safe_dict(self) -> dict:
        return {
            "passed": self.passed,
            "scanned_files": self.scanned_files,
            "finding_count": len(self.findings),
            "findings": [asdict(finding) for finding in self.findings],
        }


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.startswith(".env")


def iter_scan_files(paths: Iterable[Path]) -> Iterable[Path]:
    for root in paths:
        if not root.exists():
            continue
        if root.is_file() and _is_text_file(root):
            yield root
            continue
        for path in root.rglob("*"):
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if _is_text_file(path):
                yield path


def _http_urls(line: str) -> Iterable[str]:
    yield from re.findall(r"http://[^\s\"'<>)]*", line, flags=re.IGNORECASE)


def _line_findings(path: Path, line_no: int, line: str) -> list[Finding]:
    findings: list[Finding] = []
    lower = line.lower()

    if "dev-token" in lower:
        findings.append(
            Finding(str(path), line_no, "dev_token", "high", "Hardcoded development token marker found.")
        )

    if re.search(r"\bbearer\s+[a-z0-9._~+/-]{8,}", line, flags=re.IGNORECASE):
        findings.append(
            Finding(str(path), line_no, "bearer_token", "critical", "Hardcoded bearer token pattern found.")
        )

    if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", line):
        findings.append(
            Finding(str(path), line_no, "private_key_marker", "critical", "Private key marker found.")
        )

    if re.search(r"\b(api[_-]?key|secret|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]", line, re.IGNORECASE):
        findings.append(
            Finding(str(path), line_no, "api_secret_assignment", "high", "Possible hardcoded API secret assignment found.")
        )

    if re.search(r"<script\b(?![^>]*\bsrc=)[^>]*>", line, re.IGNORECASE):
        findings.append(
            Finding(str(path), line_no, "inline_script", "medium", "Inline script tag found; production CSP should avoid inline scripts.")
        )

    for url in _http_urls(line):
        if not LOCAL_HTTP_RE.match(url):
            findings.append(
                Finding(str(path), line_no, "non_local_http", "high", "Non-localhost HTTP asset or API reference found.")
            )

    return findings


def scan_paths(paths: Iterable[str | Path]) -> ScanSummary:
    roots = [Path(path) for path in paths]
    findings: list[Finding] = []
    scanned_files = 0
    for path in iter_scan_files(roots):
        scanned_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            findings.extend(_line_findings(path, line_no, line))
    return ScanSummary(scanned_files=scanned_files, findings=findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan frontend/static files for unsafe hardcoded secrets and asset references.")
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_SCAN_PATHS))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    args = parser.parse_args(argv)

    summary = scan_paths(args.paths)
    safe = summary.safe_dict()
    if args.json:
        print(json.dumps(safe, indent=2))
    else:
        print(f"Scanned files: {safe['scanned_files']}")
        print(f"Findings: {safe['finding_count']}")
        for finding in safe["findings"]:
            print(f"{finding['severity']} {finding['rule']} {finding['path']}:{finding['line']} - {finding['message']}")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
