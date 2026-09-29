"""CORDTests - Generation 4.0 Architecture Features"""

import pytest
from cord.core.llm import ThoughtStreamFilter
from cord.voice.tts import TextToSpeech
from cord.ui.repl import CordMentionAndCommandCompleter, CordREPL
from cord.core.config import CordConfig, ConfigManager
from unittest.mock import MagicMock
from prompt_toolkit.document import Document

def test_universal_thought_filter():
    filter = ThoughtStreamFilter()
    chunks = filter.process("Hello <think>Thinking deeply</think> and solution.")
    kinds = [k for k, v in chunks]
    assert 'thinking' in kinds
    assert 'Thinking deeply' in "".join(v for k, v in chunks if k == 'thinking')


def test_edge_tts_engine():
    tts = TextToSpeech()
    assert tts.DEFAULT_VOICE == "en-US-ChristopherNeural"
    cleaned = tts._clean_text_for_speech("Hello `world` ```code```")
    assert "world" in cleaned
    assert "Code block executed." in cleaned


def test_mention_completer_and_resolution(tmp_path):
    f1 = tmp_path / 'test_file.py'
    f1.write_text("print('hello')", encoding='utf-8')
    
    completer = CordMentionAndCommandCompleter(str(tmp_path))
    doc = Document('Check @test', cursor_position=11)
    completions = list(completer.get_completions(doc, None))
    assert any('@test_file.py' in c.text for c in completions)
    
    cfg_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path / "home")
    cfg_mgr.config = CordConfig(workspace_dir=str(tmp_path))
    repl = CordREPL(cfg_mgr, MagicMock())
    res = repl._resolve_mentions('Read @test_file.py')
    assert "print('hello')" in res
