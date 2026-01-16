# Claude Code Workspace Manager

A visual configuration and launch tool for Claude Code CLI. Save named workspace configurations, configure all CLI options through a web UI, and launch with one click.

## Features

- **Visual Configuration** - Form-based editor for all Claude Code CLI flags
- **Workspace Management** - Save, edit, and organize multiple workspace configurations
- **IDE Integration** - Launch with VS Code, Cursor, or VS Code Insiders
- **One-Click Launch** - Open terminal with full command ready to go
- **Zero Configuration** - Works immediately after download
- **Cross-Platform** - macOS and Linux support

## Quick Start

```bash
# Run the app
python workspace_manager.py

# Open in browser
open http://127.0.0.1:5199
```

Flask will be auto-installed if not present.

## Requirements

- Python 3.8+
- Flask (auto-installed on first run)
- VS Code / Cursor (optional, for IDE integration)

## Usage

1. **Create a Workspace** - Click "+ New Workspace" in the sidebar
2. **Configure Options** - Fill in the form fields:
   - Basic info (name, description)
   - Working directory
   - Model selection (sonnet, opus, haiku)
   - Permissions and allowed tools
   - System prompt customization
   - Environment variables
   - IDE integration settings
3. **Save** - Click "Save" to persist the configuration
4. **Launch** - Click "Launch" to open a terminal with Claude Code

## Supported Claude Code Options

| Option | Description |
|--------|-------------|
| `--model` | Primary model (sonnet, opus, haiku) |
| `--fallback-model` | Fallback when primary is overloaded |
| `--dangerously-skip-permissions` | Skip permission prompts |
| `--permission-mode` | Permission mode (plan) |
| `--allowedTools` | Tools to auto-approve |
| `--disallowedTools` | Tools to block |
| `--append-system-prompt` | Additional system prompt text |
| `--system-prompt-file` | Path to system prompt file |
| `--mcp-config` | Path to MCP configuration |
| `--strict-mcp-config` | Strict MCP config validation |
| `--agent` | Specific agent to use |
| `--verbose` | Verbose output |
| `--debug` | Debug categories |
| `--add-dir` | Additional directories |

## Storage

Workspaces are stored in `~/.claude-workspaces/workspaces.json`.

## Command Line Options

```bash
python workspace_manager.py --port 8080  # Use custom port
```

## Example Workspaces

See `example-workspaces.json` for sample configurations:

- **web-frontend** - React/TypeScript project with VS Code
- **python-api** - Python FastAPI backend with Cursor
- **quick-task** - Fast iteration with full permissions
- **code-review** - Read-only code review mode

## Security

- Server binds to `127.0.0.1` only (localhost)
- No external network access
- No authentication (local machine trust model)

## License

MIT License
