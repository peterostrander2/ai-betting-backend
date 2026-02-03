import types

import asyncio
import pytest

import odds_api
import playbook_api
from alt_data_sources import balldontlie, serpapi


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"ok": True}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("http error")


class _FakeAsyncClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return self._resp


class _FakeSyncClient:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return self._resp


def test_odds_api_marks_used_on_success(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setitem(__import__("sys").modules, "httpx", types.SimpleNamespace(AsyncClient=lambda timeout=10.0: _FakeAsyncClient(_FakeResp(200, {"events": []}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)

    resp, used = asyncio.run(odds_api.odds_api_get("https://example.com", params={}))
    assert used is True
    assert resp is not None
    assert called["count"] == 1


def test_odds_api_does_not_mark_on_failure(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setitem(__import__("sys").modules, "httpx", types.SimpleNamespace(AsyncClient=lambda timeout=10.0: _FakeAsyncClient(_FakeResp(500, {"error": True}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)

    resp, used = asyncio.run(odds_api.odds_api_get("https://example.com", params={}))
    assert used is False
    assert called["count"] == 0
    assert resp is not None


def test_playbook_marks_used_on_success(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    class _Client:
        async def get(self, *args, **kwargs):
            return _FakeResp(200, {"data": []})

    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)
    resp = asyncio.run(playbook_api.playbook_fetch("splits", {"league": "NBA"}, client=_Client(), api_key="x"))
    assert resp is not None
    assert called["count"] == 1


def test_playbook_does_not_mark_on_failure(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    class _Client:
        async def get(self, *args, **kwargs):
            return _FakeResp(500, {"error": True})

    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)
    resp = asyncio.run(playbook_api.playbook_fetch("splits", {"league": "NBA"}, client=_Client(), api_key="x"))
    assert resp is None
    assert called["count"] == 0


def test_balldontlie_marks_used_on_success(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setattr(balldontlie, "BDL_ENABLED", True)
    monkeypatch.setattr(balldontlie, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(balldontlie, "httpx", types.SimpleNamespace(AsyncClient=lambda timeout=10.0: _FakeAsyncClient(_FakeResp(200, {"data": []}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)
    balldontlie._cache.clear()
    balldontlie._cache_timestamps.clear()
    resp = asyncio.run(balldontlie._fetch_bdl("/games", {"dates[]": "2026-01-01"}))
    assert resp is not None
    assert called["count"] == 1


def test_balldontlie_does_not_mark_on_failure(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setattr(balldontlie, "BDL_ENABLED", True)
    monkeypatch.setattr(balldontlie, "HTTPX_AVAILABLE", True)
    monkeypatch.setattr(balldontlie, "httpx", types.SimpleNamespace(AsyncClient=lambda timeout=10.0: _FakeAsyncClient(_FakeResp(500, {"error": True}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)
    balldontlie._cache.clear()
    balldontlie._cache_timestamps.clear()
    resp = asyncio.run(balldontlie._fetch_bdl("/games", {"dates[]": "2026-01-01"}))
    assert resp is None
    assert called["count"] == 0


def test_serpapi_marks_used_on_success(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setattr(serpapi, "SERPAPI_ENABLED", True)
    monkeypatch.setattr(serpapi, "SERPAPI_KEY", "x")
    monkeypatch.setitem(__import__("sys").modules, "httpx", types.SimpleNamespace(Client=lambda timeout=2.0: _FakeSyncClient(_FakeResp(200, {"search_information": {"total_results": 1}}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)

    result = serpapi.get_search_trend("test team")
    assert result is not None
    assert called["count"] == 1


def test_serpapi_does_not_mark_on_missing_fields(monkeypatch):
    called = {"count": 0}

    def _mark(_):
        called["count"] += 1

    monkeypatch.setattr(serpapi, "SERPAPI_ENABLED", True)
    monkeypatch.setattr(serpapi, "SERPAPI_KEY", "x")
    monkeypatch.setitem(__import__("sys").modules, "httpx", types.SimpleNamespace(Client=lambda timeout=2.0: _FakeSyncClient(_FakeResp(200, {"nope": True}))))
    monkeypatch.setattr("integration_registry.mark_integration_used", _mark)

    result = serpapi.get_search_trend("test team")
    assert result is not None
    assert called["count"] == 0
