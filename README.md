# ➡️ browser-use mcp server

[![Twitter URL](https://img.shields.io/twitter/url/https/twitter.com/cobrowser.svg?style=social&label=Follow%20%40cobrowser)](https://x.com/cobrowser)
[![PyPI version](https://badge.fury.io/py/browser-use-mcp-server.svg)](https://pypi.org/project/browser-use-mcp-server/)

[browser-use](https://github.com/browser-use/browser-use) MCP Server with SSE +
stdio transport

### Requirements

- [uv](https://github.com/astral-sh/uv)
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) (for stdio)

```
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Install mcp-proxy pypi package via uv
uv tool install mcp-proxy
```

### Quickstart

Starting in SSE mode:

```bash
uv sync
uv pip install playwright
uv run playwright install --with-deps --no-shell chromium
uv run server --port 8000
```

With stdio mode:

```bash
# Run with stdio mode and specify a proxy port
uv run server --stdio --proxy-port 8001

# Or just stdio mode (random proxy port)
uv run server --stdio
```

- the .env requires the following:

```
OPENAI_API_KEY=[your api key]
CHROME_PATH=[only change this if you have a custom chrome build]
PATIENT=false # Set to true if you want api calls to wait for tasks to complete (default is false)
```

When building the docker image, you can use Docker secrets for VNC password:

```bash
# With Docker secrets (recommended for production)
echo "your-secure-password" > vnc_password.txt
docker run -v $(pwd)/vnc_password.txt:/run/secrets/vnc_password your-image-name

# Or during development with the default password
docker build .
```

### Local Development and Testing

To develop and test the package locally:

1. Build a distributable wheel:

```bash
# From the project root directory
uv build
```

2. Install it as a global tool using the built wheel:

```bash
uv tool install dist/browser_use_mcp_server-*.whl
```

3. Run the tool from any directory:

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

### Tools

- [x] SSE transport
- [x] stdio transport (via mcp-proxy)
- [x] browser_use - Initiates browser tasks with URL and action
- [x] browser_get_result - Retrieves results of async browser tasks
- [x] VNC server - stream the dockerized browser to your client

### VNC

the dockerfile has a vnc server with a default password of browser-use. connect
to it:

```
docker build -t  browser-use-mcp-server .
docker run --rm -p8000:8000 -p5900:5900 browser-use-mcp-server
git clone https://github.com/novnc/noVNC
cd noVNC
./utils/novnc_proxy --vnc localhost:5900
```

<p align="center">
<img width="428" alt="Screenshot 2025-03-24 at 12 03 15 PM" src="https://github.com/user-attachments/assets/45bc5bee-418d-4182-94f5-db84b4fc0b3a" />
<br>
<img width="428" alt="Screenshot 2025-03-24 at 12 11 42 PM" src="https://github.com/user-attachments/assets/7db53f41-fc00-4e48-8892-f7108096f9c4" />
</p>

### Supported Clients

- cursor.ai
- claude desktop
- claude code
- windsurf ([windsurf](https://codeium.com/windsurf) doesn't support SSE, only
  stdio)

#### SSE Mode

After running the server in SSE mode, add http://localhost:8000/sse to your
client UI, or in a mcp.json file:

```json
{
  "mcpServers": {
    "browser-use-mcp-server": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

#### stdio Mode

When running in stdio mode, the server will automatically start both the SSE
server and mcp-proxy. The proxy handles the conversion between stdio and SSE
protocols. No additional configuration is needed - just start your client and it
will communicate with the server through stdin/stdout.

For Windsurf integration, add this to your config:

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

### Client Configuration Paths

#### Cursor

- `./.cursor/mcp.json`

#### Windsurf

- `~/.codeium/windsurf/mcp_config.json`

#### Claude

- `~/Library/Application Support/Claude/claude_desktop_config.json`
- `%APPDATA%\Claude\claude_desktop_config.json`

### Example Usage

Try asking your LLM the following:

`open https://news.ycombinator.com and return the top ranked article`

### Help

for issues or interest reach out @ https://cobrowser.xyz

# Stars

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
</picture>
