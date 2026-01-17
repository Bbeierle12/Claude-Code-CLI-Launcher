#!/usr/bin/env python3
"""
Claude Code Workspace Manager - Core Business Logic

This module contains all the non-UI logic for managing Claude Code workspaces:
- Storage (workspaces, groups, templates, history)
- Command generation
- Terminal/IDE launching
"""

import json
import os
import platform
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

CONFIG_DIR = Path.home() / ".claude-workspaces"
WORKSPACES_FILE = CONFIG_DIR / "workspaces.json"
LAUNCH_SCRIPT = CONFIG_DIR / "launch.sh"
LAUNCH_SCRIPT_WIN = CONFIG_DIR / "launch.bat"

# Built-in tools for Claude Code
BUILTIN_TOOLS = [
    "Read", "Edit", "Write", "Bash", "Glob", "Grep",
    "LS", "Task", "WebFetch", "WebSearch", "TodoRead", "TodoWrite"
]

# Built-in workspace templates
BUILTIN_TEMPLATES = {
    "python-project": {
        "name": "Python Project",
        "description": "Python development with best practices",
        "icon": "python",
        "builtin": True,
        "config": {
            "model": "sonnet",
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            "append_system_prompt": "This is a Python project. Follow PEP 8 style guidelines and use type hints where appropriate.",
            "init_claude_md": True,
            "claude_md_content": "# Python Project\n\n## Setup\n- Use virtual environment (venv or conda)\n- Follow PEP 8 style guide\n- Use type hints for function signatures"
        }
    },
    "nodejs-project": {
        "name": "Node.js Project",
        "description": "Node.js/npm development setup",
        "icon": "nodejs",
        "builtin": True,
        "config": {
            "model": "sonnet",
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            "append_system_prompt": "This is a Node.js project using npm. Follow modern ES6+ conventions."
        }
    },
    "react-app": {
        "name": "React Application",
        "description": "React frontend development",
        "icon": "react",
        "builtin": True,
        "config": {
            "model": "sonnet",
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebFetch"],
            "append_system_prompt": "This is a React application. Use functional components and hooks. Follow React best practices."
        }
    },
    "rust-project": {
        "name": "Rust Project",
        "description": "Rust development with Cargo",
        "icon": "rust",
        "builtin": True,
        "config": {
            "model": "sonnet",
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            "append_system_prompt": "This is a Rust project using Cargo. Follow Rust idioms and ensure memory safety."
        }
    },
    "general": {
        "name": "General Purpose",
        "description": "Basic workspace with common tools",
        "icon": "folder",
        "builtin": True,
        "config": {
            "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
        }
    }
}

# Default group colors
GROUP_COLORS = [
    "#3fb950",  # Green
    "#58a6ff",  # Blue
    "#d29922",  # Orange
    "#a371f7",  # Purple
    "#f85149",  # Red
    "#79c0ff",  # Light Blue
    "#d2a8ff",  # Light Purple
    "#7ee787",  # Light Green
]

# Default workspace template
DEFAULT_WORKSPACE = {
    "name": "",
    "description": "",
    "working_dir": "",
    "additional_dirs": [],
    "model": "",
    "fallback_model": "",
    "skip_permissions": False,
    "permission_mode": "",
    "allowed_tools": [],
    "disallowed_tools": [],
    "append_system_prompt": "",
    "system_prompt_file": "",
    "mcp_config": "",
    "strict_mcp": False,
    "agent": "",
    "verbose": False,
    "debug_categories": "",
    "env_vars": {},
    "ide": "terminal",
    "open_folder_in_ide": False,
    "init_claude_md": False,
    "claude_md_content": "",
    "created": "",
    "last_used": "",
    "use_count": 0,
    "group": "",
    "template_source": ""
}

# Current data schema version
DATA_VERSION = 2

# ============================================================================
# Storage Layer
# ============================================================================

def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def get_default_data() -> dict:
    """Get default v2 data structure."""
    return {
        "version": DATA_VERSION,
        "workspaces": {},
        "groups": {},
        "templates": {},
        "history": [],
        "settings": {
            "history_limit": 20
        }
    }

def migrate_v1_to_v2(old_data: dict) -> dict:
    """Migrate v1 (flat workspace dict) to v2 structure."""
    new_data = get_default_data()
    new_data["workspaces"] = old_data
    for name, ws in new_data["workspaces"].items():
        if "group" not in ws:
            ws["group"] = ""
        if "template_source" not in ws:
            ws["template_source"] = ""
    return new_data

def load_data() -> dict:
    """Load full data structure from JSON file with auto-migration."""
    ensure_config_dir()
    if WORKSPACES_FILE.exists():
        try:
            with open(WORKSPACES_FILE, 'r') as f:
                data = json.load(f)

            if "version" not in data:
                data = migrate_v1_to_v2(data)
                save_data(data)

            default = get_default_data()
            for key in default:
                if key not in data:
                    data[key] = default[key]

            return data
        except (json.JSONDecodeError, IOError):
            return get_default_data()
    return get_default_data()

def save_data(data: dict):
    """Save full data structure to JSON file."""
    ensure_config_dir()
    data["version"] = DATA_VERSION
    with open(WORKSPACES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_workspaces() -> dict:
    """Load workspaces from JSON file."""
    data = load_data()
    return data.get("workspaces", {})

def save_workspaces(workspaces: dict):
    """Save workspaces to JSON file."""
    data = load_data()
    data["workspaces"] = workspaces
    save_data(data)

def get_workspace(name: str) -> dict | None:
    """Get a single workspace by name."""
    workspaces = load_workspaces()
    return workspaces.get(name)

def create_workspace(workspace: dict) -> dict:
    """Create or update a workspace."""
    name = workspace.get('name', '').strip()
    if not name:
        raise ValueError("Workspace name is required")

    workspaces = load_workspaces()
    ws = {**DEFAULT_WORKSPACE, **workspace}

    if name not in workspaces:
        ws['created'] = datetime.now().isoformat()
    else:
        ws['created'] = workspaces[name].get('created', datetime.now().isoformat())

    workspaces[name] = ws
    save_workspaces(workspaces)
    return ws

def delete_workspace(name: str) -> bool:
    """Delete a workspace."""
    workspaces = load_workspaces()
    if name in workspaces:
        del workspaces[name]
        save_workspaces(workspaces)
        return True
    return False

# ============================================================================
# Groups Functions
# ============================================================================

def load_groups() -> dict:
    """Load groups from data."""
    data = load_data()
    return data.get("groups", {})

def save_groups(groups: dict):
    """Save groups to data."""
    data = load_data()
    data["groups"] = groups
    save_data(data)

def get_next_group_color() -> str:
    """Get the next available group color."""
    groups = load_groups()
    used_colors = {g.get("color") for g in groups.values()}
    for color in GROUP_COLORS:
        if color not in used_colors:
            return color
    return GROUP_COLORS[0]

def create_group(name: str, color: str = None) -> dict:
    """Create a new group."""
    if not name:
        raise ValueError("Group name is required")

    groups = load_groups()
    if name in groups:
        raise ValueError("Group already exists")

    groups[name] = {
        "order": len(groups),
        "color": color or get_next_group_color()
    }
    save_groups(groups)
    return groups[name]

def update_group(name: str, new_name: str = None, color: str = None) -> bool:
    """Update a group."""
    groups = load_groups()
    if name not in groups:
        return False

    if new_name and new_name != name:
        if new_name in groups:
            raise ValueError("Group with new name already exists")
        groups[new_name] = groups.pop(name)
        workspaces = load_workspaces()
        for ws in workspaces.values():
            if ws.get('group') == name:
                ws['group'] = new_name
        save_workspaces(workspaces)
        name = new_name

    if color:
        groups[name]['color'] = color

    save_groups(groups)
    return True

def delete_group(name: str) -> bool:
    """Delete a group."""
    groups = load_groups()
    if name not in groups:
        return False

    workspaces = load_workspaces()
    for ws in workspaces.values():
        if ws.get('group') == name:
            ws['group'] = ""
    save_workspaces(workspaces)

    del groups[name]
    save_groups(groups)
    return True

def set_workspace_group(workspace_name: str, group_name: str) -> bool:
    """Assign a workspace to a group."""
    workspaces = load_workspaces()
    if workspace_name not in workspaces:
        return False

    workspaces[workspace_name]['group'] = group_name
    save_workspaces(workspaces)
    return True

# ============================================================================
# Templates Functions
# ============================================================================

def load_templates() -> dict:
    """Load all templates (builtin + user-defined)."""
    data = load_data()
    user_templates = data.get("templates", {})
    all_templates = {**BUILTIN_TEMPLATES}
    for tid, template in user_templates.items():
        template["builtin"] = False
        all_templates[tid] = template
    return all_templates

def save_user_template(template_id: str, template: dict):
    """Save a user-defined template."""
    data = load_data()
    if "templates" not in data:
        data["templates"] = {}
    template["builtin"] = False
    data["templates"][template_id] = template
    save_data(data)

def delete_user_template(template_id: str) -> bool:
    """Delete a user-defined template."""
    if template_id in BUILTIN_TEMPLATES:
        return False
    data = load_data()
    if template_id in data.get("templates", {}):
        del data["templates"][template_id]
        save_data(data)
        return True
    return False

def create_workspace_from_template(template_id: str, name: str, working_dir: str = "", overrides: dict = None) -> dict:
    """Create a workspace from a template."""
    templates = load_templates()
    if template_id not in templates:
        raise ValueError("Template not found")

    workspaces = load_workspaces()
    if name in workspaces:
        raise ValueError("Workspace already exists")

    template = templates[template_id]
    config = template.get('config', {})

    workspace = {**DEFAULT_WORKSPACE, **config, **(overrides or {})}
    workspace['name'] = name
    workspace['working_dir'] = working_dir
    workspace['template_source'] = template_id
    workspace['created'] = datetime.now().isoformat()

    workspaces[name] = workspace
    save_workspaces(workspaces)
    return workspace

# ============================================================================
# History Functions
# ============================================================================

def load_history(limit: int = 20) -> list:
    """Load launch history."""
    data = load_data()
    history = data.get("history", [])
    return history[:limit]

def add_history_entry(workspace_name: str, working_dir: str):
    """Add a launch to history."""
    data = load_data()
    history = data.get("history", [])
    settings = data.get("settings", {})
    limit = settings.get("history_limit", 20)

    entry = {
        "id": str(uuid.uuid4())[:8],
        "workspace_name": workspace_name,
        "working_dir": working_dir,
        "launched_at": datetime.now().isoformat()
    }

    history.insert(0, entry)
    if len(history) > limit:
        history = history[:limit]

    data["history"] = history
    save_data(data)

def clear_history():
    """Clear all history."""
    data = load_data()
    data["history"] = []
    save_data(data)

# ============================================================================
# Command Generation
# ============================================================================

def build_command(ws: dict) -> list:
    """Build Claude CLI command from workspace configuration."""
    cmd = ["claude"]

    if ws.get('model'):
        cmd.extend(["--model", ws['model']])
    if ws.get('fallback_model'):
        cmd.extend(["--fallback-model", ws['fallback_model']])

    if ws.get('skip_permissions'):
        cmd.append("--dangerously-skip-permissions")
    if ws.get('permission_mode'):
        cmd.extend(["--permission-mode", ws['permission_mode']])

    for tool in ws.get('allowed_tools', []):
        cmd.extend(["--allowedTools", tool])
    for tool in ws.get('disallowed_tools', []):
        cmd.extend(["--disallowedTools", tool])

    if ws.get('append_system_prompt'):
        cmd.extend(["--append-system-prompt", ws['append_system_prompt']])
    if ws.get('system_prompt_file'):
        cmd.extend(["--system-prompt-file", ws['system_prompt_file']])

    if ws.get('mcp_config'):
        cmd.extend(["--mcp-config", ws['mcp_config']])
    if ws.get('strict_mcp'):
        cmd.append("--strict-mcp-config")

    if ws.get('agent'):
        cmd.extend(["--agent", ws['agent']])

    if ws.get('verbose'):
        cmd.append("--verbose")
    if ws.get('debug_categories'):
        cmd.extend(["--debug", ws['debug_categories']])

    for d in ws.get('additional_dirs', []):
        if d.strip():
            cmd.extend(["--add-dir", d.strip()])

    return cmd

def shell_quote(s: str) -> str:
    """Safely quote a string for shell usage."""
    if not s:
        return "''"
    return "'" + s.replace("'", "'\"'\"'") + "'"

def win_quote(s: str) -> str:
    """Safely quote a string for Windows cmd usage."""
    if not s:
        return '""'
    if ' ' in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s

def build_launch_script(ws: dict) -> str:
    """Generate launch script content (bash)."""
    lines = ["#!/bin/bash", ""]

    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()
    lines.append(f"cd {shell_quote(working_dir)}")
    lines.append("")

    env_vars = ws.get('env_vars', {})
    if env_vars:
        lines.append("# Environment variables")
        for key, value in env_vars.items():
            lines.append(f"export {key}={shell_quote(value)}")
        lines.append("")

    if ws.get('init_claude_md') and ws.get('claude_md_content'):
        claude_md_path = os.path.join(working_dir, "CLAUDE.md")
        lines.append("# Create CLAUDE.md if it doesn't exist")
        lines.append(f"if [ ! -f {shell_quote(claude_md_path)} ]; then")
        lines.append(f"    cat > {shell_quote(claude_md_path)} << 'CLAUDE_MD_EOF'")
        lines.append(ws['claude_md_content'])
        lines.append("CLAUDE_MD_EOF")
        lines.append("fi")
        lines.append("")

    cmd = build_command(ws)
    cmd_str = " ".join(shell_quote(c) if i > 0 else c for i, c in enumerate(cmd))
    lines.append("# Launch Claude Code")
    lines.append(cmd_str)
    lines.append("")

    return "\n".join(lines)

def build_launch_script_windows(ws: dict) -> str:
    """Generate launch script content (Windows batch)."""
    lines = ["@echo off", ""]

    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()
    lines.append(f'cd /d "{working_dir}"')
    lines.append("")

    env_vars = ws.get('env_vars', {})
    if env_vars:
        lines.append("REM Environment variables")
        for key, value in env_vars.items():
            lines.append(f'set "{key}={value}"')
        lines.append("")

    if ws.get('init_claude_md') and ws.get('claude_md_content'):
        claude_md_path = os.path.join(working_dir, "CLAUDE.md")
        lines.append("REM Create CLAUDE.md if it doesn't exist")
        lines.append(f'if not exist "{claude_md_path}" (')
        for line in ws['claude_md_content'].split('\n'):
            lines.append(f'    echo {line}>>{claude_md_path}')
        lines.append(")")
        lines.append("")

    cmd = build_command(ws)
    cmd_str = " ".join(win_quote(c) for c in cmd)
    lines.append("REM Launch Claude Code")
    lines.append(cmd_str)
    lines.append("")

    return "\n".join(lines)

# ============================================================================
# IDE & Terminal Integration
# ============================================================================

def detect_available_ides() -> dict:
    """Detect which IDEs are available on the system."""
    ides = {"terminal": True}
    for ide, cmd in [("vscode", "code"), ("vscode-insiders", "code-insiders"), ("cursor", "cursor")]:
        ides[ide] = shutil.which(cmd) is not None
    return ides

def get_ide_command(ide: str) -> str:
    """Get the command for launching an IDE."""
    commands = {
        "vscode": "code",
        "vscode-insiders": "code-insiders",
        "cursor": "cursor"
    }
    return commands.get(ide, "")

def detect_terminal() -> tuple:
    """Detect available terminal emulator."""
    system = platform.system()

    if system == "Darwin":
        return ("osascript", "applescript")
    elif system == "Windows":
        return ("cmd", "windows")

    terminals = [
        ("gnome-terminal", ["gnome-terminal", "--", "bash"]),
        ("konsole", ["konsole", "-e", "bash"]),
        ("xfce4-terminal", ["xfce4-terminal", "-e", "bash"]),
        ("xterm", ["xterm", "-e", "bash"]),
    ]

    for name, cmd in terminals:
        if shutil.which(name):
            return (name, cmd)

    return (None, None)

def launch_in_terminal(script_path: str, working_dir: str):
    """Launch the script in a terminal window."""
    system = platform.system()

    if system == "Windows":
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", script_path],
            cwd=working_dir,
            shell=True
        )
    elif system == "Darwin":
        applescript = f'''
        tell application "Terminal"
            do script "cd {working_dir} && bash {script_path}"
            activate
        end tell
        '''
        subprocess.Popen(["osascript", "-e", applescript])
    else:
        terminal_name, terminal_cmd = detect_terminal()
        if terminal_name:
            if terminal_name == "gnome-terminal":
                subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"cd '{working_dir}' && bash '{script_path}'; exec bash"])
            elif terminal_name == "konsole":
                subprocess.Popen(["konsole", "-e", "bash", "-c", f"cd '{working_dir}' && bash '{script_path}'; exec bash"])
            elif terminal_name == "xfce4-terminal":
                subprocess.Popen(["xfce4-terminal", "-e", f"bash -c \"cd '{working_dir}' && bash '{script_path}'; exec bash\""])
            else:
                subprocess.Popen(["xterm", "-e", f"cd '{working_dir}' && bash '{script_path}'; exec bash"])

def open_ide(ide: str, folder: str):
    """Open a folder in the specified IDE."""
    cmd = get_ide_command(ide)
    if cmd and shutil.which(cmd):
        subprocess.Popen([cmd, folder])

def launch_workspace(name: str) -> bool:
    """Launch a workspace by name."""
    workspaces = load_workspaces()
    if name not in workspaces:
        return False

    ws = workspaces[name]

    # Update metadata
    ws['last_used'] = datetime.now().isoformat()
    ws['use_count'] = ws.get('use_count', 0) + 1
    workspaces[name] = ws
    save_workspaces(workspaces)

    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()

    # Add to history
    add_history_entry(name, working_dir)

    # Generate and save launch script
    ensure_config_dir()
    system = platform.system()

    if system == "Windows":
        script_content = build_launch_script_windows(ws)
        script_path = LAUNCH_SCRIPT_WIN
    else:
        script_content = build_launch_script(ws)
        script_path = LAUNCH_SCRIPT

    with open(script_path, 'w') as f:
        f.write(script_content)

    if system != "Windows":
        os.chmod(script_path, 0o755)

    # Open IDE if configured
    ide = ws.get('ide', 'terminal')
    if ide != 'terminal' and ws.get('open_folder_in_ide'):
        open_ide(ide, working_dir)

    # Launch in terminal
    launch_in_terminal(str(script_path), working_dir)

    return True

# ============================================================================
# Import/Export Functions
# ============================================================================

def export_workspace(name: str) -> dict | None:
    """Export a single workspace as dict."""
    workspaces = load_workspaces()
    if name not in workspaces:
        return None

    return {
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "workspaces": [workspaces[name]]
    }

def export_all_workspaces() -> dict:
    """Export all workspaces and groups."""
    workspaces = load_workspaces()
    groups = load_groups()

    return {
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "workspaces": list(workspaces.values()),
        "groups": groups
    }

def import_workspaces(import_data: dict, conflict_resolution: str = 'skip') -> dict:
    """
    Import workspaces from dict.

    Args:
        import_data: Dict with 'workspaces' list and optional 'groups' dict
        conflict_resolution: 'skip', 'rename', or 'overwrite'

    Returns:
        Dict with 'imported', 'skipped', 'renamed' lists
    """
    import_ws = import_data.get('workspaces', [])
    import_groups = import_data.get('groups', {})

    if not import_ws:
        raise ValueError("No workspaces to import")

    workspaces = load_workspaces()
    groups = load_groups()

    imported = []
    skipped = []
    renamed = {}

    for ws in import_ws:
        name = ws.get('name', '')
        if not name:
            continue

        if name in workspaces:
            if conflict_resolution == 'skip':
                skipped.append(name)
                continue
            elif conflict_resolution == 'rename':
                new_name = name
                counter = 1
                while new_name in workspaces:
                    new_name = f"{name}-{counter}"
                    counter += 1
                renamed[name] = new_name
                ws['name'] = new_name
                name = new_name

        workspace = {**DEFAULT_WORKSPACE, **ws}
        workspace['created'] = workspace.get('created') or datetime.now().isoformat()
        workspaces[name] = workspace
        imported.append(name)

    for group_name, group_data in import_groups.items():
        if group_name not in groups:
            groups[group_name] = group_data

    save_workspaces(workspaces)
    save_groups(groups)

    return {
        "imported": imported,
        "skipped": skipped,
        "renamed": renamed
    }
