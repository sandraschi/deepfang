"""Tests for DeepFang supervisor."""

import pytest


def test_supervisor_import():
    from deepfang import DeepFangSupervisor, app

    assert DeepFangSupervisor is not None
    assert app is not None


def test_supervisor_init():
    from deepfang.main import DeepFangSupervisor

    sv = DeepFangSupervisor(config={"zeroclaw_url": "http://test:9000", "deepseek_url": "http://test:9001", "moltbot_url": "http://test:9002"})
    assert sv.zeroclaw_url == "http://test:9000"
    assert sv.deepseek_url == "http://test:9001"
    assert sv.moltbot_url == "http://test:9002"


def test_supervisor_audit_log():
    from deepfang.main import DeepFangSupervisor

    sv = DeepFangSupervisor()
    assert sv.get_audit_log() == []


def test_mcp_server_import():
    from deepfang.mcp_server import deepfang_status, deepfang_pipeline, deepfang_audit

    assert callable(deepfang_status)
    assert callable(deepfang_pipeline)
    assert callable(deepfang_audit)


@pytest.mark.asyncio
async def test_health_structure():
    from deepfang.main import DeepFangSupervisor

    sv = DeepFangSupervisor()
    health = await sv.health()
    assert "status" in health
    assert "services" in health
    assert "zeroclaw" in health["services"]
    assert "deepseek" in health["services"]
    assert "moltbot" in health["services"]
    assert health["services"]["zeroclaw"] == "unreachable"
