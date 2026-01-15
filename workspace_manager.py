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
    "use_count": 0
}

app = Flask(__name__)

# ============================================================================
# Storage Layer
# ============================================================================

def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_workspaces() -> dict:
    """Load workspaces from JSON file."""
    ensure_config_dir()
    if WORKSPACES_FILE.exists():
        try:
            with open(WORKSPACES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_workspaces(workspaces: dict):
    """Save workspaces to JSON file."""
    ensure_config_dir()
    with open(WORKSPACES_FILE, 'w') as f:
        json.dump(workspaces, f, indent=2)

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

    # Generate launch script
    script_content = build_launch_script(ws)
    ensure_config_dir()
    with open(LAUNCH_SCRIPT, 'w') as f:
        f.write(script_content)
    os.chmod(LAUNCH_SCRIPT, 0o755)

    # Get working directory
    working_dir = os.path.expanduser(ws.get('working_dir', '')) or os.getcwd()

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

            <button class="btn-new" onclick="createNewWorkspace()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 5v14M5 12h14"/>
                </svg>
                New Workspace
            </button>

            <div class="workspace-list-header">Workspaces</div>
            <ul class="workspace-list" id="workspace-list">
                <!-- Populated by JS -->
            </ul>
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

    <script>
        // State
        let workspaces = {};
        let currentWorkspace = null;
        let availableTools = [];
        let availableIdes = {};

        // Initialize
        async function init() {
            await Promise.all([
                loadWorkspaces(),
                loadTools(),
                loadIdes()
            ]);
            renderWorkspaceList();
            showEmptyState();
        }

        // API Functions
        async function loadWorkspaces() {
            const res = await fetch('/api/workspaces');
            workspaces = await res.json();
        }

        async function loadTools() {
            const res = await fetch('/api/tools');
            availableTools = await res.json();
        }

        async function loadIdes() {
            const res = await fetch('/api/ides');
            availableIdes = await res.json();
        }

        // Render Functions
        function renderWorkspaceList() {
            const list = document.getElementById('workspace-list');
            const names = Object.keys(workspaces).sort();

            if (names.length === 0) {
                list.innerHTML = '<li style="padding: 20px; color: var(--text-dim); font-size: 13px;">No workspaces yet</li>';
                return;
            }

            list.innerHTML = names.map(name => {
                const ws = workspaces[name];
                const isActive = currentWorkspace && currentWorkspace.name === name;
                return `
                    <li class="workspace-item ${isActive ? 'active' : ''}" onclick="selectWorkspace('${name}')">
                        <span class="workspace-item-name">${name}</span>
                        ${ws.model ? `<span class="workspace-item-badge">${ws.model}</span>` : ''}
                    </li>
                `;
            }).join('');
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

            document.getElementById('main-content').innerHTML = `
                <div class="main-header">
                    <h1>${ws.name || 'New Workspace'}</h1>
                    <div class="header-actions">
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
                use_count: 0
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
