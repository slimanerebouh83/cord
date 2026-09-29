"""Tests for i18n multi-language support, Windows 10/11 tools, and thinking mode."""
import pytest
from cord.ui.i18n import LANGUAGES, TRANSLATIONS, I18nManager, t
from cord.core.config import CordConfig
from cord.tools import get_default_tools
from cord.tools.computer.windows_apps import WindowsAppTool
from cord.tools.computer.computer_mouse import ComputerMouseTool
from cord.tools.computer.computer_window import ComputerWindowTool


def test_i18n_supported_languages():
    expected_langs = {"en", "fr", "es", "de", "zh", "ja", "ru", "tr", "ar"}
    assert set(LANGUAGES.keys()) == expected_langs

    manager = I18nManager(default_lang="en")

    # Test key translations across supported languages
    for lang in expected_langs:
        manager.set_language(lang)
        welcome = manager.t("welcome_title")
        assert welcome != ""
        assert isinstance(welcome, str)

        input_box = manager.t("input_box_title")
        assert input_box != ""

    # Test English LTR detection
    manager.set_language("en")
    assert manager.is_rtl is False

    # Test fallback on unknown key
    assert manager.t("non_existent_key_xyz") == "non_existent_key_xyz"


def test_config_fields():
    cfg = CordConfig()
    assert cfg.language is None
    assert cfg.input_engine == "auto"
    assert cfg.thinking_mode == "stream"


def test_windows_app_tool_registered():
    tools = get_default_tools()
    tool_names = [t.name for t in tools]

    assert "windows_app" in tool_names
    assert "computer_mouse" in tool_names
    assert "computer_window" in tool_names
    assert "computer_keyboard" in tool_names
    assert len(tools) >= 49


def test_windows_app_tool_schema():
    tool = WindowsAppTool()
    schema = tool.to_schema()
    assert schema["name"] == "windows_app"
    assert "action" in schema["parameters"]["properties"]
    assert "open" in schema["parameters"]["properties"]["action"]["enum"]
    assert "minimize_all" in schema["parameters"]["properties"]["action"]["enum"]


def test_mouse_and_window_tools_schema():
    mouse_tool = ComputerMouseTool()
    assert mouse_tool.name == "computer_mouse"
    assert "scroll_amount" in mouse_tool.parameters["properties"]

    win_tool = ComputerWindowTool()
    assert win_tool.name == "computer_window"
    assert "focus" in win_tool.parameters["properties"]["action"]["enum"]


def test_config_save_global_and_local(tmp_path):
    from cord.core.config import ConfigManager, CordConfig
    cm = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path / "home")
    cfg = cm.config
    cfg.language = "ar"
    cm.save_global(cfg)
    assert (tmp_path / "home" / "config.json").exists()

    cm.save_local(cfg)
    assert (tmp_path / ".cord" / "config.json").exists()
