"""
Tests - CORD Configurable Voice Models & Local Ollama Integration
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from cord.voice.models import VoiceConfig, OPENAI_VOICES, ELEVENLABS_PRESET_VOICES
from cord.voice.tts import TextToSpeech
from cord.tools.voice.voice_tool import ManageVoiceModelsTool
from cord.models.ollama_manager import OllamaManager
from cord.tools.models.ollama_tool import OllamaModelTool
from cord.core.config import ConfigManager, CordConfig


def test_voice_config_lifecycle(tmp_path):
    v_file = tmp_path / "voice.json"
    cfg = VoiceConfig(
        provider="openai",
        model="tts-1-hd",
        voice_id="nova",
        api_key="sk-mock-12345678",
        speed=1.2,
    )
    cfg.save(config_path=v_file)

    assert v_file.exists()
    restored = VoiceConfig.load(config_path=v_file)
    assert restored.provider == "openai"
    assert restored.voice_id == "nova"
    assert restored.speed == 1.2
    assert restored.api_key == "sk-mock-12345678"


def test_tts_multi_provider_routing():
    tts_engine = TextToSpeech()
    # Test configuration updates
    tts_engine.configure(provider="openai", voice_id="alloy", api_key="sk-test-openai")
    assert tts_engine.config.provider == "openai"
    assert tts_engine.config.voice_id == "alloy"

    tts_engine.configure(provider="elevenlabs", voice_id="rachel", api_key="xi-test-key")
    assert tts_engine.config.provider == "elevenlabs"
    assert tts_engine.config.voice_id == "rachel"

    tts_engine.configure(provider="edge", voice_id="en-US-ChristopherNeural")
    assert tts_engine.config.provider == "edge"


@pytest.mark.asyncio
async def test_manage_voice_tool():
    tool = ManageVoiceModelsTool()

    # 1. List voices
    res_list = await tool.execute(action="list")
    assert res_list.success
    assert "CORD Voice Models" in res_list.output
    assert "openai" in res_list.output
    assert "elevenlabs" in res_list.output

    # 2. Update voice
    res_set = await tool.execute(
        action="set",
        provider="openai",
        model="tts-1",
        voice_id="shimmer",
        api_key="sk-mock-voice-key",
    )
    assert res_set.success
    assert "shimmer" in res_set.output

    # 3. Test speech
    with patch("cord.voice.tts.TextToSpeech.speak") as mock_speak:
        res_test = await tool.execute(action="test", test_phrase="Testing CORD speech.")
        assert res_test.success
        mock_speak.assert_called_once()


def test_ollama_manager_discovery():
    mgr = OllamaManager()

    # Mock list_models
    mock_tags = {
        "models": [
            {"name": "deepseek-r1:8b", "model": "deepseek-r1:8b", "size": 4900000000, "digest": "sha256:1234"},
            {"name": "qwen2.5-coder:7b", "model": "qwen2.5-coder:7b", "size": 4500000000, "digest": "sha256:5678"},
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_tags).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        assert mgr.is_running() is True
        models = mgr.list_models()
        assert len(models) == 2
        assert models[0]["name"] == "deepseek-r1:8b"
        assert "GB" in models[0]["size"]


@pytest.mark.asyncio
async def test_ollama_tool_workflow(tmp_path):
    cfg_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path / "home")
    cfg_mgr.config = CordConfig(workspace_dir=str(tmp_path))
    tool = OllamaModelTool(config_mgr=cfg_mgr)

    with patch("cord.models.ollama_manager.OllamaManager.is_running", return_value=True):
        with patch("cord.models.ollama_manager.OllamaManager.list_models", return_value=[{"name": "deepseek-r1:8b", "size": "4.6 GB", "digest": "abc123456789"}]):
            # 1. Status
            res_status = await tool.execute(action="status")
            assert res_status.success
            assert "ONLINE" in res_status.output

            # 2. List
            res_list = await tool.execute(action="list")
            assert res_list.success
            assert "deepseek-r1:8b" in res_list.output

            # 3. Switch model
            res_switch = await tool.execute(action="switch", model_name="deepseek-r1:8b")
            assert res_switch.success
            assert cfg_mgr.config.model == "deepseek-r1:8b"
            assert cfg_mgr.config.provider == "ollama"
            assert "11434" in cfg_mgr.config.base_url
