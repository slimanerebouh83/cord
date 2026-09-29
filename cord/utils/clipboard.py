"""
CORD Utils - System Clipboard Integration
Enables copying assistant responses, code blocks, and selected text to OS clipboard.
Supports Windows (clip.exe & PowerShell Set-Clipboard), macOS (pbcopy), and Linux (xclip/wl-copy).
"""

from __future__ import annotations
import sys
import subprocess
from typing import Optional


def copy_to_clipboard(text: str) -> bool:
    """Copies text to the system clipboard with full UTF-8 / Arabic support."""
    if not text:
        return False

    if sys.platform == "win32":
        # Primary Windows method: clip.exe with UTF-16LE encoding (universal Unicode support)
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-16le"))
            if p.returncode == 0:
                return True
        except Exception:
            pass

        # Fallback Windows method: PowerShell Set-Clipboard
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, encoding="utf-8")
            p.communicate(input=text)
            if p.returncode == 0:
                return True
        except Exception:
            pass
        return False

    elif sys.platform == "darwin":
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
        except Exception:
            return False

    else:
        # Linux (Wayland wl-copy or X11 xclip)
        for binary, args in [("wl-copy", []), ("xclip", ["-selection", "clipboard"])]:
            try:
                p = subprocess.Popen([binary] + args, stdin=subprocess.PIPE)
                p.communicate(input=text.encode("utf-8"))
                if p.returncode == 0:
                    return True
            except Exception:
                continue
        return False


def get_from_clipboard() -> Optional[str]:
    """Retrieves text from system clipboard."""
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard"],
                text=True,
                encoding="utf-8",
                timeout=2.0,
            )
            return out.rstrip("\r\n")
        except Exception:
            return None
    elif sys.platform == "darwin":
        try:
            return subprocess.check_output(["pbpaste"], text=True, timeout=2.0)
        except Exception:
            return None
    else:
        for binary, args in [("wl-paste", []), ("xclip", ["-selection", "clipboard", "-o"])]:
            try:
                return subprocess.check_output([binary] + args, text=True, timeout=2.0)
            except Exception:
                continue
        return None
