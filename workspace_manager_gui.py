#!/usr/bin/env python3
"""
Claude Code Workspace Manager - Dear PyGui Desktop Application

A native desktop GUI for managing Claude Code workspaces.

Usage:
    python workspace_manager_gui.py
"""

import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Auto-install dearpygui if not present
try:
    import dearpygui.dearpygui as dpg
except ImportError:
    print("Dear PyGui not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "dearpygui"])
    import dearpygui.dearpygui as dpg

# Import core business logic
import workspace_core as core

# ============================================================================
# Theme Colors (matching the web dark theme)
# ============================================================================

COLORS = {
    "bg": (13, 17, 23),
    "surface": (22, 27, 34),
    "surface_2": (33, 38, 45),
    "border": (48, 54, 61),
    "text": (201, 209, 217),
    "text_dim": (139, 148, 158),
    "accent": (210, 168, 255),
    "accent_dim": (163, 113, 247),
    "green": (63, 185, 80),
    "red": (248, 81, 73),
    "blue": (88, 166, 255),
    "orange": (210, 153, 34),
}

# ============================================================================
# Main Application Class
# ============================================================================

class WorkspaceManagerApp:
    def __init__(self):
        self.workspaces = {}
        self.groups = {}
        self.templates = {}
        self.history = []
        self.current_workspace = None
        self.selected_template = None
        self.editing_group = None
        self.selected_group_color = None
        self.import_data = None

        # Widget IDs for updating
        self.sidebar_content_id = None
        self.main_content_id = None
        self.recent_content_id = None
        self.workspace_list_id = None

    def setup_theme(self):
        """Configure the dark theme."""
        with dpg.theme() as self.global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg"])
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["surface"])
                dpg.add_theme_color(dpg.mvThemeCol_PopupBg, COLORS["surface"])
                dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["surface_2"])
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, COLORS["accent_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, COLORS["surface"])
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, COLORS["surface_2"])
                dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text"])
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, COLORS["text_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["surface_2"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_Header, COLORS["surface_2"])
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, COLORS["accent_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_Tab, COLORS["surface_2"])
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, COLORS["border"])
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, COLORS["accent_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, COLORS["accent"])
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, COLORS["accent"])
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, COLORS["accent"])
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)

        # Button themes
        with dpg.theme() as self.btn_primary_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent_dim"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent"])

        with dpg.theme() as self.btn_success_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["green"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 200, 100))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (80, 200, 100))

        with dpg.theme() as self.btn_danger_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["red"])
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 100, 90))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (255, 100, 90))

    def load_all_data(self):
        """Load all data from core."""
        self.workspaces = core.load_workspaces()
        self.groups = core.load_groups()
        self.templates = core.load_templates()
        self.history = core.load_history(5)

    def create_main_window(self):
        """Create the main application window."""
        with dpg.window(tag="main_window", label="Claude Code Workspace Manager"):
            with dpg.group(horizontal=True):
                # Sidebar
                self.create_sidebar()

                # Main content area
                with dpg.child_window(tag="main_content", border=False):
                    self.show_empty_state()

    def create_sidebar(self):
        """Create the sidebar with workspaces list."""
        with dpg.child_window(tag="sidebar", width=280, border=False):
            # Header
            dpg.add_text("Claude Workspaces", color=COLORS["accent"])
            dpg.add_separator()

            # Action buttons
            with dpg.group(horizontal=True):
                btn = dpg.add_button(label="+ New", callback=self.create_new_workspace, width=100)
                dpg.bind_item_theme(btn, self.btn_primary_theme)
                dpg.add_button(label="Template", callback=self.show_template_modal, width=80)

            dpg.add_spacer(height=10)

            # Recent section
            with dpg.collapsing_header(label="Recent", default_open=True):
                with dpg.group(tag="recent_content"):
                    self.render_recent_history()

            dpg.add_spacer(height=5)

            # Workspaces section (grouped)
            with dpg.collapsing_header(label="Workspaces", default_open=True):
                with dpg.group(tag="workspace_list"):
                    self.render_workspace_list()

            # Spacer to push footer down
            dpg.add_spacer(height=20)

            # Footer buttons
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Import", callback=self.show_import_modal, width=80)
                dpg.add_button(label="Export All", callback=self.export_all, width=80)
                dpg.add_button(label="+ Group", callback=lambda: self.show_group_modal(), width=80)

    def render_recent_history(self):
        """Render the recent history section."""
        if dpg.does_item_exist("recent_content"):
            dpg.delete_item("recent_content", children_only=True)

        with dpg.group(parent="recent_content"):
            if not self.history:
                dpg.add_text("No recent launches", color=COLORS["text_dim"])
            else:
                for entry in self.history:
                    ws_name = entry.get('workspace_name', '')
                    launched_at = entry.get('launched_at', '')
                    exists = ws_name in self.workspaces

                    # Format time
                    try:
                        dt = datetime.fromisoformat(launched_at)
                        time_str = dt.strftime("%m/%d %H:%M")
                    except:
                        time_str = ""

                    with dpg.group(horizontal=True):
                        # Workspace name button
                        if exists:
                            dpg.add_button(
                                label=f"{ws_name[:20]}",
                                callback=lambda s, a, u: self.select_workspace(u),
                                user_data=ws_name,
                                width=150
                            )
                            # Launch button
                            launch_btn = dpg.add_button(
                                label="▶",
                                callback=lambda s, a, u: self.quick_launch(u),
                                user_data=ws_name,
                                width=30
                            )
                            dpg.bind_item_theme(launch_btn, self.btn_success_theme)
                        else:
                            dpg.add_text(f"{ws_name[:20]} (deleted)", color=COLORS["text_dim"])

    def render_workspace_list(self):
        """Render the workspace list grouped by groups."""
        if dpg.does_item_exist("workspace_list"):
            dpg.delete_item("workspace_list", children_only=True)

        with dpg.group(parent="workspace_list"):
            # Group workspaces
            grouped = {}
            ungrouped = []

            for name, ws in self.workspaces.items():
                group = ws.get('group', '')
                if group and group in self.groups:
                    if group not in grouped:
                        grouped[group] = []
                    grouped[group].append(name)
                else:
                    ungrouped.append(name)

            # Render groups
            for group_name, group_data in sorted(self.groups.items(), key=lambda x: x[1].get('order', 0)):
                color_hex = group_data.get('color', '#3fb950')
                # Convert hex to RGB tuple
                color = self.hex_to_rgb(color_hex)

                ws_in_group = grouped.get(group_name, [])

                with dpg.collapsing_header(label=f"{group_name} ({len(ws_in_group)})", default_open=True):
                    # Edit group button
                    dpg.add_button(
                        label="Edit Group",
                        callback=lambda s, a, u: self.show_group_modal(u),
                        user_data=group_name,
                        small=True
                    )

                    for ws_name in sorted(ws_in_group):
                        self.add_workspace_item(ws_name, color)

            # Ungrouped section
            if ungrouped:
                with dpg.collapsing_header(label=f"Ungrouped ({len(ungrouped)})", default_open=True):
                    for ws_name in sorted(ungrouped):
                        self.add_workspace_item(ws_name)

    def add_workspace_item(self, name: str, color=None):
        """Add a workspace item to the list."""
        with dpg.group(horizontal=True):
            if color:
                dpg.add_text("●", color=color)
            btn = dpg.add_button(
                label=name[:25],
                callback=lambda s, a, u: self.select_workspace(u),
                user_data=name,
                width=200 if not color else 185
            )
            if self.current_workspace == name:
                dpg.bind_item_theme(btn, self.btn_primary_theme)

    def hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def show_empty_state(self):
        """Show empty state when no workspace is selected."""
        if dpg.does_item_exist("main_content"):
            dpg.delete_item("main_content", children_only=True)

        with dpg.group(parent="main_content"):
            dpg.add_spacer(height=100)
            dpg.add_text("Select a workspace or create a new one", color=COLORS["text_dim"])
            dpg.add_spacer(height=20)
            btn = dpg.add_button(label="+ Create New Workspace", callback=self.create_new_workspace)
            dpg.bind_item_theme(btn, self.btn_primary_theme)

    def select_workspace(self, name: str):
        """Select a workspace to edit."""
        self.current_workspace = name
        self.render_workspace_list()
        self.show_workspace_form()

    def create_new_workspace(self):
        """Create a new workspace."""
        # Generate unique name
        base_name = "new-workspace"
        name = base_name
        counter = 1
        while name in self.workspaces:
            name = f"{base_name}-{counter}"
            counter += 1

        # Create with defaults
        ws = {**core.DEFAULT_WORKSPACE}
        ws['name'] = name
        ws['created'] = datetime.now().isoformat()
        self.workspaces[name] = ws
        core.save_workspaces(self.workspaces)

        self.current_workspace = name
        self.render_workspace_list()
        self.show_workspace_form()

    def show_workspace_form(self):
        """Show the workspace editing form."""
        if dpg.does_item_exist("main_content"):
            dpg.delete_item("main_content", children_only=True)

        if not self.current_workspace or self.current_workspace not in self.workspaces:
            self.show_empty_state()
            return

        ws = self.workspaces[self.current_workspace]

        with dpg.group(parent="main_content"):
            # Header
            with dpg.group(horizontal=True):
                dpg.add_text(f"Workspace: {self.current_workspace}", color=COLORS["accent"])
                dpg.add_spacer(width=20)

                # Template badge
                if ws.get('template_source'):
                    dpg.add_text(f"[{ws['template_source']}]", color=COLORS["text_dim"])

                dpg.add_spacer(width=20)

                # Action buttons
                dpg.add_button(label="Export", callback=self.export_current, width=80)
                dpg.add_button(label="Save as Template", callback=self.show_save_template_modal, width=120)

                launch_btn = dpg.add_button(label="▶ Launch", callback=self.launch_current, width=100)
                dpg.bind_item_theme(launch_btn, self.btn_success_theme)

            dpg.add_separator()
            dpg.add_spacer(height=10)

            # Tab bar
            with dpg.tab_bar():
                # Basic tab
                with dpg.tab(label="Basic"):
                    self.render_basic_tab(ws)

                # Model tab
                with dpg.tab(label="Model"):
                    self.render_model_tab(ws)

                # Tools tab
                with dpg.tab(label="Tools"):
                    self.render_tools_tab(ws)

                # Advanced tab
                with dpg.tab(label="Advanced"):
                    self.render_advanced_tab(ws)

                # MCP tab
                with dpg.tab(label="MCP"):
                    self.render_mcp_tab(ws)

            dpg.add_spacer(height=20)

            # Bottom buttons
            with dpg.group(horizontal=True):
                delete_btn = dpg.add_button(label="Delete Workspace", callback=self.delete_current, width=150)
                dpg.bind_item_theme(delete_btn, self.btn_danger_theme)

                dpg.add_spacer(width=20)

                save_btn = dpg.add_button(label="Save Changes", callback=self.save_current, width=150)
                dpg.bind_item_theme(save_btn, self.btn_primary_theme)

    def render_basic_tab(self, ws: dict):
        """Render the basic settings tab."""
        dpg.add_spacer(height=10)

        dpg.add_text("Name")
        dpg.add_input_text(tag="ws_name", default_value=ws.get('name', ''), width=400)

        dpg.add_spacer(height=5)
        dpg.add_text("Description")
        dpg.add_input_text(tag="ws_description", default_value=ws.get('description', ''), width=400)

        dpg.add_spacer(height=5)
        dpg.add_text("Working Directory")
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="ws_working_dir", default_value=ws.get('working_dir', ''), width=350)
            dpg.add_button(label="Browse", callback=self.browse_directory)

        dpg.add_spacer(height=5)
        dpg.add_text("Group")
        group_names = [""] + list(self.groups.keys())
        current_group = ws.get('group', '')
        default_idx = group_names.index(current_group) if current_group in group_names else 0
        dpg.add_combo(tag="ws_group", items=group_names, default_value=current_group, width=400)

        dpg.add_spacer(height=5)
        dpg.add_text("Additional Directories (one per line)")
        additional_dirs = "\n".join(ws.get('additional_dirs', []))
        dpg.add_input_text(tag="ws_additional_dirs", default_value=additional_dirs, multiline=True, width=400, height=80)

    def render_model_tab(self, ws: dict):
        """Render the model settings tab."""
        dpg.add_spacer(height=10)

        dpg.add_text("Model")
        models = ["", "opus", "sonnet", "haiku"]
        dpg.add_combo(tag="ws_model", items=models, default_value=ws.get('model', ''), width=300)

        dpg.add_spacer(height=5)
        dpg.add_text("Fallback Model")
        dpg.add_combo(tag="ws_fallback_model", items=models, default_value=ws.get('fallback_model', ''), width=300)

        dpg.add_spacer(height=10)
        dpg.add_separator()

        dpg.add_spacer(height=10)
        dpg.add_text("Permissions")
        dpg.add_checkbox(tag="ws_skip_permissions", label="Skip Permission Prompts (Dangerous!)", default_value=ws.get('skip_permissions', False))

        dpg.add_spacer(height=5)
        dpg.add_text("Permission Mode")
        permission_modes = ["", "default", "acceptEdits", "bypassPermissions", "plan"]
        dpg.add_combo(tag="ws_permission_mode", items=permission_modes, default_value=ws.get('permission_mode', ''), width=300)

    def render_tools_tab(self, ws: dict):
        """Render the tools settings tab."""
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            # Allowed tools
            with dpg.group():
                dpg.add_text("Allowed Tools")
                dpg.add_text("(Select tools to allow)", color=COLORS["text_dim"])

                allowed = ws.get('allowed_tools', [])
                for tool in core.BUILTIN_TOOLS:
                    dpg.add_checkbox(
                        tag=f"ws_allowed_{tool}",
                        label=tool,
                        default_value=tool in allowed
                    )

            dpg.add_spacer(width=50)

            # Disallowed tools
            with dpg.group():
                dpg.add_text("Disallowed Tools")
                dpg.add_text("(Select tools to block)", color=COLORS["text_dim"])

                disallowed = ws.get('disallowed_tools', [])
                for tool in core.BUILTIN_TOOLS:
                    dpg.add_checkbox(
                        tag=f"ws_disallowed_{tool}",
                        label=tool,
                        default_value=tool in disallowed
                    )

    def render_advanced_tab(self, ws: dict):
        """Render the advanced settings tab."""
        dpg.add_spacer(height=10)

        dpg.add_text("System Prompt (append)")
        dpg.add_input_text(tag="ws_append_system_prompt", default_value=ws.get('append_system_prompt', ''), multiline=True, width=500, height=100)

        dpg.add_spacer(height=5)
        dpg.add_text("System Prompt File")
        dpg.add_input_text(tag="ws_system_prompt_file", default_value=ws.get('system_prompt_file', ''), width=500)

        dpg.add_spacer(height=5)
        dpg.add_text("Agent")
        dpg.add_input_text(tag="ws_agent", default_value=ws.get('agent', ''), width=300)

        dpg.add_spacer(height=10)
        dpg.add_separator()

        dpg.add_spacer(height=10)
        dpg.add_text("IDE Integration")
        ides = ["terminal", "vscode", "vscode-insiders", "cursor"]
        dpg.add_combo(tag="ws_ide", items=ides, default_value=ws.get('ide', 'terminal'), width=200)

        dpg.add_checkbox(tag="ws_open_folder_in_ide", label="Open folder in IDE on launch", default_value=ws.get('open_folder_in_ide', False))

        dpg.add_spacer(height=10)
        dpg.add_separator()

        dpg.add_spacer(height=10)
        dpg.add_text("Debug")
        dpg.add_checkbox(tag="ws_verbose", label="Verbose output", default_value=ws.get('verbose', False))

        dpg.add_text("Debug Categories (comma-separated)")
        dpg.add_input_text(tag="ws_debug_categories", default_value=ws.get('debug_categories', ''), width=400)

        dpg.add_spacer(height=10)
        dpg.add_separator()

        dpg.add_spacer(height=10)
        dpg.add_text("Environment Variables (KEY=VALUE, one per line)")
        env_vars = ws.get('env_vars', {})
        env_str = "\n".join(f"{k}={v}" for k, v in env_vars.items())
        dpg.add_input_text(tag="ws_env_vars", default_value=env_str, multiline=True, width=500, height=80)

    def render_mcp_tab(self, ws: dict):
        """Render the MCP settings tab."""
        dpg.add_spacer(height=10)

        dpg.add_text("MCP Config File")
        dpg.add_input_text(tag="ws_mcp_config", default_value=ws.get('mcp_config', ''), width=500)

        dpg.add_spacer(height=5)
        dpg.add_checkbox(tag="ws_strict_mcp", label="Strict MCP Config (only use specified servers)", default_value=ws.get('strict_mcp', False))

        dpg.add_spacer(height=20)
        dpg.add_separator()

        dpg.add_spacer(height=10)
        dpg.add_text("CLAUDE.md Initialization")
        dpg.add_checkbox(tag="ws_init_claude_md", label="Create CLAUDE.md if missing", default_value=ws.get('init_claude_md', False))

        dpg.add_spacer(height=5)
        dpg.add_text("CLAUDE.md Content")
        dpg.add_input_text(tag="ws_claude_md_content", default_value=ws.get('claude_md_content', ''), multiline=True, width=500, height=150)

    def browse_directory(self):
        """Open file dialog to browse for directory."""
        # Dear PyGui doesn't have a native folder dialog, so we'll use the file dialog
        dpg.add_file_dialog(
            directory_selector=True,
            callback=self.directory_selected,
            tag="file_dialog",
            width=700,
            height=400
        )

    def directory_selected(self, sender, app_data):
        """Handle directory selection."""
        if app_data and app_data.get('file_path_name'):
            dpg.set_value("ws_working_dir", app_data['file_path_name'])
        dpg.delete_item("file_dialog")

    def save_current(self):
        """Save the current workspace."""
        if not self.current_workspace:
            return

        old_name = self.current_workspace
        new_name = dpg.get_value("ws_name").strip()

        if not new_name:
            self.show_toast("Error: Name is required", error=True)
            return

        # Collect form data
        ws = {
            'name': new_name,
            'description': dpg.get_value("ws_description"),
            'working_dir': dpg.get_value("ws_working_dir"),
            'group': dpg.get_value("ws_group"),
            'model': dpg.get_value("ws_model"),
            'fallback_model': dpg.get_value("ws_fallback_model"),
            'skip_permissions': dpg.get_value("ws_skip_permissions"),
            'permission_mode': dpg.get_value("ws_permission_mode"),
            'append_system_prompt': dpg.get_value("ws_append_system_prompt"),
            'system_prompt_file': dpg.get_value("ws_system_prompt_file"),
            'agent': dpg.get_value("ws_agent"),
            'ide': dpg.get_value("ws_ide"),
            'open_folder_in_ide': dpg.get_value("ws_open_folder_in_ide"),
            'verbose': dpg.get_value("ws_verbose"),
            'debug_categories': dpg.get_value("ws_debug_categories"),
            'mcp_config': dpg.get_value("ws_mcp_config"),
            'strict_mcp': dpg.get_value("ws_strict_mcp"),
            'init_claude_md': dpg.get_value("ws_init_claude_md"),
            'claude_md_content': dpg.get_value("ws_claude_md_content"),
        }

        # Additional dirs
        additional_dirs_str = dpg.get_value("ws_additional_dirs")
        ws['additional_dirs'] = [d.strip() for d in additional_dirs_str.split('\n') if d.strip()]

        # Allowed tools
        allowed_tools = []
        for tool in core.BUILTIN_TOOLS:
            if dpg.get_value(f"ws_allowed_{tool}"):
                allowed_tools.append(tool)
        ws['allowed_tools'] = allowed_tools

        # Disallowed tools
        disallowed_tools = []
        for tool in core.BUILTIN_TOOLS:
            if dpg.get_value(f"ws_disallowed_{tool}"):
                disallowed_tools.append(tool)
        ws['disallowed_tools'] = disallowed_tools

        # Env vars
        env_vars_str = dpg.get_value("ws_env_vars")
        env_vars = {}
        for line in env_vars_str.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
        ws['env_vars'] = env_vars

        # Preserve metadata
        if old_name in self.workspaces:
            ws['created'] = self.workspaces[old_name].get('created', datetime.now().isoformat())
            ws['last_used'] = self.workspaces[old_name].get('last_used', '')
            ws['use_count'] = self.workspaces[old_name].get('use_count', 0)
            ws['template_source'] = self.workspaces[old_name].get('template_source', '')

        # Handle rename
        if new_name != old_name:
            if new_name in self.workspaces:
                self.show_toast("Error: Workspace with that name already exists", error=True)
                return
            del self.workspaces[old_name]

        self.workspaces[new_name] = ws
        core.save_workspaces(self.workspaces)

        self.current_workspace = new_name
        self.render_workspace_list()
        self.show_toast("Workspace saved!")

    def delete_current(self):
        """Delete the current workspace."""
        if not self.current_workspace:
            return

        name = self.current_workspace
        del self.workspaces[name]
        core.save_workspaces(self.workspaces)

        self.current_workspace = None
        self.render_workspace_list()
        self.show_empty_state()
        self.show_toast(f"Deleted {name}")

    def launch_current(self):
        """Launch the current workspace."""
        if not self.current_workspace:
            return

        self.save_current()
        if core.launch_workspace(self.current_workspace):
            self.load_all_data()
            self.render_recent_history()
            self.show_toast(f"Launched {self.current_workspace}")
        else:
            self.show_toast("Failed to launch workspace", error=True)

    def quick_launch(self, name: str):
        """Quick launch a workspace from history."""
        if core.launch_workspace(name):
            self.load_all_data()
            self.render_recent_history()
            self.show_toast(f"Launched {name}")
        else:
            self.show_toast("Failed to launch workspace", error=True)

    def export_current(self):
        """Export the current workspace."""
        if not self.current_workspace:
            return

        export_data = core.export_workspace(self.current_workspace)
        if export_data:
            # Save to file
            filename = f"{self.current_workspace}_export.json"
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            self.show_toast(f"Exported to {filename}")
        else:
            self.show_toast("Export failed", error=True)

    def export_all(self):
        """Export all workspaces."""
        export_data = core.export_all_workspaces()
        filename = "workspaces_export.json"
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        self.show_toast(f"Exported all to {filename}")

    # =========================================================================
    # Modals
    # =========================================================================

    def show_template_modal(self):
        """Show template selection modal."""
        if dpg.does_item_exist("template_modal"):
            dpg.delete_item("template_modal")

        with dpg.window(
            label="New from Template",
            tag="template_modal",
            modal=True,
            width=500,
            height=400,
            pos=[200, 100]
        ):
            dpg.add_text("Select a template:")
            dpg.add_separator()

            self.selected_template = None

            # Template grid
            with dpg.group():
                for tid, template in self.templates.items():
                    with dpg.group(horizontal=True):
                        is_builtin = template.get('builtin', False)
                        label = f"{'[Built-in] ' if is_builtin else ''}{template['name']}"

                        btn = dpg.add_button(
                            label=label,
                            callback=lambda s, a, u: self.select_template(u),
                            user_data=tid,
                            width=400
                        )

                    dpg.add_text(f"  {template.get('description', '')}", color=COLORS["text_dim"])
                    dpg.add_spacer(height=5)

            dpg.add_separator()

            dpg.add_text("Workspace Name")
            dpg.add_input_text(tag="template_ws_name", width=300)

            dpg.add_text("Working Directory")
            dpg.add_input_text(tag="template_ws_dir", width=300)

            dpg.add_spacer(height=10)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("template_modal"), width=100)
                create_btn = dpg.add_button(label="Create", callback=self.create_from_template, width=100)
                dpg.bind_item_theme(create_btn, self.btn_primary_theme)

    def select_template(self, template_id: str):
        """Select a template."""
        self.selected_template = template_id
        self.show_toast(f"Selected: {self.templates[template_id]['name']}")

    def create_from_template(self):
        """Create workspace from selected template."""
        if not self.selected_template:
            self.show_toast("Please select a template", error=True)
            return

        name = dpg.get_value("template_ws_name").strip()
        working_dir = dpg.get_value("template_ws_dir").strip()

        if not name:
            self.show_toast("Please enter a workspace name", error=True)
            return

        try:
            core.create_workspace_from_template(self.selected_template, name, working_dir)
            self.load_all_data()
            self.current_workspace = name
            dpg.delete_item("template_modal")
            self.render_workspace_list()
            self.show_workspace_form()
            self.show_toast(f"Created {name} from template")
        except ValueError as e:
            self.show_toast(str(e), error=True)

    def show_import_modal(self):
        """Show import modal."""
        if dpg.does_item_exist("import_modal"):
            dpg.delete_item("import_modal")

        with dpg.window(
            label="Import Workspaces",
            tag="import_modal",
            modal=True,
            width=500,
            height=350,
            pos=[200, 100]
        ):
            dpg.add_text("Select a JSON file to import:")
            dpg.add_separator()

            dpg.add_button(label="Browse...", callback=self.browse_import_file, width=100)

            dpg.add_spacer(height=10)
            dpg.add_text("", tag="import_preview_text")

            dpg.add_spacer(height=10)
            dpg.add_text("If workspace exists:")
            dpg.add_combo(
                tag="import_conflict_resolution",
                items=["skip", "rename", "overwrite"],
                default_value="skip",
                width=200
            )

            dpg.add_spacer(height=20)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("import_modal"), width=100)
                import_btn = dpg.add_button(label="Import", callback=self.perform_import, width=100)
                dpg.bind_item_theme(import_btn, self.btn_primary_theme)

    def browse_import_file(self):
        """Browse for import file."""
        dpg.add_file_dialog(
            callback=self.import_file_selected,
            tag="import_file_dialog",
            width=700,
            height=400,
            default_path="."
        )

    def import_file_selected(self, sender, app_data):
        """Handle import file selection."""
        dpg.delete_item("import_file_dialog")

        if not app_data or not app_data.get('file_path_name'):
            return

        file_path = app_data['file_path_name']

        try:
            with open(file_path, 'r') as f:
                self.import_data = json.load(f)

            workspaces = self.import_data.get('workspaces', [])
            preview = f"Found {len(workspaces)} workspace(s) to import:\n"
            for ws in workspaces[:5]:
                preview += f"  - {ws.get('name', 'unnamed')}\n"
            if len(workspaces) > 5:
                preview += f"  ... and {len(workspaces) - 5} more"

            dpg.set_value("import_preview_text", preview)

        except Exception as e:
            self.show_toast(f"Error reading file: {e}", error=True)
            self.import_data = None

    def perform_import(self):
        """Perform the import."""
        if not self.import_data:
            self.show_toast("No file selected", error=True)
            return

        conflict_resolution = dpg.get_value("import_conflict_resolution")

        try:
            result = core.import_workspaces(self.import_data, conflict_resolution)
            self.load_all_data()
            self.render_workspace_list()
            dpg.delete_item("import_modal")

            msg = f"Imported: {len(result['imported'])}"
            if result['skipped']:
                msg += f", Skipped: {len(result['skipped'])}"
            if result['renamed']:
                msg += f", Renamed: {len(result['renamed'])}"

            self.show_toast(msg)
            self.import_data = None

        except ValueError as e:
            self.show_toast(str(e), error=True)

    def show_group_modal(self, group_name: str = None):
        """Show group management modal."""
        if dpg.does_item_exist("group_modal"):
            dpg.delete_item("group_modal")

        self.editing_group = group_name
        is_edit = group_name is not None

        group_data = self.groups.get(group_name, {}) if is_edit else {}
        self.selected_group_color = group_data.get('color', core.GROUP_COLORS[0])

        with dpg.window(
            label="Edit Group" if is_edit else "New Group",
            tag="group_modal",
            modal=True,
            width=400,
            height=300,
            pos=[250, 150]
        ):
            dpg.add_text("Group Name")
            dpg.add_input_text(tag="group_name_input", default_value=group_name or "", width=300)

            dpg.add_spacer(height=10)
            dpg.add_text("Color")

            # Color picker buttons
            with dpg.group(horizontal=True):
                for color in core.GROUP_COLORS:
                    rgb = self.hex_to_rgb(color)
                    with dpg.theme() as color_theme:
                        with dpg.theme_component(dpg.mvButton):
                            dpg.add_theme_color(dpg.mvThemeCol_Button, rgb)
                            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, rgb)

                    btn = dpg.add_button(
                        label="  ",
                        callback=lambda s, a, u: self.select_group_color(u),
                        user_data=color,
                        width=30,
                        height=30
                    )
                    dpg.bind_item_theme(btn, color_theme)

            dpg.add_spacer(height=20)

            with dpg.group(horizontal=True):
                if is_edit:
                    delete_btn = dpg.add_button(label="Delete", callback=self.delete_group_from_modal, width=80)
                    dpg.bind_item_theme(delete_btn, self.btn_danger_theme)

                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("group_modal"), width=80)
                save_btn = dpg.add_button(label="Save", callback=self.save_group_from_modal, width=80)
                dpg.bind_item_theme(save_btn, self.btn_primary_theme)

    def select_group_color(self, color: str):
        """Select a group color."""
        self.selected_group_color = color
        self.show_toast(f"Selected color: {color}")

    def save_group_from_modal(self):
        """Save group from modal."""
        name = dpg.get_value("group_name_input").strip()

        if not name:
            self.show_toast("Group name is required", error=True)
            return

        try:
            if self.editing_group:
                # Update existing
                core.update_group(self.editing_group, new_name=name, color=self.selected_group_color)
            else:
                # Create new
                core.create_group(name, self.selected_group_color)

            self.load_all_data()
            self.render_workspace_list()
            dpg.delete_item("group_modal")
            self.show_toast(f"Group '{name}' saved")

        except ValueError as e:
            self.show_toast(str(e), error=True)

    def delete_group_from_modal(self):
        """Delete group from modal."""
        if self.editing_group:
            core.delete_group(self.editing_group)
            self.load_all_data()
            self.render_workspace_list()
            dpg.delete_item("group_modal")
            self.show_toast(f"Group '{self.editing_group}' deleted")

    def show_save_template_modal(self):
        """Show save as template modal."""
        if not self.current_workspace:
            return

        if dpg.does_item_exist("save_template_modal"):
            dpg.delete_item("save_template_modal")

        ws = self.workspaces.get(self.current_workspace, {})

        with dpg.window(
            label="Save as Template",
            tag="save_template_modal",
            modal=True,
            width=400,
            height=250,
            pos=[250, 150]
        ):
            dpg.add_text("Template Name")
            dpg.add_input_text(tag="save_template_name", default_value=ws.get('name', ''), width=300)

            dpg.add_spacer(height=5)
            dpg.add_text("Description")
            dpg.add_input_text(tag="save_template_desc", width=300)

            dpg.add_spacer(height=10)
            dpg.add_text("The current settings (except name and directory)", color=COLORS["text_dim"])
            dpg.add_text("will be saved as a reusable template.", color=COLORS["text_dim"])

            dpg.add_spacer(height=20)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("save_template_modal"), width=100)
                save_btn = dpg.add_button(label="Save Template", callback=self.save_as_template, width=120)
                dpg.bind_item_theme(save_btn, self.btn_primary_theme)

    def save_as_template(self):
        """Save current workspace as template."""
        name = dpg.get_value("save_template_name").strip()
        desc = dpg.get_value("save_template_desc").strip()

        if not name:
            self.show_toast("Template name is required", error=True)
            return

        template_id = name.lower().replace(' ', '-')

        if template_id in core.BUILTIN_TEMPLATES:
            self.show_toast("Cannot override built-in template", error=True)
            return

        ws = self.workspaces.get(self.current_workspace, {})

        # Extract config (exclude name, working_dir, metadata)
        config = {k: v for k, v in ws.items() if k not in [
            'name', 'working_dir', 'created', 'last_used', 'use_count',
            'group', 'template_source'
        ]}

        template = {
            'name': name,
            'description': desc,
            'icon': 'folder',
            'config': config
        }

        core.save_user_template(template_id, template)
        self.load_all_data()
        dpg.delete_item("save_template_modal")
        self.show_toast(f"Template '{name}' saved")

    def show_toast(self, message: str, error: bool = False):
        """Show a toast notification."""
        tag = f"toast_{id(message)}"

        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        color = COLORS["red"] if error else COLORS["green"]

        with dpg.window(
            tag=tag,
            label="",
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            pos=[dpg.get_viewport_width() - 320, dpg.get_viewport_height() - 60],
            width=300,
            height=40
        ):
            dpg.add_text(message, color=color)

        # Auto-close after 3 seconds
        def close_toast():
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

        dpg.set_frame_callback(dpg.get_frame_count() + 180, close_toast)

    def run(self):
        """Run the application."""
        dpg.create_context()

        self.setup_theme()
        self.load_all_data()

        dpg.create_viewport(title="Claude Code Workspace Manager", width=1200, height=800)
        dpg.setup_dearpygui()

        self.create_main_window()

        dpg.bind_theme(self.global_theme)
        dpg.set_primary_window("main_window", True)

        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    app = WorkspaceManagerApp()
    app.run()


if __name__ == '__main__':
    main()
