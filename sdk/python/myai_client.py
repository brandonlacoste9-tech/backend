"""
Thin Python client for the MoneyMaker summarisation API.
Usage:
    client = MyAIClient(base_url="http://localhost:8000")
    client.register("alice@example.com", "password")
    # or client.login("alice@example.com", "password")
    summary = client.summarise("Your long text here...")
"""
from __future__ import annotations

import time
from typing import Any

import requests


class MyAIClientError(Exception):
    """Raised when the API returns an error or the job fails."""
    pass


class MyAIClient:
    """
    Sync client for register, login, and summarise.
    After login/register, the JWT is stored and used for summarise.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"
        resp = self._session.request(
            method, url, json=json, timeout=kwargs.pop("timeout", self.timeout), **kwargs
        )
        return resp

    def register(self, email: str, password: str) -> dict[str, Any]:
        """Register a new user. Stores the returned access token."""
        resp = self._request(
            "POST", "/auth/register", json={"email": email, "password": password}
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token")
        if not self._token:
            raise MyAIClientError("Register response missing access_token")
        return data

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Log in. Stores the returned access token."""
        resp = self._request(
            "POST", "/auth/login", json={"email": email, "password": password}
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token")
        if not self._token:
            raise MyAIClientError("Login response missing access_token")
        return data

    def summarise(
        self,
        text: str,
        max_length: int = 80,
        poll_interval: float = 1.0,
        timeout: float = 120.0,
    ) -> str:
        """
        Submit text for summarisation, poll until the job completes, return the summary.
        max_length is a hint (backend may ignore it). Raises MyAIClientError on failure or timeout.
        """
        if not self._token:
            raise MyAIClientError("Not authenticated. Call login() or register() first.")
        resp = self._request(
            "POST", "/service/generate", json={"prompt": text}, timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            raise MyAIClientError("Generate response missing job_id")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_resp = self._request(
                "GET", f"/service/status/{job_id}", timeout=10.0
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            s = status_data.get("status", "")
            if s == "completed":
                result = status_data.get("result")
                return result if result is not None else ""
            if s == "failed":
                detail = status_data.get("detail") or "Job failed"
                raise MyAIClientError(detail)
            time.sleep(poll_interval)
        raise MyAIClientError(f"Summarise timed out after {timeout}s")

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self) -> MyAIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
