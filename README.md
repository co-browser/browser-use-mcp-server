# ➡️ browser-use mcp server

[browser-use](https://github.com/browser-use/browser-use) MCP Server with SSE
transport

### requirements

- uv

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### quickstart

```
uv sync
uv pip install playwright
uv run playwright install --with-deps --no-shell chromium
uv run server --port 8000
```

- the .env requires the following:

```
OPENAI_API_KEY=[your api key]
CHROME_PATH=[only change this if you have a custom chrome build]
```

- we will be adding support for other LLM providers to power browser-use
  (claude, grok, bedrock, etc)

when building the docker image, you can use Docker secrets for VNC password:

```
# With Docker secrets (recommended for production)
echo "your-secure-password" > vnc_password.txt
docker run -v $(pwd)/vnc_password.txt:/run/secrets/vnc_password your-image-name

# Or during development with the default password
docker build .
```

### tools

- [x] SSE transport
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

### supported clients

- cursor.ai
- claude desktop
- claude code
- <s>windsurf</s> ([windsurf](https://codeium.com/windsurf) doesn't support SSE
  yet)

### usage

after running the server, add http://localhost:8000/sse to your client UI, or in
a mcp.json file:

```json
{
  "mcpServers": {
    "browser-use-mcp-server": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

#### cursor

- `./.cursor/mcp.json`

#### windsurf

- `~/.codeium/windsurf/mcp_config.json`

#### claude

- `~/Library/Application Support/Claude/claude_desktop_config.json`
- `%APPDATA%\Claude\claude_desktop_config.json`

then try asking your LLM the following:

`open https://news.ycombinator.com and return the top ranked article`

### help

for issues or interest reach out @ https://cobrowser.xyz

# stars

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=co-browser/browser-use-mcp-server&type=Date" />
</picture>
