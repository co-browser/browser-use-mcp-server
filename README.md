# browser-use-mcp-server

<div align="center">

[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/cobrowser.svg?style=social&label=Follow%20%40cobrowser)](https://x.com/cobrowser)
[![PyPI version](https://badge.fury.io/py/browser-use-mcp-server.svg)](https://pypi.org/project/browser-use-mcp-server/)

**An MCP server that enables AI agents to control web browsers using
[browser-use](https://github.com/browser-use/browser-use).**

</div>

## Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- [Playwright](https://playwright.dev/) - Browser automation
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) - Required for stdio mode

```bash
# Install prerequisites
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install mcp-proxy
uv tool update-shell
```

## Environment

Create a `.env` file:

```
OPENAI_API_KEY=your-api-key
CHROME_PATH=optional/path/to/chrome
PATIENT=false  # Set to true if API calls should wait for task completion
```

## Installation

```bash
# Install dependencies
uv sync
uv pip install playwright
uv run playwright install --with-deps --no-shell chromium
```

## Usage

### SSE Mode

```bash
# Run directly from source
uv run server --port 8000
```

### stdio Mode

```bash
# 1. Build and install globally
uv build
uv tool uninstall browser-use-mcp-server 2>/dev/null || true
uv tool install dist/browser_use_mcp_server-*.whl

# 2. Run with stdio transport
browser-use-mcp-server run server --port 8000 --stdio --proxy-port 9000
```

## Client Configuration

### SSE Mode

```json
{
  "mcpServers": {
    "browser-use-mcp-server": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### stdio Mode

```json
{
  "mcpServers": {
    "browser-server": {
      "command": "browser-use-mcp-server",
      "args": [
        "run",
        "server",
        "--port",
        "8000",
        "--stdio",
        "--proxy-port",
        "9000"
      ],
      "env": {
        "OPENAI_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Config Locations

| Client           | Configuration Path                                                |
| ---------------- | ----------------------------------------------------------------- |
| Cursor           | `./.cursor/mcp.json`                                              |
| Windsurf         | `~/.codeium/windsurf/mcp_config.json`                             |
| Claude (Mac)     | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude (Windows) | `%APPDATA%\Claude\claude_desktop_config.json`                     |

## Features

- [x] **Browser Automation**: Control browsers through AI agents
- [x] **Dual Transport**: Support for both SSE and stdio protocols
- [x] **VNC Streaming**: Watch browser automation in real-time
- [x] **Async Tasks**: Execute browser operations asynchronously

## Local Development

To develop and test the package locally:

1. Build a distributable wheel:

   ```bash
   # From the project root directory
   uv build
   ```

2. Install it as a global tool:

   ```bash
   uv tool uninstall browser-use-mcp-server 2>/dev/null || true
   uv tool install dist/browser_use_mcp_server-*.whl
   ```

3. Run from any directory:

   ```bash
   # Set your OpenAI API key for the current session
   export OPENAI_API_KEY=your-api-key-here

   # Or provide it inline for a one-time run
   OPENAI_API_KEY=your-api-key-here browser-use-mcp-server run server --port 8000 --stdio --proxy-port 9000
   ```

4. After making changes, rebuild and reinstall:
   ```bash
   uv build
   uv tool uninstall browser-use-mcp-server
   uv tool install dist/browser_use_mcp_server-*.whl
   ```

## Docker

```bash
# Run with default VNC password
docker build -t browser-use-mcp-server .
docker run --rm -p8000:8000 -p5900:5900 browser-use-mcp-server

# Use custom VNC password
echo "your-password" > vnc_password.txt
docker run --rm -p8000:8000 -p5900:5900 \
  -v $(pwd)/vnc_password.txt:/run/secrets/vnc_password \
  browser-use-mcp-server
```

### VNC Viewer

```bash
# Browser-based viewer
git clone https://github.com/novnc/noVNC
cd noVNC
./utils/novnc_proxy --vnc localhost:5900
```

Default password: `browser-use`

<div align="center">
  <img width="428" alt="VNC Screenshot" src="https://github.com/user-attachments/assets/45bc5bee-418d-4182-94f5-db84b4fc0b3a" />
  <br><br>
  <img width="428" alt="VNC Screenshot" src="https://github.com/user-attachments/assets/7db53f41-fc00-4e48-8892-f7108096f9c4" />
</div>

## Example

Try asking your AI:

```
open https://news.ycombinator.com and return the top ranked article
```

## Support

For issues or inquiries: [cobrowser.xyz](https://cobrowser.xyz)

## Star History

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
  </picture>
</div>
