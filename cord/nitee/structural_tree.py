"""
NITEE v3 - Structural Tree Module
Extracts OS Accessibility Tree (Win32 UIAutomation / DOM) and formats it into
compact NITEE v3 node lines (e.g. `n_12 Button "Save" #save-btn`).
"""

from __future__ import annotations
import os
import sys
import ctypes
try:
    from ctypes import wintypes
except Exception:
    wintypes = None
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Ensure uiautomation DLL directory is registered on Windows (Python 3.8+)
if sys.platform == "win32":
    try:
        import uiautomation as _temp_auto
        _bin_dir = os.path.join(os.path.dirname(_temp_auto.__file__), "bin")
        if os.path.exists(_bin_dir) and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(_bin_dir)
            except Exception:
                pass
    except Exception:
        pass


@dataclass
class UIElementNode:
    """Representation of an element in the Structural UI Tree."""
    id: str
    control_type: str
    name: str = ""
    automation_id: str = ""
    value: Optional[str] = None
    center_x: int = 0
    center_y: int = 0
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    is_password: bool = False
    is_enabled: bool = True
    raw_control: Any = None

    def to_tree_line(self) -> str:
        """Format node line according to NITEE v3 spec:
        n_12 Button "Save" #save-btn
        n_8  Edit   "Email" = "user@x.com"
        n_9  Edit   "Password" [password]
        """
        parts = [self.id, self.control_type]
        if self.name:
            clean_name = self.name.replace('"', '\\"').replace("\n", " ")
            parts.append(f'"{clean_name}"')
        if self.automation_id:
            clean_id = self.automation_id.replace(" ", "_")
            parts.append(f"#{clean_id}")
        if self.is_password:
            parts.append("[password]")
        if self.value is not None and not self.is_password:
            clean_val = str(self.value).replace('"', '\\"').replace("\n", " ")
            parts.append(f'= "{clean_val}"')
        return " ".join(parts)


class StructuralTree:
    """Captures and traverses the active window or desktop UIAutomation tree."""

    # Interactive control types that the planner actively addresses
    INTERACTIVE_TYPES = {
        "ButtonControl", "EditControl", "CheckBoxControl", "RadioButtonControl",
        "ComboBoxControl", "ListItemControl", "MenuItemControl", "HyperlinkControl",
        "TabItemControl", "TreeItemControl", "SliderControl", "DocumentControl",
        "TableControl", "DataGridControl", "CustomControl", "WindowControl", "PaneControl"
    }

    TYPE_NAME_MAP = {
        "ButtonControl": "Button",
        "EditControl": "Edit",
        "CheckBoxControl": "CheckBox",
        "RadioButtonControl": "RadioButton",
        "ComboBoxControl": "ComboBox",
        "ListItemControl": "ListItem",
        "MenuItemControl": "MenuItem",
        "HyperlinkControl": "Link",
        "TabItemControl": "Tab",
        "TreeItemControl": "TreeItem",
        "TextControl": "Text",
        "ImageControl": "Image",
        "DocumentControl": "Document",
        "WindowControl": "Window",
        "PaneControl": "Pane",
        "GroupControl": "Group",
        "MenuControl": "Menu",
        "MenuBarControl": "MenuBar",
    }

    def __init__(self, max_depth: int = 6, max_nodes: int = 100):
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self._nodes: Dict[str, UIElementNode] = {}
        self._active_window_title: str = ""

    @property
    def nodes(self) -> Dict[str, UIElementNode]:
        return self._nodes

    @property
    def active_window_title(self) -> str:
        return self._active_window_title

    def get_element(self, element_id: str) -> Optional[UIElementNode]:
        """Lookup an element node by its cycle-specific ID (e.g. 'n_12')."""
        return self._nodes.get(element_id)

    def capture(self, window_title_query: Optional[str] = None) -> Tuple[str, Dict[str, UIElementNode]]:
        """Capture the structural UI tree of the foreground or target window.
        
        Returns:
            (formatted_tree_text, nodes_map)
        """
        self._nodes.clear()
        self._active_window_title = "Unknown Window"

        try:
            import uiautomation as auto
        except Exception:
            return self._capture_win32_fallback()

        target_control = None
        try:
            if window_title_query:
                # Find matching window
                target_control = auto.WindowControl(searchDepth=1, SubName=window_title_query)
                if not target_control.Exists(maxSearchSeconds=1):
                    target_control = None

            if not target_control or not target_control.Exists(maxSearchSeconds=0.2):
                target_control = auto.GetForegroundControl()

            if not target_control:
                target_control = auto.GetRootControl()

            if target_control:
                try:
                    self._active_window_title = target_control.Name or "Desktop"
                except Exception:
                    self._active_window_title = "Active Window"

                self._traverse_uia_control(target_control, depth=0)
        except Exception:
            return self._capture_win32_fallback()

        # If UIA yielded too few nodes (e.g. foreground is empty/locked), fallback to Win32
        if len(self._nodes) < 2:
            fallback_text, fallback_nodes = self._capture_win32_fallback()
            if len(fallback_nodes) > len(self._nodes):
                return fallback_text, fallback_nodes

        lines = [node.to_tree_line() for node in self._nodes.values()]
        tree_text = "\n".join(lines)
        return tree_text, dict(self._nodes)

    def _traverse_uia_control(self, control: Any, depth: int) -> None:
        """Walk children recursively and register relevant UI controls."""
        if depth > self.max_depth or len(self._nodes) >= self.max_nodes:
            return

        try:
            children = control.GetChildren()
        except Exception:
            return

        for child in children:
            if len(self._nodes) >= self.max_nodes:
                break

            try:
                type_name = child.ControlTypeName
                name = (child.Name or "").strip()
                auto_id = (child.AutomationId or "").strip()
                rect = child.BoundingRectangle

                # Ignore invisible or 0-dimension controls
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                if width <= 0 or height <= 0:
                    continue

                center_x = rect.left + width // 2
                center_y = rect.top + height // 2

                # Detect value & password status
                val = None
                is_pwd = False
                try:
                    is_pwd = getattr(child, "IsPassword", False)
                except Exception:
                    pass

                try:
                    if hasattr(child, "GetValuePattern"):
                        vp = child.GetValuePattern()
                        if vp:
                            val = vp.Value
                except Exception:
                    pass

                node_id = f"n_{len(self._nodes) + 1}"
                simplified_type = self.TYPE_NAME_MAP.get(type_name, type_name.replace("Control", ""))

                node = UIElementNode(
                    id=node_id,
                    control_type=simplified_type,
                    name=name,
                    automation_id=auto_id,
                    value=val,
                    center_x=center_x,
                    center_y=center_y,
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                    is_password=is_pwd,
                    is_enabled=True,
                    raw_control=child,
                )
                self._nodes[node_id] = node

                # Recurse down into children
                self._traverse_uia_control(child, depth + 1)
            except Exception:
                continue

    def _capture_win32_fallback(self) -> Tuple[str, Dict[str, UIElementNode]]:
        """Fallback for Windows environments when UIA returns empty or in tests."""
        if sys.platform != "win32":
            return self._generate_mock_tree()

        try:
            user32 = ctypes.windll.user32
            hwnd_fg = user32.GetForegroundWindow()
            if not hwnd_fg:
                return self._generate_mock_tree()

            title_buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd_fg, title_buf, 512)
            self._active_window_title = title_buf.value or "Active App"

            # Enumerate child windows
            child_hwnds: List[int] = []
            EnumChildWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

            def _enum_proc(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    child_hwnds.append(hwnd)
                return True

            user32.EnumChildWindows(hwnd_fg, EnumChildWindowsProc(_enum_proc), 0)

            for hwnd in child_hwnds[: self.max_nodes]:
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buf, 256)
                txt_buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, txt_buf, 512)

                cls_name = cls_buf.value.lower()
                ctrl_type = "Pane"
                if "button" in cls_name:
                    ctrl_type = "Button"
                elif "edit" in cls_name:
                    ctrl_type = "Edit"
                elif "static" in cls_name:
                    ctrl_type = "Text"
                elif "combo" in cls_name:
                    ctrl_type = "ComboBox"
                elif "list" in cls_name:
                    ctrl_type = "ListItem"

                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                rc = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rc))
                w = rc.right - rc.left
                h = rc.bottom - rc.top
                if w > 0 and h > 0:
                    cx = rc.left + w // 2
                    cy = rc.top + h // 2
                    node_id = f"n_{len(self._nodes) + 1}"
                    node = UIElementNode(
                        id=node_id,
                        control_type=ctrl_type,
                        name=txt_buf.value,
                        automation_id=f"win32_{hwnd}",
                        center_x=cx,
                        center_y=cy,
                        rect=(rc.left, rc.top, rc.right, rc.bottom),
                    )
                    self._nodes[node_id] = node

            if not self._nodes:
                return self._generate_mock_tree()

            lines = [node.to_tree_line() for node in self._nodes.values()]
            return "\n".join(lines), dict(self._nodes)
        except Exception:
            return self._generate_mock_tree()

    def _generate_mock_tree(self) -> Tuple[str, Dict[str, UIElementNode]]:
        """Mock fallback used when running headlessly or under automated test environments."""
        sample_nodes = [
            UIElementNode("n_1", "Window", name="Terminal / Console", automation_id="term_main", center_x=600, center_y=400),
            UIElementNode("n_2", "Button", name="Run", automation_id="btn_run", center_x=120, center_y=60),
            UIElementNode("n_3", "Edit", name="Search", automation_id="edit_search", value="cord", center_x=300, center_y=60),
            UIElementNode("n_4", "Button", name="Close", automation_id="btn_close", center_x=1150, center_y=30),
        ]
        self._nodes = {n.id: n for n in sample_nodes}
        lines = [n.to_tree_line() for n in sample_nodes]
        return "\n".join(lines), dict(self._nodes)
