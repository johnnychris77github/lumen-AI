from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.check_frontend_static_security import main, scan_paths


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_scanner_detects_obvious_hardcoded_tokens(tmp_path):
    sample = write(tmp_path / "frontend" / "src" / "bad.ts", 'const token = "dev-token";\n')

    summary = scan_paths([sample])

    assert summary.passed is False
    assert {finding.rule for finding in summary.findings} == {"dev_token"}


def test_scanner_detects_private_key_markers(tmp_path):
    sample = write(tmp_path / "frontend" / "key.txt", "-----BEGIN PRIVATE KEY-----\nredacted\n")

    summary = scan_paths([sample])

    assert summary.passed is False
    assert summary.findings[0].rule == "private_key_marker"


def test_scanner_allows_safe_localhost_development_urls(tmp_path):
    sample = write(
        tmp_path / "frontend" / "src" / "dev.ts",
        'const api = "http://localhost:5173";\nconst other = "http://127.0.0.1:8000/api";\n',
    )

    summary = scan_paths([sample])

    assert summary.passed is True


def test_scanner_flags_non_localhost_http_references(tmp_path):
    sample = write(tmp_path / "frontend" / "src" / "bad-url.ts", 'const asset = "http://cdn.example.com/app.js";\n')

    summary = scan_paths([sample])

    assert summary.passed is False
    assert summary.findings[0].rule == "non_local_http"


def test_scanner_returns_safe_summaries_without_secret_values(tmp_path, capsys):
    sample = write(tmp_path / "frontend" / "src" / "secret.ts", 'const apiKey = "super-secret-value";\n')

    exit_code = main([str(sample), "--json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "api_secret_assignment" in output
    assert "super-secret-value" not in output
    assert "apiKey" not in output
