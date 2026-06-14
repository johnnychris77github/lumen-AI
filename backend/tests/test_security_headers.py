from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.security_headers import HSTS_VALUE, SECURITY_HEADERS, SecurityHeadersMiddleware


def make_client(*, hsts_enabled: bool = False) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts_enabled)

    @app.get("/api/ok")
    def ok():
        return {"ok": True}

    @app.get("/api/error")
    def error():
        raise HTTPException(status_code=418, detail="teapot")

    return TestClient(app)


def assert_default_headers(response):
    for header, value in SECURITY_HEADERS.items():
        assert response.headers[header] == value


def test_security_headers_present_on_normal_api_responses():
    response = make_client().get("/api/ok")

    assert response.status_code == 200
    assert_default_headers(response)


def test_security_headers_present_on_error_responses():
    response = make_client().get("/api/error")

    assert response.status_code == 418
    assert_default_headers(response)


def test_hsts_not_sent_for_plain_http_unless_enabled():
    response = make_client().get("/api/ok")

    assert "Strict-Transport-Security" not in response.headers


def test_hsts_sent_when_enabled_by_config():
    response = make_client(hsts_enabled=True).get("/api/ok")

    assert response.headers["Strict-Transport-Security"] == HSTS_VALUE


def test_hsts_sent_when_https_detected():
    response = make_client().get("/api/ok", headers={"X-Forwarded-Proto": "https"})

    assert response.headers["Strict-Transport-Security"] == HSTS_VALUE


def test_cors_behavior_is_not_broken():
    response = make_client().options(
        "/api/ok",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert_default_headers(response)
