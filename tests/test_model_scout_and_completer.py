"""
Tests for Model Scout Subagent, SlashCommandCompleter, and Arabic rendering fixes.
"""

import pytest
from prompt_toolkit.document import Document

from cord.ui.repl import SlashCommandCompleter, SLASH_COMMAND_INFO
from cord.ui.arabic import fix_arabic, is_arabic
from cord.subagents.model_scout import ModelScoutSubagent, LATEST_MODELS_CATALOG
from cord.subagents.roles import ROLE_CONFIGS
from cord.core.config import ConfigManager, CordConfig


def test_arabic_no_backwards_reversal():
    # Verify standard Arabic text is NOT inverted or reversed letter-by-letter
    input_text = "صندوق الكتابة"
    result = fix_arabic(input_text)
    assert result == input_text
    assert "ةباتكلا" not in result
    assert "قودنص" not in result

    arabic_name = "العربية"
    res_name = fix_arabic(arabic_name)
    assert res_name == "العربية"
    assert "ة يبرعلا" not in res_name


def test_slash_command_completer():
    completer = SlashCommandCompleter()

    # Trigger on '/' alone
    doc_slash = Document("/")
    completions_slash = list(completer.get_completions(doc_slash, None))
    assert len(completions_slash) == len(SLASH_COMMAND_INFO)
    texts = [c.text for c in completions_slash]
    assert "/menu" in texts
    assert "/scout" in texts
    assert "/mode" in texts

    # Filter with '/sc'
    doc_sc = Document("/sc")
    completions_sc = list(completer.get_completions(doc_sc, None))
    assert len(completions_sc) == 1
    assert completions_sc[0].text == "/scout"
    assert "Scout" in completions_sc[0].display_meta_text

    # Filter with '/m'
    doc_m = Document("/m")
    completions_m = list(completer.get_completions(doc_m, None))
    texts_m = [c.text for c in completions_m]
    assert "/menu" in texts_m
    assert "/mode" in texts_m
    assert "/models" in texts_m
    assert "/model" in texts_m


def test_model_scout_catalog_coverage():
    # Verify frontier labs are covered
    catalog = LATEST_MODELS_CATALOG
    assert "claude-3-7-sonnet" in catalog
    assert "claude-3-7-thinking" in catalog
    assert "deepseek-r1" in catalog
    assert "deepseek-v3" in catalog
    assert "gemini-2-5-pro" in catalog
    assert "gemini-2-flash" in catalog
    assert "o3-mini" in catalog
    assert "gpt-4-5" in catalog
    assert "kimi-k1-5" in catalog
    assert "kimi-128k" in catalog
    assert "qwen-2-5-coder" in catalog


def test_model_scout_filtering(tmp_path):
    config_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path)
    scout = ModelScoutSubagent(config_mgr)

    # Filter by Anthropic
    anthropic_models = scout.get_catalog("anthropic")
    assert any("claude" in k for k in anthropic_models.keys())
    assert all("anthropic" in v["org"].lower() for v in anthropic_models.values())

    # Filter by DeepSeek
    deepseek_models = scout.get_catalog("deepseek")
    assert any("deepseek" in k for k in deepseek_models.keys())

    # Filter by Kimi / Moonshot
    kimi_models = scout.get_catalog("kimi")
    assert any("kimi" in k for k in kimi_models.keys())


def test_model_scout_update_config(tmp_path):
    config_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path)
    scout = ModelScoutSubagent(config_mgr)

    updated_count = scout.update_saved_models_in_config()
    assert updated_count > 0

    saved = config_mgr.config.saved_models
    assert "claude-3-7-sonnet" in saved
    assert "deepseek-r1" in saved
    assert "gemini-2-5-pro" in saved
    assert "kimi-k1-5" in saved


def test_role_configs_has_model_scout():
    assert "model_scout" in ROLE_CONFIGS
    role = ROLE_CONFIGS["model_scout"]
    assert "Claude" in role["system_prompt"]
    assert "DeepSeek" in role["system_prompt"]
    assert "Kimi" in role["system_prompt"]


def test_mention_completer_instant_response_on_home_dir():
    import time
    from pathlib import Path
    from cord.ui.repl import CordMentionAndCommandCompleter

    completer = CordMentionAndCommandCompleter(workspace_dir=str(Path.home()))
    t0 = time.perf_counter()
    completions = list(completer.get_completions(Document("@"), None))
    elapsed = time.perf_counter() - t0

    # Must complete almost instantaneously (under 150ms), preventing any UI freeze
    assert elapsed < 0.15, f"Completion took too long: {elapsed:.3f}s"

    texts = [c.text for c in completions]
    assert "@git" in texts
    assert "@tasks" in texts

    # Ensure no AppData or deep internal recursion leaked in
    for t in texts:
        assert "appdata" not in t.lower()


def test_mention_completer_filtering():
    from pathlib import Path
    from cord.ui.repl import CordMentionAndCommandCompleter

    completer = CordMentionAndCommandCompleter(workspace_dir=str(Path.home()))
    completions = list(completer.get_completions(Document("@gi"), None))
    texts = [c.text for c in completions]
    assert "@git" in texts

