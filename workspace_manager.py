#!/usr/bin/env python3
"""
Claude Code Workspace Manager
A visual configuration and launch tool for Claude Code CLI.

Usage:
    python workspace_manager.py [--port PORT]

Opens a web interface at http://127.0.0.1:5199 for managing Claude Code workspaces.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Auto-install Flask if not present
try:
    from flask import Flask, jsonify, request, Response
except ImportError:
    print("Flask not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    from flask import Flask, jsonify, request, Response

# Configuration
DEFAULT_PORT = 5199
CONFIG_DIR = Path.home() / ".claude-workspaces"
WORKSPACES_FILE = CONFIG_DIR / "workspaces.json"
LAUNCH_SCRIPT = CONFIG_DIR / "launch.sh"

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
    # New v2 fields
    "group": "",
    "template_source": ""
}

# Current data schema version
DATA_VERSION = 2

app = Flask(__name__)

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
    # Old format was just a flat dict of workspaces
    new_data["workspaces"] = old_data
    # Add default group and template_source fields to existing workspaces
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

            # Check if this is v1 format (no version field = flat workspace dict)
            if "version" not in data:
                data = migrate_v1_to_v2(data)
                save_data(data)

            # Ensure all required keys exist
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
    """Load workspaces from JSON file (backward compatible)."""
    data = load_data()
    return data.get("workspaces", {})

def save_workspaces(workspaces: dict):
    """Save workspaces to JSON file (backward compatible)."""
    data = load_data()
    data["workspaces"] = workspaces
    save_data(data)

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
    # If all colors used, return the first one
    return GROUP_COLORS[0]

# ============================================================================
# Templates Functions
# ============================================================================

def load_templates() -> dict:
    """Load all templates (builtin + user-defined)."""
    data = load_data()
    user_templates = data.get("templates", {})
    # Merge builtin and user templates (user templates can override builtin)
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
    """Delete a user-defined template. Returns False if builtin."""
    if template_id in BUILTIN_TEMPLATES:
        return False
    data = load_data()
    if template_id in data.get("templates", {}):
        del data["templates"][template_id]
        save_data(data)
        return True
    return False

# ============================================================================
# History Functions
# ============================================================================

def load_history() -> list:
    """Load launch history."""
    data = load_data()
    return data.get("history", [])

def add_history_entry(workspace_name: str, working_dir: str):
    """Add a launch to history."""
    import uuid
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

    # Add to beginning of list
    history.insert(0, entry)

    # Prune to limit
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

    # Model
    if ws.get('model'):
        cmd.extend(["--model", ws['model']])
    if ws.get('fallback_model'):
        cmd.extend(["--fallback-model", ws['fallback_model']])

    # Permissions
    if ws.get('skip_permissions'):
        cmd.append("--dangerously-skip-permissions")
    if ws.get('permission_mode'):
        cmd.extend(["--permission-mode", ws['permission_mode']])

    # Tools
    for tool in ws.get('allowed_tools', []):
        cmd.extend(["--allowedTools", tool])
    for tool in ws.get('disallowed_tools', []):
        cmd.extend(["--disallowedTools", tool])

    # System Prompt
    if ws.get('append_system_prompt'):
        cmd.extend(["--append-system-prompt", ws['append_system_prompt']])
    if ws.get('system_prompt_file'):
        cmd.extend(["--system-prompt-file", ws['system_prompt_file']])

    # MCP
    if ws.get('mcp_config'):
        cmd.extend(["--mcp-config", ws['mcp_config']])
    if ws.get('strict_mcp'):
        cmd.append("--strict-mcp-config")

    # Agent
    if ws.get('agent'):
        cmd.extend(["--agent", ws['agent']])

    # Debug
    if ws.get('verbose'):
        cmd.append("--verbose")
    if ws.get('debug_categories'):
        cmd.extend(["--debug", ws['debug_categories']])

    # Additional Directories
    for d in ws.get('additional_dirs', []):
        if d.strip():
            cmd.extend(["--add-dir", d.strip()])

    return cmd

def shell_quote(s: str) -> str:
    """Safely quote a string for shell usage."""
    if not s:
        return "''"
    # Use single quotes and escape any single quotes in the string
    return "'" + s.replace("'", "'\"'\"'") + "'"

def build_launch_script(ws: dict) -> str:
    """Generate launch script content."""
    lines = ["#!/bin/bash", ""]

    # Change to working directory
    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()
    lines.append(f"cd {shell_quote(working_dir)}")
    lines.append("")

    # Export environment variables
    env_vars = ws.get('env_vars', {})
    if env_vars:
        lines.append("# Environment variables")
        for key, value in env_vars.items():
            lines.append(f"export {key}={shell_quote(value)}")
        lines.append("")

    # Create CLAUDE.md if requested
    if ws.get('init_claude_md') and ws.get('claude_md_content'):
        claude_md_path = os.path.join(working_dir, "CLAUDE.md")
        lines.append("# Create CLAUDE.md if it doesn't exist")
        lines.append(f"if [ ! -f {shell_quote(claude_md_path)} ]; then")
        lines.append(f"    cat > {shell_quote(claude_md_path)} << 'CLAUDE_MD_EOF'")
        lines.append(ws['claude_md_content'])
        lines.append("CLAUDE_MD_EOF")
        lines.append("fi")
        lines.append("")

    # Build and add Claude command
    cmd = build_command(ws)
    cmd_str = " ".join(shell_quote(c) if i > 0 else c for i, c in enumerate(cmd))
    lines.append("# Launch Claude Code")
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
    """Detect available terminal emulator. Returns (command, args_format)."""
    system = platform.system()

    if system == "Darwin":
        return ("osascript", "applescript")

    # Linux - try terminals in order of preference
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

    if system == "Darwin":
        # macOS - use AppleScript
        applescript = f'''
        tell application "Terminal"
            do script "cd {working_dir} && bash {script_path}"
            activate
        end tell
        '''
        subprocess.Popen(["osascript", "-e", applescript])
    else:
        # Linux
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

# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/workspaces', methods=['GET'])
def list_workspaces():
    """List all workspaces."""
    return jsonify(load_workspaces())

@app.route('/api/workspaces/<name>', methods=['GET'])
def get_workspace(name):
    """Get a single workspace by name."""
    workspaces = load_workspaces()
    if name in workspaces:
        return jsonify(workspaces[name])
    return jsonify({"error": "Workspace not found"}), 404

@app.route('/api/workspaces', methods=['POST'])
def save_workspace():
    """Create or update a workspace."""
    data = request.json
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"error": "Workspace name is required"}), 400

    workspaces = load_workspaces()

    # Merge with defaults
    workspace = {**DEFAULT_WORKSPACE, **data}

    # Set timestamps
    if name not in workspaces:
        workspace['created'] = datetime.now().isoformat()
    else:
        workspace['created'] = workspaces[name].get('created', datetime.now().isoformat())

    workspaces[name] = workspace
    save_workspaces(workspaces)

    return jsonify({"status": "ok"})

@app.route('/api/workspaces/<name>', methods=['DELETE'])
def delete_workspace(name):
    """Delete a workspace."""
    workspaces = load_workspaces()
    if name in workspaces:
        del workspaces[name]
        save_workspaces(workspaces)
    return jsonify({"status": "ok"})

@app.route('/api/workspaces/<name>/command', methods=['GET'])
def get_command(name):
    """Get the CLI command for a workspace."""
    workspaces = load_workspaces()
    if name not in workspaces:
        return jsonify({"error": "Workspace not found"}), 404

    ws = workspaces[name]
    cmd = build_command(ws)
    script = build_launch_script(ws)

    return jsonify({
        "command": " ".join(cmd),
        "script": script
    })

@app.route('/api/workspaces/<name>/launch', methods=['POST'])
def launch_workspace(name):
    """Launch a workspace."""
    workspaces = load_workspaces()
    if name not in workspaces:
        return jsonify({"error": "Workspace not found"}), 404

    ws = workspaces[name]

    # Update metadata
    ws['last_used'] = datetime.now().isoformat()
    ws['use_count'] = ws.get('use_count', 0) + 1
    workspaces[name] = ws
    save_workspaces(workspaces)

    # Get working directory
    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()

    # Add to history
    add_history_entry(name, working_dir)

    # Generate launch script
    script_content = build_launch_script(ws)
    ensure_config_dir()
    with open(LAUNCH_SCRIPT, 'w') as f:
        f.write(script_content)
    os.chmod(LAUNCH_SCRIPT, 0o755)

    # Open IDE if configured
    ide = ws.get('ide', 'terminal')
    if ide != 'terminal' and ws.get('open_folder_in_ide'):
        open_ide(ide, working_dir)

    # Launch in terminal
    launch_in_terminal(str(LAUNCH_SCRIPT), working_dir)

    return jsonify({"status": "ok"})

@app.route('/api/ides', methods=['GET'])
def list_ides():
    """List available IDEs."""
    return jsonify(detect_available_ides())

@app.route('/api/tools', methods=['GET'])
def list_tools():
    """List built-in Claude Code tools."""
    return jsonify(BUILTIN_TOOLS)

# ============================================================================
# API Routes - Groups
# ============================================================================

@app.route('/api/groups', methods=['GET'])
def api_list_groups():
    """List all groups."""
    return jsonify(load_groups())

@app.route('/api/groups', methods=['POST'])
def api_create_group():
    """Create a new group."""
    data = request.json
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"error": "Group name is required"}), 400

    groups = load_groups()
    if name in groups:
        return jsonify({"error": "Group already exists"}), 400

    groups[name] = {
        "order": len(groups),
        "color": data.get('color', get_next_group_color())
    }
    save_groups(groups)

    return jsonify({"status": "ok", "group": groups[name]})

@app.route('/api/groups/<name>', methods=['PUT'])
def api_update_group(name):
    """Update a group (rename, color, order)."""
    data = request.json
    groups = load_groups()

    if name not in groups:
        return jsonify({"error": "Group not found"}), 404

    new_name = data.get('new_name', '').strip()
    if new_name and new_name != name:
        if new_name in groups:
            return jsonify({"error": "Group with new name already exists"}), 400
        # Rename group
        groups[new_name] = groups.pop(name)
        # Update workspaces that reference this group
        workspaces = load_workspaces()
        for ws in workspaces.values():
            if ws.get('group') == name:
                ws['group'] = new_name
        save_workspaces(workspaces)
        name = new_name

    if 'color' in data:
        groups[name]['color'] = data['color']
    if 'order' in data:
        groups[name]['order'] = data['order']

    save_groups(groups)
    return jsonify({"status": "ok"})

@app.route('/api/groups/<name>', methods=['DELETE'])
def api_delete_group(name):
    """Delete a group (moves workspaces to ungrouped)."""
    groups = load_groups()

    if name not in groups:
        return jsonify({"error": "Group not found"}), 404

    # Remove group from workspaces
    workspaces = load_workspaces()
    for ws in workspaces.values():
        if ws.get('group') == name:
            ws['group'] = ""
    save_workspaces(workspaces)

    # Delete the group
    del groups[name]
    save_groups(groups)

    return jsonify({"status": "ok"})

@app.route('/api/workspaces/<name>/group', methods=['PUT'])
def api_set_workspace_group(name):
    """Assign a workspace to a group."""
    data = request.json
    group_name = data.get('group', '')

    workspaces = load_workspaces()
    if name not in workspaces:
        return jsonify({"error": "Workspace not found"}), 404

    workspaces[name]['group'] = group_name
    save_workspaces(workspaces)

    return jsonify({"status": "ok"})

# ============================================================================
# API Routes - Templates
# ============================================================================

@app.route('/api/templates', methods=['GET'])
def api_list_templates():
    """List all templates (builtin + user-defined)."""
    return jsonify(load_templates())

@app.route('/api/templates/<template_id>', methods=['GET'])
def api_get_template(template_id):
    """Get a single template."""
    templates = load_templates()
    if template_id in templates:
        return jsonify(templates[template_id])
    return jsonify({"error": "Template not found"}), 404

@app.route('/api/templates', methods=['POST'])
def api_create_template():
    """Create a user template."""
    data = request.json
    template_id = data.get('id', '').strip().lower().replace(' ', '-')
    name = data.get('name', '').strip()

    if not template_id or not name:
        return jsonify({"error": "Template ID and name are required"}), 400

    if template_id in BUILTIN_TEMPLATES:
        return jsonify({"error": "Cannot override builtin template"}), 400

    template = {
        "name": name,
        "description": data.get('description', ''),
        "icon": data.get('icon', 'folder'),
        "config": data.get('config', {})
    }

    save_user_template(template_id, template)
    return jsonify({"status": "ok", "template_id": template_id})

@app.route('/api/templates/<template_id>', methods=['DELETE'])
def api_delete_template(template_id):
    """Delete a user template."""
    if template_id in BUILTIN_TEMPLATES:
        return jsonify({"error": "Cannot delete builtin template"}), 400

    if delete_user_template(template_id):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Template not found"}), 404

@app.route('/api/workspaces/from-template', methods=['POST'])
def api_create_from_template():
    """Create a workspace from a template."""
    data = request.json
    template_id = data.get('template_id', '')
    name = data.get('name', '').strip()
    working_dir = data.get('working_dir', '')
    overrides = data.get('overrides', {})

    if not template_id or not name:
        return jsonify({"error": "Template ID and workspace name are required"}), 400

    templates = load_templates()
    if template_id not in templates:
        return jsonify({"error": "Template not found"}), 404

    workspaces = load_workspaces()
    if name in workspaces:
        return jsonify({"error": "Workspace already exists"}), 400

    template = templates[template_id]
    config = template.get('config', {})

    # Create workspace from template
    workspace = {**DEFAULT_WORKSPACE, **config, **overrides}
    workspace['name'] = name
    workspace['working_dir'] = working_dir
    workspace['template_source'] = template_id
    workspace['created'] = datetime.now().isoformat()

    workspaces[name] = workspace
    save_workspaces(workspaces)

    return jsonify({"status": "ok", "workspace": workspace})

# ============================================================================
# API Routes - History
# ============================================================================

@app.route('/api/history', methods=['GET'])
def api_get_history():
    """Get launch history."""
    limit = request.args.get('limit', 20, type=int)
    history = load_history()[:limit]

    # Add 'exists' field to indicate if workspace still exists
    workspaces = load_workspaces()
    for entry in history:
        entry['exists'] = entry['workspace_name'] in workspaces

    return jsonify({"history": history})

@app.route('/api/history', methods=['DELETE'])
def api_clear_history():
    """Clear all history."""
    clear_history()
    return jsonify({"status": "ok"})

@app.route('/api/history/<entry_id>/relaunch', methods=['POST'])
def api_relaunch_from_history(entry_id):
    """Re-launch a workspace from history."""
    history = load_history()
    entry = next((h for h in history if h['id'] == entry_id), None)

    if not entry:
        return jsonify({"error": "History entry not found"}), 404

    workspace_name = entry['workspace_name']
    workspaces = load_workspaces()

    if workspace_name not in workspaces:
        return jsonify({"error": "Workspace no longer exists"}), 404

    # Delegate to regular launch
    return launch_workspace(workspace_name)

# ============================================================================
# API Routes - Import/Export
# ============================================================================

@app.route('/api/export/workspace/<name>', methods=['GET'])
def api_export_workspace(name):
    """Export a single workspace as JSON."""
    workspaces = load_workspaces()
    if name not in workspaces:
        return jsonify({"error": "Workspace not found"}), 404

    workspace = workspaces[name]
    return jsonify({
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "workspaces": [workspace]
    })

@app.route('/api/export/all', methods=['GET'])
def api_export_all():
    """Export all workspaces as JSON."""
    workspaces = load_workspaces()
    groups = load_groups()

    return jsonify({
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "workspaces": list(workspaces.values()),
        "groups": groups
    })

@app.route('/api/import/workspace', methods=['POST'])
def api_import_workspaces():
    """Import workspace(s) from JSON."""
    data = request.json
    import_workspaces = data.get('workspaces', [])
    conflict_resolution = data.get('conflict_resolution', 'skip')  # skip, rename, overwrite
    import_groups = data.get('groups', {})

    if not import_workspaces:
        return jsonify({"error": "No workspaces to import"}), 400

    workspaces = load_workspaces()
    groups = load_groups()

    imported = []
    skipped = []
    renamed = {}

    for ws in import_workspaces:
        name = ws.get('name', '')
        if not name:
            continue

        if name in workspaces:
            if conflict_resolution == 'skip':
                skipped.append(name)
                continue
            elif conflict_resolution == 'rename':
                # Find unique name
                new_name = name
                counter = 1
                while new_name in workspaces:
                    new_name = f"{name}-{counter}"
                    counter += 1
                renamed[name] = new_name
                ws['name'] = new_name
                name = new_name
            # overwrite: just proceed

        # Merge with defaults and save
        workspace = {**DEFAULT_WORKSPACE, **ws}
        workspace['created'] = workspace.get('created') or datetime.now().isoformat()
        workspaces[name] = workspace
        imported.append(name)

    # Import groups
    for group_name, group_data in import_groups.items():
        if group_name not in groups:
            groups[group_name] = group_data

    save_workspaces(workspaces)
    save_groups(groups)

    return jsonify({
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "renamed": renamed
    })

@app.route('/api/export/template/<template_id>', methods=['GET'])
def api_export_template(template_id):
    """Export a template as JSON."""
    templates = load_templates()
    if template_id not in templates:
        return jsonify({"error": "Template not found"}), 404

    template = templates[template_id]
    return jsonify({
        "export_version": 1,
        "export_date": datetime.now().isoformat(),
        "template_id": template_id,
        "template": template
    })

@app.route('/api/import/template', methods=['POST'])
def api_import_template():
    """Import a template from JSON."""
    data = request.json
    template_id = data.get('template_id', '')
    template = data.get('template', {})

    if not template_id or not template:
        return jsonify({"error": "Template ID and template data required"}), 400

    if template_id in BUILTIN_TEMPLATES:
        return jsonify({"error": "Cannot override builtin template"}), 400

    save_user_template(template_id, template)
    return jsonify({"status": "ok"})

@app.route('/api/colors', methods=['GET'])
def api_get_colors():
    """Get available group colors."""
    return jsonify(GROUP_COLORS)

# ============================================================================
# Frontend HTML/CSS/JS
# ============================================================================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code Workspace Manager</title>
    <style>
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --surface-2: #21262d;
            --border: #30363d;
            --text: #c9d1d9;
            --text-dim: #8b949e;
            --accent: #d2a8ff;
            --accent-dim: #a371f7;
            --green: #3fb950;
            --red: #f85149;
            --blue: #58a6ff;
            --orange: #d29922;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .app {
            display: grid;
            grid-template-columns: 280px 1fr;
            min-height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            background: var(--surface);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            height: 100vh;
            position: sticky;
            top: 0;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--accent);
            font-size: 18px;
            font-weight: 600;
        }

        .logo svg {
            width: 32px;
            height: 32px;
        }

        .btn-new {
            margin: 16px 20px;
            padding: 12px 16px;
            background: var(--accent-dim);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: background 0.2s;
        }

        .btn-new:hover {
            background: var(--accent);
        }

        .workspace-list-header {
            padding: 12px 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
        }

        .workspace-list {
            flex: 1;
            overflow-y: auto;
            list-style: none;
        }

        .workspace-item {
            padding: 12px 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.15s;
            border-left: 3px solid transparent;
        }

        .workspace-item:hover {
            background: var(--surface-2);
        }

        .workspace-item.active {
            background: var(--surface-2);
            border-left-color: var(--accent);
        }

        .workspace-item-name {
            font-size: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .workspace-item-badge {
            font-size: 10px;
            padding: 2px 6px;
            background: var(--surface);
            border-radius: 4px;
            color: var(--text-dim);
        }

        /* Main Content */
        .main {
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }

        .main-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
        }

        .main-header h1 {
            font-size: 20px;
            font-weight: 600;
        }

        .header-actions {
            display: flex;
            gap: 8px;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }

        .btn-primary {
            background: var(--accent-dim);
            color: white;
        }

        .btn-primary:hover {
            background: var(--accent);
        }

        .btn-secondary {
            background: var(--surface-2);
            color: var(--text);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--border);
        }

        .btn-danger {
            background: transparent;
            color: var(--red);
            border: 1px solid var(--red);
        }

        .btn-danger:hover {
            background: var(--red);
            color: white;
        }

        .btn-success {
            background: var(--green);
            color: white;
        }

        .btn-success:hover {
            filter: brightness(1.1);
        }

        /* Form */
        .form-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            padding-bottom: 100px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            max-width: 1200px;
        }

        .form-section {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }

        .form-section h3 {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-group:last-child {
            margin-bottom: 0;
        }

        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-dim);
            margin-bottom: 6px;
        }

        .form-group input[type="text"],
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 10px 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-size: 13px;
            font-family: inherit;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            outline: none;
            border-color: var(--accent-dim);
        }

        .form-group textarea {
            resize: vertical;
            min-height: 80px;
        }

        .form-group input[type="checkbox"] {
            width: 16px;
            height: 16px;
            margin-right: 8px;
            vertical-align: middle;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            font-size: 13px;
            color: var(--text);
            cursor: pointer;
        }

        .tool-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }

        .tool-item {
            display: flex;
            align-items: center;
            padding: 8px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .tool-item:hover {
            border-color: var(--accent-dim);
        }

        .tool-item.selected {
            border-color: var(--accent);
            background: rgba(210, 168, 255, 0.1);
        }

        .tool-item input {
            margin-right: 6px;
        }

        /* Quick Launch Bar */
        .quick-launch {
            position: fixed;
            bottom: 0;
            left: 280px;
            right: 0;
            background: var(--surface);
            border-top: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }

        .quick-launch-info {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .quick-launch-info strong {
            color: var(--text);
            font-size: 14px;
        }

        .quick-launch-info span {
            color: var(--text-dim);
            font-size: 13px;
        }

        .quick-launch-actions {
            display: flex;
            gap: 8px;
        }

        /* Empty State */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-dim);
            text-align: center;
            padding: 40px;
        }

        .empty-state svg {
            width: 64px;
            height: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        .empty-state h2 {
            font-size: 18px;
            margin-bottom: 8px;
            color: var(--text);
        }

        .empty-state p {
            font-size: 14px;
            max-width: 300px;
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 100px;
            right: 24px;
            padding: 12px 20px;
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 13px;
            z-index: 200;
            animation: slideIn 0.3s ease;
        }

        .toast.success {
            border-color: var(--green);
        }

        .toast.error {
            border-color: var(--red);
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        /* Responsive */
        @media (max-width: 900px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 700px) {
            .app {
                grid-template-columns: 1fr;
            }

            .sidebar {
                display: none;
            }

            .quick-launch {
                left: 0;
            }
        }

        .hint {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 4px;
        }

        /* New Workspace Buttons */
        .sidebar-buttons {
            display: flex;
            gap: 8px;
            margin: 16px 20px;
        }

        .sidebar-buttons .btn-new {
            margin: 0;
            flex: 1;
        }

        .btn-template {
            padding: 12px;
            background: var(--surface-2);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-template:hover {
            background: var(--border);
        }

        /* Sidebar Sections */
        .sidebar-section {
            border-bottom: 1px solid var(--border);
        }

        .sidebar-section-header {
            padding: 12px 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }

        .sidebar-section-header:hover {
            background: var(--surface-2);
        }

        .sidebar-section-header .chevron {
            transition: transform 0.2s;
        }

        .sidebar-section-header.collapsed .chevron {
            transform: rotate(-90deg);
        }

        .sidebar-section-content {
            max-height: 500px;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }

        .sidebar-section-content.collapsed {
            max-height: 0;
        }

        /* Recent History Items */
        .history-item {
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: background 0.15s;
        }

        .history-item:hover {
            background: var(--surface-2);
        }

        .history-item-info {
            flex: 1;
            min-width: 0;
        }

        .history-item-name {
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .history-item-time {
            font-size: 11px;
            color: var(--text-dim);
        }

        .history-item-actions {
            display: flex;
            gap: 4px;
        }

        .btn-icon {
            padding: 6px;
            background: transparent;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .btn-icon:hover {
            background: var(--surface-2);
            color: var(--text);
        }

        .btn-icon.play:hover {
            color: var(--green);
        }

        /* Group Styling */
        .group-header {
            padding: 8px 20px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-dim);
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            user-select: none;
        }

        .group-header:hover {
            background: var(--surface-2);
        }

        .group-color-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .group-count {
            font-size: 10px;
            padding: 1px 5px;
            background: var(--surface);
            border-radius: 10px;
            margin-left: auto;
        }

        .group-workspaces {
            max-height: 500px;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }

        .group-workspaces.collapsed {
            max-height: 0;
        }

        /* Sidebar Footer */
        .sidebar-footer {
            padding: 16px 20px;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 8px;
        }

        .sidebar-footer .btn {
            flex: 1;
            font-size: 12px;
            padding: 8px 12px;
        }

        /* Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.2s;
        }

        .modal-overlay.active {
            opacity: 1;
            visibility: visible;
        }

        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transform: scale(0.9);
            transition: transform 0.2s;
        }

        .modal-overlay.active .modal {
            transform: scale(1);
        }

        .modal-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-header h2 {
            font-size: 18px;
            font-weight: 600;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            padding: 4px;
        }

        .modal-close:hover {
            color: var(--text);
        }

        .modal-body {
            padding: 20px;
            overflow-y: auto;
            flex: 1;
        }

        .modal-footer {
            padding: 16px 20px;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }

        /* Template Grid */
        .template-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }

        .template-card {
            padding: 16px;
            background: var(--bg);
            border: 2px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .template-card:hover {
            border-color: var(--accent-dim);
        }

        .template-card.selected {
            border-color: var(--accent);
            background: rgba(210, 168, 255, 0.05);
        }

        .template-card-icon {
            width: 32px;
            height: 32px;
            margin-bottom: 12px;
            color: var(--accent);
        }

        .template-card-name {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 4px;
        }

        .template-card-desc {
            font-size: 12px;
            color: var(--text-dim);
        }

        .template-card-badge {
            display: inline-block;
            font-size: 10px;
            padding: 2px 6px;
            background: var(--surface-2);
            border-radius: 4px;
            color: var(--text-dim);
            margin-top: 8px;
        }

        /* Import/Export */
        .import-dropzone {
            border: 2px dashed var(--border);
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            color: var(--text-dim);
            cursor: pointer;
            transition: all 0.2s;
        }

        .import-dropzone:hover {
            border-color: var(--accent-dim);
            background: rgba(210, 168, 255, 0.05);
        }

        .import-dropzone.dragover {
            border-color: var(--accent);
            background: rgba(210, 168, 255, 0.1);
        }

        .import-preview {
            margin-top: 16px;
        }

        .import-preview-item {
            padding: 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .conflict-badge {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            background: var(--orange);
            color: white;
        }

        /* Color Picker */
        .color-picker {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .color-option {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.15s;
        }

        .color-option:hover {
            transform: scale(1.1);
        }

        .color-option.selected {
            border-color: white;
            box-shadow: 0 0 0 2px var(--accent);
        }

        /* Template Badge in Form */
        .template-source-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 11px;
            padding: 4px 8px;
            background: var(--surface-2);
            border-radius: 4px;
            color: var(--text-dim);
            margin-left: 12px;
        }
    </style>
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 17l6-6-6-6"/>
                        <path d="M12 19h8"/>
                    </svg>
                    <span>Claude Workspaces</span>
                </div>
            </div>

            <div class="sidebar-buttons">
                <button class="btn-new" onclick="createNewWorkspace()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    New
                </button>
                <button class="btn-template" onclick="showTemplateModal()" title="New from Template">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M3 9h18M9 21V9"/>
                    </svg>
                </button>
            </div>

            <!-- Recent Section -->
            <div class="sidebar-section" id="recent-section">
                <div class="sidebar-section-header" onclick="toggleSection('recent')">
                    <span>Recent</span>
                    <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </div>
                <div class="sidebar-section-content" id="recent-content">
                    <!-- Populated by JS -->
                </div>
            </div>

            <!-- Workspaces Section (Grouped) -->
            <div class="workspace-list" id="workspace-list">
                <!-- Populated by JS -->
            </div>

            <!-- Sidebar Footer -->
            <div class="sidebar-footer">
                <button class="btn btn-secondary" onclick="showImportModal()">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    Import
                </button>
                <button class="btn btn-secondary" onclick="exportAll()">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Export
                </button>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main" id="main-content">
            <!-- Populated by JS -->
        </main>
    </div>

    <!-- Quick Launch Bar -->
    <div class="quick-launch" id="quick-launch" style="display: none;">
        <div class="quick-launch-info">
            <strong id="launch-name">-</strong>
            <span id="launch-tags">-</span>
        </div>
        <div class="quick-launch-actions">
            <button class="btn btn-secondary" onclick="copyCommand()">Copy Command</button>
            <button class="btn btn-success" onclick="launchWorkspace()">Launch</button>
        </div>
    </div>

    <!-- Template Modal -->
    <div class="modal-overlay" id="template-modal">
        <div class="modal">
            <div class="modal-header">
                <h2>New from Template</h2>
                <button class="modal-close" onclick="closeModal('template-modal')">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Select Template</label>
                    <div class="template-grid" id="template-grid">
                        <!-- Populated by JS -->
                    </div>
                </div>
                <div class="form-group" style="margin-top: 20px;">
                    <label for="template-ws-name">Workspace Name *</label>
                    <input type="text" id="template-ws-name" placeholder="my-new-project">
                </div>
                <div class="form-group">
                    <label for="template-ws-dir">Working Directory</label>
                    <input type="text" id="template-ws-dir" placeholder="~/projects/my-new-project">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal('template-modal')">Cancel</button>
                <button class="btn btn-primary" onclick="createFromTemplate()">Create Workspace</button>
            </div>
        </div>
    </div>

    <!-- Import Modal -->
    <div class="modal-overlay" id="import-modal">
        <div class="modal">
            <div class="modal-header">
                <h2>Import Workspaces</h2>
                <button class="modal-close" onclick="closeModal('import-modal')">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="import-dropzone" id="import-dropzone" onclick="document.getElementById('import-file').click()">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 12px; opacity: 0.5;">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <p>Drop JSON file here or click to browse</p>
                    <input type="file" id="import-file" accept=".json" style="display: none;" onchange="handleImportFile(event)">
                </div>
                <div class="import-preview" id="import-preview" style="display: none;">
                    <h4 style="margin-bottom: 12px;">Workspaces to Import:</h4>
                    <div id="import-preview-list"></div>
                    <div class="form-group" style="margin-top: 16px;">
                        <label>If workspace exists:</label>
                        <select id="conflict-resolution">
                            <option value="skip">Skip (keep existing)</option>
                            <option value="rename">Rename (add suffix)</option>
                            <option value="overwrite">Overwrite (replace existing)</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                <button class="btn btn-primary" id="import-btn" onclick="performImport()" disabled>Import</button>
            </div>
        </div>
    </div>

    <!-- Group Management Modal -->
    <div class="modal-overlay" id="group-modal">
        <div class="modal">
            <div class="modal-header">
                <h2 id="group-modal-title">New Group</h2>
                <button class="modal-close" onclick="closeModal('group-modal')">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label for="group-name">Group Name</label>
                    <input type="text" id="group-name" placeholder="Development">
                </div>
                <div class="form-group">
                    <label>Color</label>
                    <div class="color-picker" id="color-picker">
                        <!-- Populated by JS -->
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-danger" id="delete-group-btn" onclick="deleteGroup()" style="margin-right: auto; display: none;">Delete Group</button>
                <button class="btn btn-secondary" onclick="closeModal('group-modal')">Cancel</button>
                <button class="btn btn-primary" onclick="saveGroup()">Save</button>
            </div>
        </div>
    </div>

    <!-- Save as Template Modal -->
    <div class="modal-overlay" id="save-template-modal">
        <div class="modal">
            <div class="modal-header">
                <h2>Save as Template</h2>
                <button class="modal-close" onclick="closeModal('save-template-modal')">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label for="save-template-name">Template Name *</label>
                    <input type="text" id="save-template-name" placeholder="My Custom Template">
                </div>
                <div class="form-group">
                    <label for="save-template-desc">Description</label>
                    <input type="text" id="save-template-desc" placeholder="A brief description">
                </div>
                <p class="hint" style="margin-top: 12px;">The current workspace settings (except name and directory) will be saved as a reusable template.</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal('save-template-modal')">Cancel</button>
                <button class="btn btn-primary" onclick="saveAsTemplate()">Save Template</button>
            </div>
        </div>
    </div>

    <script>
        // State
        let workspaces = {};
        let groups = {};
        let templates = {};
        let history = [];
        let colors = [];
        let currentWorkspace = null;
        let availableTools = [];
        let availableIdes = {};
        let selectedTemplate = null;
        let importData = null;
        let editingGroup = null;
        let selectedGroupColor = null;

        // Initialize
        async function init() {
            await Promise.all([
                loadWorkspaces(),
                loadGroups(),
                loadTemplates(),
                loadHistory(),
                loadColors(),
                loadTools(),
                loadIdes()
            ]);
            renderRecentHistory();
            renderWorkspaceList();
            showEmptyState();
            setupDragDrop();
        }

        // API Functions
        async function loadWorkspaces() {
            const res = await fetch('/api/workspaces');
            workspaces = await res.json();
        }

        async function loadGroups() {
            const res = await fetch('/api/groups');
            groups = await res.json();
        }

        async function loadTemplates() {
            const res = await fetch('/api/templates');
            templates = await res.json();
        }

        async function loadHistory() {
            const res = await fetch('/api/history?limit=5');
            const data = await res.json();
            history = data.history || [];
        }

        async function loadColors() {
            const res = await fetch('/api/colors');
            colors = await res.json();
        }

        async function loadTools() {
            const res = await fetch('/api/tools');
            availableTools = await res.json();
        }

        async function loadIdes() {
            const res = await fetch('/api/ides');
            availableIdes = await res.json();
        }

        // Time formatting
        function timeAgo(dateString) {
            const date = new Date(dateString);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);

            if (seconds < 60) return 'just now';
            if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
            if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
            if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';
            return date.toLocaleDateString();
        }

        // Render Functions
        function renderRecentHistory() {
            const content = document.getElementById('recent-content');

            if (history.length === 0) {
                content.innerHTML = '<div style="padding: 12px 20px; color: var(--text-dim); font-size: 12px;">No recent launches</div>';
                return;
            }

            content.innerHTML = history.map(h => `
                <div class="history-item" onclick="selectWorkspace('${h.workspace_name}')">
                    <div class="history-item-info">
                        <div class="history-item-name">${h.workspace_name}</div>
                        <div class="history-item-time">${timeAgo(h.launched_at)}</div>
                    </div>
                    <div class="history-item-actions">
                        <button class="btn-icon play" onclick="event.stopPropagation(); quickLaunch('${h.workspace_name}')" title="Launch">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function renderWorkspaceList() {
            const list = document.getElementById('workspace-list');
            const names = Object.keys(workspaces).sort();

            if (names.length === 0) {
                list.innerHTML = '<div style="padding: 20px; color: var(--text-dim); font-size: 13px;">No workspaces yet</div>';
                return;
            }

            // Group workspaces
            const grouped = {};
            const ungrouped = [];

            names.forEach(name => {
                const ws = workspaces[name];
                const groupName = ws.group || '';
                if (groupName && groups[groupName]) {
                    if (!grouped[groupName]) grouped[groupName] = [];
                    grouped[groupName].push(name);
                } else {
                    ungrouped.push(name);
                }
            });

            let html = '';

            // Render groups
            const sortedGroups = Object.keys(groups).sort((a, b) => (groups[a].order || 0) - (groups[b].order || 0));

            sortedGroups.forEach(groupName => {
                const groupWs = grouped[groupName] || [];
                const group = groups[groupName];
                html += `
                    <div class="group-header" onclick="toggleGroup('${groupName}')" oncontextmenu="event.preventDefault(); showGroupModal('${groupName}')">
                        <span class="group-color-dot" style="background: ${group.color || '#58a6ff'}"></span>
                        <span>${groupName}</span>
                        <span class="group-count">${groupWs.length}</span>
                        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M6 9l6 6 6-6"/>
                        </svg>
                    </div>
                    <div class="group-workspaces" id="group-${groupName.replace(/\\s+/g, '-')}">
                        ${groupWs.map(name => renderWorkspaceItem(name)).join('')}
                    </div>
                `;
            });

            // Render ungrouped
            if (ungrouped.length > 0) {
                html += `
                    <div class="group-header" onclick="toggleGroup('ungrouped')">
                        <span class="group-color-dot" style="background: var(--text-dim)"></span>
                        <span>Ungrouped</span>
                        <span class="group-count">${ungrouped.length}</span>
                        <svg class="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M6 9l6 6 6-6"/>
                        </svg>
                    </div>
                    <div class="group-workspaces" id="group-ungrouped">
                        ${ungrouped.map(name => renderWorkspaceItem(name)).join('')}
                    </div>
                `;
            }

            // Add "New Group" button
            html += `
                <div class="group-header" onclick="showGroupModal()" style="color: var(--accent-dim);">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    <span>New Group</span>
                </div>
            `;

            list.innerHTML = html;
        }

        function renderWorkspaceItem(name) {
            const ws = workspaces[name];
            const isActive = currentWorkspace && currentWorkspace.name === name;
            return `
                <div class="workspace-item ${isActive ? 'active' : ''}" onclick="selectWorkspace('${name}')">
                    <span class="workspace-item-name">${name}</span>
                    ${ws.model ? `<span class="workspace-item-badge">${ws.model}</span>` : ''}
                </div>
            `;
        }

        function toggleGroup(groupName) {
            const el = document.getElementById('group-' + groupName.replace(/\\s+/g, '-'));
            if (el) el.classList.toggle('collapsed');
        }

        function toggleSection(section) {
            const header = document.querySelector(`#${section}-section .sidebar-section-header`);
            const content = document.getElementById(`${section}-content`);
            header.classList.toggle('collapsed');
            content.classList.toggle('collapsed');
        }

        function showEmptyState() {
            document.getElementById('main-content').innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M9 9h6M9 13h6M9 17h4"/>
                    </svg>
                    <h2>No Workspace Selected</h2>
                    <p>Create a new workspace or select an existing one from the sidebar.</p>
                </div>
            `;
            document.getElementById('quick-launch').style.display = 'none';
        }

        function renderWorkspaceForm(ws) {
            const ideOptions = Object.entries(availableIdes)
                .map(([ide, available]) => {
                    const label = ide === 'terminal' ? 'Terminal Only' :
                                  ide === 'vscode' ? 'VS Code' :
                                  ide === 'vscode-insiders' ? 'VS Code Insiders' :
                                  ide === 'cursor' ? 'Cursor' : ide;
                    return `<option value="${ide}" ${!available && ide !== 'terminal' ? 'disabled' : ''} ${ws.ide === ide ? 'selected' : ''}>${label}${!available && ide !== 'terminal' ? ' (not found)' : ''}</option>`;
                }).join('');

            const toolCheckboxes = availableTools.map(tool => `
                <label class="tool-item ${ws.allowed_tools?.includes(tool) ? 'selected' : ''}">
                    <input type="checkbox" name="allowed_tools" value="${tool}"
                           ${ws.allowed_tools?.includes(tool) ? 'checked' : ''}
                           onchange="this.parentElement.classList.toggle('selected', this.checked)">
                    ${tool}
                </label>
            `).join('');

            const disallowedToolCheckboxes = availableTools.map(tool => `
                <label class="tool-item ${ws.disallowed_tools?.includes(tool) ? 'selected' : ''}">
                    <input type="checkbox" name="disallowed_tools" value="${tool}"
                           ${ws.disallowed_tools?.includes(tool) ? 'checked' : ''}
                           onchange="this.parentElement.classList.toggle('selected', this.checked)">
                    ${tool}
                </label>
            `).join('');

            const envVarsText = Object.entries(ws.env_vars || {})
                .map(([k, v]) => `${k}=${v}`).join('\\n');

            // Group options
            const groupOptions = ['<option value="">No Group</option>']
                .concat(Object.keys(groups).sort().map(g =>
                    `<option value="${g}" ${ws.group === g ? 'selected' : ''}>${g}</option>`
                )).join('');

            document.getElementById('main-content').innerHTML = `
                <div class="main-header">
                    <h1>${ws.name || 'New Workspace'}${ws.template_source ? `<span class="template-source-badge">from ${templates[ws.template_source]?.name || ws.template_source}</span>` : ''}</h1>
                    <div class="header-actions">
                        ${ws.name ? `<button class="btn btn-secondary" onclick="exportWorkspace('${ws.name}')">Export</button>` : ''}
                        ${ws.name ? `<button class="btn btn-secondary" onclick="showSaveTemplateModal()">Save as Template</button>` : ''}
                        ${ws.name ? `<button class="btn btn-danger" onclick="deleteWorkspace()">Delete</button>` : ''}
                        <button class="btn btn-secondary" onclick="cancelEdit()">Cancel</button>
                        <button class="btn btn-primary" onclick="saveWorkspace()">Save</button>
                    </div>
                </div>

                <div class="form-container">
                    <form id="workspace-form" class="form-grid">
                        <!-- Basic Info -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
                                </svg>
                                Basic Info
                            </h3>
                            <div class="form-group">
                                <label for="name">Workspace Name *</label>
                                <input type="text" id="name" name="name" value="${ws.name || ''}"
                                       placeholder="my-project" required ${ws.name ? 'readonly' : ''}>
                            </div>
                            <div class="form-group">
                                <label for="description">Description</label>
                                <input type="text" id="description" name="description" value="${ws.description || ''}"
                                       placeholder="A brief description of this workspace">
                            </div>
                            <div class="form-group">
                                <label for="group">Group</label>
                                <select id="group" name="group">
                                    ${groupOptions}
                                </select>
                            </div>
                        </div>

                        <!-- Directory -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                                </svg>
                                Directory
                            </h3>
                            <div class="form-group">
                                <label for="working_dir">Working Directory</label>
                                <input type="text" id="working_dir" name="working_dir" value="${ws.working_dir || ''}"
                                       placeholder="~/projects/my-app">
                                <div class="hint">Leave empty to use current directory</div>
                            </div>
                            <div class="form-group">
                                <label for="additional_dirs">Additional Directories</label>
                                <textarea id="additional_dirs" name="additional_dirs"
                                          placeholder="One directory per line">${(ws.additional_dirs || []).join('\\n')}</textarea>
                                <div class="hint">Additional --add-dir paths, one per line</div>
                            </div>
                        </div>

                        <!-- IDE Integration -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="2" y="3" width="20" height="14" rx="2"/>
                                    <path d="M8 21h8M12 17v4"/>
                                </svg>
                                IDE Integration
                            </h3>
                            <div class="form-group">
                                <label for="ide">Launch Target</label>
                                <select id="ide" name="ide">
                                    ${ideOptions}
                                </select>
                            </div>
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="open_folder_in_ide" name="open_folder_in_ide"
                                           ${ws.open_folder_in_ide ? 'checked' : ''}>
                                    Open working directory in IDE
                                </label>
                            </div>
                        </div>

                        <!-- Model -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="3"/>
                                    <path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24"/>
                                </svg>
                                Model
                            </h3>
                            <div class="form-group">
                                <label for="model">Primary Model</label>
                                <select id="model" name="model">
                                    <option value="" ${!ws.model ? 'selected' : ''}>Default</option>
                                    <option value="sonnet" ${ws.model === 'sonnet' ? 'selected' : ''}>Sonnet (Fast, balanced)</option>
                                    <option value="opus" ${ws.model === 'opus' ? 'selected' : ''}>Opus (Most capable)</option>
                                    <option value="haiku" ${ws.model === 'haiku' ? 'selected' : ''}>Haiku (Fastest)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="fallback_model">Fallback Model</label>
                                <select id="fallback_model" name="fallback_model">
                                    <option value="" ${!ws.fallback_model ? 'selected' : ''}>None</option>
                                    <option value="sonnet" ${ws.fallback_model === 'sonnet' ? 'selected' : ''}>Sonnet</option>
                                    <option value="opus" ${ws.fallback_model === 'opus' ? 'selected' : ''}>Opus</option>
                                    <option value="haiku" ${ws.fallback_model === 'haiku' ? 'selected' : ''}>Haiku</option>
                                </select>
                                <div class="hint">Used when primary model is overloaded</div>
                            </div>
                        </div>

                        <!-- Permissions -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                                Permissions
                            </h3>
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="skip_permissions" name="skip_permissions"
                                           ${ws.skip_permissions ? 'checked' : ''}>
                                    Skip permission prompts (--dangerously-skip-permissions)
                                </label>
                            </div>
                            <div class="form-group">
                                <label for="permission_mode">Permission Mode</label>
                                <select id="permission_mode" name="permission_mode">
                                    <option value="" ${!ws.permission_mode ? 'selected' : ''}>Default</option>
                                    <option value="plan" ${ws.permission_mode === 'plan' ? 'selected' : ''}>Plan Mode</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Allowed Tools (auto-approved)</label>
                                <div class="tool-grid">
                                    ${toolCheckboxes}
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Disallowed Tools (blocked)</label>
                                <div class="tool-grid">
                                    ${disallowedToolCheckboxes}
                                </div>
                            </div>
                        </div>

                        <!-- System Prompt -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                                </svg>
                                System Prompt
                            </h3>
                            <div class="form-group">
                                <label for="append_system_prompt">Append to System Prompt</label>
                                <textarea id="append_system_prompt" name="append_system_prompt"
                                          placeholder="Additional instructions for Claude...">${ws.append_system_prompt || ''}</textarea>
                            </div>
                            <div class="form-group">
                                <label for="system_prompt_file">System Prompt File</label>
                                <input type="text" id="system_prompt_file" name="system_prompt_file"
                                       value="${ws.system_prompt_file || ''}" placeholder="~/prompts/my-prompt.txt">
                            </div>
                        </div>

                        <!-- MCP & Agent -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                                    <path d="M2 17l10 5 10-5"/>
                                    <path d="M2 12l10 5 10-5"/>
                                </svg>
                                MCP & Agent
                            </h3>
                            <div class="form-group">
                                <label for="mcp_config">MCP Config Path</label>
                                <input type="text" id="mcp_config" name="mcp_config"
                                       value="${ws.mcp_config || ''}" placeholder="~/.claude/mcp-config.json">
                            </div>
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="strict_mcp" name="strict_mcp"
                                           ${ws.strict_mcp ? 'checked' : ''}>
                                    Strict MCP config (--strict-mcp-config)
                                </label>
                            </div>
                            <div class="form-group">
                                <label for="agent">Agent</label>
                                <input type="text" id="agent" name="agent"
                                       value="${ws.agent || ''}" placeholder="Agent name">
                            </div>
                        </div>

                        <!-- Debug -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/>
                                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                                    <circle cx="12" cy="17" r=".5"/>
                                </svg>
                                Debug & Output
                            </h3>
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="verbose" name="verbose"
                                           ${ws.verbose ? 'checked' : ''}>
                                    Verbose output (--verbose)
                                </label>
                            </div>
                            <div class="form-group">
                                <label for="debug_categories">Debug Categories</label>
                                <input type="text" id="debug_categories" name="debug_categories"
                                       value="${ws.debug_categories || ''}" placeholder="category1,category2">
                            </div>
                        </div>

                        <!-- Environment Variables -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                                </svg>
                                Environment Variables
                            </h3>
                            <div class="form-group">
                                <label for="env_vars">Environment Variables</label>
                                <textarea id="env_vars" name="env_vars"
                                          placeholder="KEY=value&#10;ANOTHER_KEY=another_value">${envVarsText}</textarea>
                                <div class="hint">One per line in KEY=value format</div>
                            </div>
                        </div>

                        <!-- Project Setup -->
                        <div class="form-section">
                            <h3>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                                </svg>
                                Project Setup
                            </h3>
                            <div class="form-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="init_claude_md" name="init_claude_md"
                                           ${ws.init_claude_md ? 'checked' : ''}>
                                    Create CLAUDE.md if missing
                                </label>
                            </div>
                            <div class="form-group">
                                <label for="claude_md_content">CLAUDE.md Content</label>
                                <textarea id="claude_md_content" name="claude_md_content"
                                          placeholder="# Project&#10;&#10;Description of the project...">${ws.claude_md_content || ''}</textarea>
                            </div>
                        </div>
                    </form>
                </div>
            `;

            // Update quick launch bar
            updateQuickLaunch(ws);
        }

        function updateQuickLaunch(ws) {
            const bar = document.getElementById('quick-launch');
            if (!ws || !ws.name) {
                bar.style.display = 'none';
                return;
            }

            bar.style.display = 'flex';
            document.getElementById('launch-name').textContent = ws.name;

            const tags = [];
            if (ws.model) tags.push(ws.model);
            if (ws.ide && ws.ide !== 'terminal') tags.push(ws.ide);
            if (ws.skip_permissions) tags.push('no-perms');

            document.getElementById('launch-tags').textContent = tags.length ? ` - ${tags.join(' - ')}` : '';
        }

        // Actions
        function createNewWorkspace() {
            currentWorkspace = { ...getDefaultWorkspace() };
            renderWorkspaceForm(currentWorkspace);
            renderWorkspaceList();
        }

        function selectWorkspace(name) {
            currentWorkspace = { ...workspaces[name] };
            renderWorkspaceForm(currentWorkspace);
            renderWorkspaceList();
        }

        function cancelEdit() {
            if (currentWorkspace && currentWorkspace.name && workspaces[currentWorkspace.name]) {
                currentWorkspace = { ...workspaces[currentWorkspace.name] };
                renderWorkspaceForm(currentWorkspace);
            } else {
                currentWorkspace = null;
                showEmptyState();
            }
            renderWorkspaceList();
        }

        function getDefaultWorkspace() {
            return {
                name: '',
                description: '',
                working_dir: '',
                additional_dirs: [],
                model: '',
                fallback_model: '',
                skip_permissions: false,
                permission_mode: '',
                allowed_tools: [],
                disallowed_tools: [],
                append_system_prompt: '',
                system_prompt_file: '',
                mcp_config: '',
                strict_mcp: false,
                agent: '',
                verbose: false,
                debug_categories: '',
                env_vars: {},
                ide: 'terminal',
                open_folder_in_ide: false,
                init_claude_md: false,
                claude_md_content: '',
                created: '',
                last_used: '',
                use_count: 0,
                group: '',
                template_source: ''
            };
        }

        function getFormData() {
            const form = document.getElementById('workspace-form');
            const data = getDefaultWorkspace();

            // Basic fields
            data.name = form.name.value.trim();
            data.description = form.description.value.trim();
            data.working_dir = form.working_dir.value.trim();
            data.model = form.model.value;
            data.fallback_model = form.fallback_model.value;
            data.skip_permissions = form.skip_permissions.checked;
            data.permission_mode = form.permission_mode.value;
            data.append_system_prompt = form.append_system_prompt.value;
            data.system_prompt_file = form.system_prompt_file.value.trim();
            data.mcp_config = form.mcp_config.value.trim();
            data.strict_mcp = form.strict_mcp.checked;
            data.agent = form.agent.value.trim();
            data.verbose = form.verbose.checked;
            data.debug_categories = form.debug_categories.value.trim();
            data.ide = form.ide.value;
            data.open_folder_in_ide = form.open_folder_in_ide.checked;
            data.init_claude_md = form.init_claude_md.checked;
            data.claude_md_content = form.claude_md_content.value;

            // Group
            if (form.group) {
                data.group = form.group.value;
            }

            // Additional directories
            data.additional_dirs = form.additional_dirs.value
                .split('\\n')
                .map(d => d.trim())
                .filter(d => d);

            // Allowed tools
            data.allowed_tools = Array.from(form.querySelectorAll('input[name="allowed_tools"]:checked'))
                .map(cb => cb.value);

            // Disallowed tools
            data.disallowed_tools = Array.from(form.querySelectorAll('input[name="disallowed_tools"]:checked'))
                .map(cb => cb.value);

            // Environment variables
            data.env_vars = {};
            form.env_vars.value.split('\\n').forEach(line => {
                const [key, ...rest] = line.split('=');
                if (key && rest.length) {
                    data.env_vars[key.trim()] = rest.join('=').trim();
                }
            });

            return data;
        }

        async function saveWorkspace() {
            const data = getFormData();

            if (!data.name) {
                showToast('Workspace name is required', 'error');
                return;
            }

            try {
                const res = await fetch('/api/workspaces', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    await loadWorkspaces();
                    currentWorkspace = workspaces[data.name];
                    renderWorkspaceList();
                    renderWorkspaceForm(currentWorkspace);
                    showToast('Workspace saved', 'success');
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Failed to save', 'error');
                }
            } catch (e) {
                showToast('Failed to save workspace', 'error');
            }
        }

        async function deleteWorkspace() {
            if (!currentWorkspace || !currentWorkspace.name) return;

            if (!confirm(`Delete workspace "${currentWorkspace.name}"?`)) return;

            try {
                await fetch(`/api/workspaces/${encodeURIComponent(currentWorkspace.name)}`, {
                    method: 'DELETE'
                });

                await loadWorkspaces();
                currentWorkspace = null;
                renderWorkspaceList();
                showEmptyState();
                showToast('Workspace deleted', 'success');
            } catch (e) {
                showToast('Failed to delete workspace', 'error');
            }
        }

        async function copyCommand() {
            if (!currentWorkspace || !currentWorkspace.name) return;

            try {
                const res = await fetch(`/api/workspaces/${encodeURIComponent(currentWorkspace.name)}/command`);
                const data = await res.json();

                await navigator.clipboard.writeText(data.command);
                showToast('Command copied to clipboard', 'success');
            } catch (e) {
                showToast('Failed to copy command', 'error');
            }
        }

        async function launchWorkspace() {
            if (!currentWorkspace || !currentWorkspace.name) return;

            // Save first to ensure latest changes
            await saveWorkspace();

            try {
                const res = await fetch(`/api/workspaces/${encodeURIComponent(currentWorkspace.name)}/launch`, {
                    method: 'POST'
                });

                if (res.ok) {
                    showToast('Launching workspace...', 'success');
                    // Reload to update use count
                    await loadWorkspaces();
                    if (workspaces[currentWorkspace.name]) {
                        currentWorkspace = workspaces[currentWorkspace.name];
                    }
                } else {
                    showToast('Failed to launch', 'error');
                }
            } catch (e) {
                showToast('Failed to launch workspace', 'error');
            }
        }

        // Toast notification
        function showToast(message, type = 'info') {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();

            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);

            setTimeout(() => toast.remove(), 3000);
        }

        // Quick launch from history
        async function quickLaunch(name) {
            if (!workspaces[name]) {
                showToast('Workspace not found', 'error');
                return;
            }

            try {
                const res = await fetch(`/api/workspaces/${encodeURIComponent(name)}/launch`, {
                    method: 'POST'
                });

                if (res.ok) {
                    showToast('Launching ' + name + '...', 'success');
                    await loadHistory();
                    renderRecentHistory();
                } else {
                    showToast('Failed to launch', 'error');
                }
            } catch (e) {
                showToast('Failed to launch', 'error');
            }
        }

        // Modal functions
        function openModal(id) {
            document.getElementById(id).classList.add('active');
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }

        // Template Modal
        function showTemplateModal() {
            selectedTemplate = null;
            document.getElementById('template-ws-name').value = '';
            document.getElementById('template-ws-dir').value = '';

            const grid = document.getElementById('template-grid');
            grid.innerHTML = Object.entries(templates).map(([id, t]) => `
                <div class="template-card" onclick="selectTemplate('${id}')" id="template-${id}">
                    <svg class="template-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        ${getTemplateIcon(t.icon)}
                    </svg>
                    <div class="template-card-name">${t.name}</div>
                    <div class="template-card-desc">${t.description || ''}</div>
                    ${t.builtin ? '<span class="template-card-badge">Built-in</span>' : '<span class="template-card-badge">Custom</span>'}
                </div>
            `).join('');

            openModal('template-modal');
        }

        function getTemplateIcon(icon) {
            const icons = {
                python: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
                nodejs: '<circle cx="12" cy="12" r="10"/><path d="M8 12l4 4 4-4"/>',
                react: '<circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>',
                rust: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 8v8M8 12h8"/>',
                folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>'
            };
            return icons[icon] || icons.folder;
        }

        function selectTemplate(id) {
            selectedTemplate = id;
            document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
            document.getElementById('template-' + id).classList.add('selected');
        }

        async function createFromTemplate() {
            if (!selectedTemplate) {
                showToast('Please select a template', 'error');
                return;
            }

            const name = document.getElementById('template-ws-name').value.trim();
            const workingDir = document.getElementById('template-ws-dir').value.trim();

            if (!name) {
                showToast('Workspace name is required', 'error');
                return;
            }

            try {
                const res = await fetch('/api/workspaces/from-template', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        template_id: selectedTemplate,
                        name: name,
                        working_dir: workingDir
                    })
                });

                if (res.ok) {
                    const data = await res.json();
                    await loadWorkspaces();
                    renderWorkspaceList();
                    selectWorkspace(name);
                    closeModal('template-modal');
                    showToast('Workspace created from template', 'success');
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Failed to create workspace', 'error');
                }
            } catch (e) {
                showToast('Failed to create workspace', 'error');
            }
        }

        // Save as Template Modal
        function showSaveTemplateModal() {
            if (!currentWorkspace || !currentWorkspace.name) {
                showToast('No workspace selected', 'error');
                return;
            }
            document.getElementById('save-template-name').value = '';
            document.getElementById('save-template-desc').value = '';
            openModal('save-template-modal');
        }

        async function saveAsTemplate() {
            const name = document.getElementById('save-template-name').value.trim();
            const desc = document.getElementById('save-template-desc').value.trim();

            if (!name) {
                showToast('Template name is required', 'error');
                return;
            }

            const templateId = name.toLowerCase().replace(/\\s+/g, '-');
            const config = { ...currentWorkspace };
            delete config.name;
            delete config.working_dir;
            delete config.created;
            delete config.last_used;
            delete config.use_count;
            delete config.group;
            delete config.template_source;

            try {
                const res = await fetch('/api/templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: templateId,
                        name: name,
                        description: desc,
                        config: config
                    })
                });

                if (res.ok) {
                    await loadTemplates();
                    closeModal('save-template-modal');
                    showToast('Template saved', 'success');
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Failed to save template', 'error');
                }
            } catch (e) {
                showToast('Failed to save template', 'error');
            }
        }

        // Group Modal
        function showGroupModal(groupName = null) {
            editingGroup = groupName;
            document.getElementById('group-modal-title').textContent = groupName ? 'Edit Group' : 'New Group';
            document.getElementById('group-name').value = groupName || '';
            document.getElementById('delete-group-btn').style.display = groupName ? 'block' : 'none';

            // Render color picker
            const existingColor = groupName && groups[groupName] ? groups[groupName].color : null;
            selectedGroupColor = existingColor || colors[0];

            document.getElementById('color-picker').innerHTML = colors.map(c => `
                <div class="color-option ${c === selectedGroupColor ? 'selected' : ''}"
                     style="background: ${c}"
                     onclick="selectGroupColor('${c}')"></div>
            `).join('');

            openModal('group-modal');
        }

        function selectGroupColor(color) {
            selectedGroupColor = color;
            document.querySelectorAll('.color-option').forEach(el => {
                el.classList.toggle('selected', el.style.background === color);
            });
        }

        async function saveGroup() {
            const name = document.getElementById('group-name').value.trim();

            if (!name) {
                showToast('Group name is required', 'error');
                return;
            }

            try {
                if (editingGroup) {
                    // Update existing group
                    const res = await fetch(`/api/groups/${encodeURIComponent(editingGroup)}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            new_name: name !== editingGroup ? name : undefined,
                            color: selectedGroupColor
                        })
                    });

                    if (!res.ok) {
                        const err = await res.json();
                        showToast(err.error || 'Failed to update group', 'error');
                        return;
                    }
                } else {
                    // Create new group
                    const res = await fetch('/api/groups', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: name,
                            color: selectedGroupColor
                        })
                    });

                    if (!res.ok) {
                        const err = await res.json();
                        showToast(err.error || 'Failed to create group', 'error');
                        return;
                    }
                }

                await loadGroups();
                await loadWorkspaces();
                renderWorkspaceList();
                closeModal('group-modal');
                showToast(editingGroup ? 'Group updated' : 'Group created', 'success');
            } catch (e) {
                showToast('Failed to save group', 'error');
            }
        }

        async function deleteGroup() {
            if (!editingGroup) return;

            if (!confirm(`Delete group "${editingGroup}"? Workspaces will be moved to ungrouped.`)) return;

            try {
                await fetch(`/api/groups/${encodeURIComponent(editingGroup)}`, {
                    method: 'DELETE'
                });

                await loadGroups();
                await loadWorkspaces();
                renderWorkspaceList();
                closeModal('group-modal');
                showToast('Group deleted', 'success');
            } catch (e) {
                showToast('Failed to delete group', 'error');
            }
        }

        // Import Modal
        function showImportModal() {
            importData = null;
            document.getElementById('import-preview').style.display = 'none';
            document.getElementById('import-dropzone').style.display = 'block';
            document.getElementById('import-btn').disabled = true;
            document.getElementById('import-file').value = '';
            openModal('import-modal');
        }

        function handleImportFile(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    importData = JSON.parse(e.target.result);

                    // Show preview
                    const previewList = document.getElementById('import-preview-list');
                    const wsToImport = importData.workspaces || [];

                    previewList.innerHTML = wsToImport.map(ws => {
                        const exists = workspaces[ws.name];
                        return `
                            <div class="import-preview-item">
                                <span>${ws.name}</span>
                                ${exists ? '<span class="conflict-badge">Exists</span>' : ''}
                            </div>
                        `;
                    }).join('');

                    document.getElementById('import-dropzone').style.display = 'none';
                    document.getElementById('import-preview').style.display = 'block';
                    document.getElementById('import-btn').disabled = false;
                } catch (err) {
                    showToast('Invalid JSON file', 'error');
                }
            };
            reader.readAsText(file);
        }

        async function performImport() {
            if (!importData) return;

            const resolution = document.getElementById('conflict-resolution').value;

            try {
                const res = await fetch('/api/import/workspace', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        workspaces: importData.workspaces || [],
                        groups: importData.groups || {},
                        conflict_resolution: resolution
                    })
                });

                if (res.ok) {
                    const result = await res.json();
                    await loadWorkspaces();
                    await loadGroups();
                    renderWorkspaceList();
                    closeModal('import-modal');

                    const msg = `Imported ${result.imported.length} workspace(s)` +
                        (result.skipped.length ? `, skipped ${result.skipped.length}` : '') +
                        (Object.keys(result.renamed).length ? `, renamed ${Object.keys(result.renamed).length}` : '');
                    showToast(msg, 'success');
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Import failed', 'error');
                }
            } catch (e) {
                showToast('Import failed', 'error');
            }
        }

        // Export functions
        async function exportAll() {
            try {
                const res = await fetch('/api/export/all');
                const data = await res.json();

                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'claude-workspaces-export.json';
                a.click();
                URL.revokeObjectURL(url);

                showToast('Exported all workspaces', 'success');
            } catch (e) {
                showToast('Export failed', 'error');
            }
        }

        async function exportWorkspace(name) {
            try {
                const res = await fetch(`/api/export/workspace/${encodeURIComponent(name)}`);
                const data = await res.json();

                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `workspace-${name}.json`;
                a.click();
                URL.revokeObjectURL(url);

                showToast('Workspace exported', 'success');
            } catch (e) {
                showToast('Export failed', 'error');
            }
        }

        // Drag and drop setup
        function setupDragDrop() {
            const dropzone = document.getElementById('import-dropzone');
            if (!dropzone) return;

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            ['dragenter', 'dragover'].forEach(eventName => {
                dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
            });

            dropzone.addEventListener('drop', (e) => {
                const file = e.dataTransfer.files[0];
                if (file) {
                    document.getElementById('import-file').files = e.dataTransfer.files;
                    handleImportFile({ target: { files: [file] } });
                }
            }, false);
        }

        // Initialize on load
        init();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the main application."""
    return Response(HTML_TEMPLATE, mimetype='text/html')

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Claude Code Workspace Manager')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Port to run on (default: {DEFAULT_PORT})')
    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║         Claude Code Workspace Manager                         ║
╠═══════════════════════════════════════════════════════════════╣
║  Open in browser:  http://127.0.0.1:{args.port:<5}                   ║
║  Press Ctrl+C to stop                                         ║
╚═══════════════════════════════════════════════════════════════╝
""")

    # Ensure config directory exists
    ensure_config_dir()

    # Run Flask app
    app.run(host='127.0.0.1', port=args.port, debug=False)

if __name__ == '__main__':
    main()
