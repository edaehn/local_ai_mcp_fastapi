# Local AI MCP: stdio + FastAPI + Ollama semantic search

This folder is a **minimal, working** example from the blog post *[Local AI Agents with Cline, Ollama, and MCP](https://daehnhardt.com/blog/2026/06/04/local-ai-agents-cline-ollama-mcp/)*. The same **`find_similar_files`** tool is exposed two ways:

| Mode | How it runs | Typical client |
|------|----------------|-----------------|
| **stdio MCP** | `python mcp_server.py` — the client **spawns** one process and talks over stdin/stdout | **Cline** (built-in `stdio` config), **Claude Desktop** (`claude_desktop_config.json`), **Claude Code** (`claude mcp add --transport stdio …`) |
| **FastAPI + HTTP MCP** | `uvicorn main:app …` — one **long-lived** server | **Claude Code** (`--transport http`), **Claude Desktop** via [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) to SSE |

| Surface (HTTP mode only) | URL / command | Typical client |
|--------|----------------|----------------|
| **Streamable HTTP** (MCP) | `http://127.0.0.1:8765/mcp` | Claude Code (`claude mcp add --transport http …`) |
| **SSE** (MCP, legacy) | `http://127.0.0.1:8765/mcp-sse/sse` | Claude Desktop + `mcp-remote`, or other SSE clients |
| **REST** (optional) | `POST http://127.0.0.1:8765/api/search` | `curl`, quick manual tests |
| **Health** | `GET http://127.0.0.1:8765/health` | Ops / sanity checks |

---

## Why offer both stdio and FastAPI?

**stdio (`mcp_server.py`)** is the original MCP shape: **no listening port**, no separate “start the server” step in daily use — your IDE or Claude Desktop **starts the process when a session needs tools** and tears it down afterward. That keeps local firewalls and mental models simple, matches **Cline’s first-class stdio path**, and matches how **Claude Desktop** expects entries in `claude_desktop_config.json` (`command` + `args`). Each session gets a **fresh process**: clear isolation, easy upgrades (edit the file, reconnect), and predictable cwd if you configure absolute paths.

**FastAPI + HTTP (`main.py`)** pays off when you want a **shared daemon**: one process, `/health`, putting MCP behind reverse proxies / TLS later, or **Claude Code’s `--transport http`** without spawning Python per chat. Choose stdio for “my laptop, one editor”; choose HTTP when “always-on service” or HTTP-native clients matter.

Shared logic lives in **`semantic_core.py`**; tool wiring is **`mcp_tools.py`** so stdio and HTTP stay aligned.

---

## Prerequisites

1. **Python 3.10+**
2. **[Ollama](https://ollama.com)** installed and running locally. See my post [DeepSeek R1 with Ollama](https://daehnhardt.com/blog/2025/01/28/deepseek-with-ollama/) for detailed instructions on Ollama installation and usage.
3. Embedding model (once):

   ```bash
   ollama pull nomic-embed-text
   ```

4. Optional: **Node.js 18+** if you use the `mcp-remote` bridge for Claude Desktop against the HTTP server.

---

## Setup

```bash
cd local_ai_mcp_fastapi
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run tests (no live Ollama daemon; embeddings are mocked via `semantic_core._ollama_embeddings`). Tests are written so **`import semantic_core` succeeds without the `ollama` PyPI package** — useful for minimal CI images. For **`mcp_server.py`**, **`uvicorn`**, or any real embedding call, install everything from `requirements.txt` and keep the Ollama app running.

```bash
pytest tests/ -v
```

---

## Option A — stdio MCP (`mcp_server.py`)

From this directory (with the venv activated):

```bash
python mcp_server.py
```

If you run it **by hand** in a terminal, it will appear to “hang” with no output — that is normal: it is waiting for MCP JSON-RPC on stdin. Real use is under an MCP client.

### Cline (VS Code)

In the MCP panel, add a server with **`type: stdio`**. Point **`command`** at your venv’s Python and **`args`** at the **absolute path** to `mcp_server.py` (so imports resolve no matter which folder is the workspace root):

```json
{
  "mcpServers": {
    "local-doc-search": {
      "type": "stdio",
      "command": "/ABS/PATH/TO/local_ai_mcp_fastapi/.venv/bin/python",
      "args": ["/ABS/PATH/TO/local_ai_mcp_fastapi/mcp_server.py"]
    }
  }
}
```

Replace `/ABS/PATH/TO/local_ai_mcp_fastapi` with the real path on your machine. After saving, reload MCP in Cline and try a prompt that should call **`find_similar_files`**.

### Claude Desktop

Same idea: `command` + `args` in `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Use the **venv interpreter** so `mcp` and `ollama` packages are available:

```json
{
  "mcpServers": {
    "local-doc-search": {
      "command": "/ABS/PATH/TO/local_ai_mcp_fastapi/.venv/bin/python",
      "args": ["/ABS/PATH/TO/local_ai_mcp_fastapi/mcp_server.py"]
    }
  }
}
```

Fully quit and reopen Claude Desktop after editing.

### Claude Code (stdio)

```bash
claude mcp add --transport stdio local-docs -- /ABS/PATH/TO/local_ai_mcp_fastapi/.venv/bin/python /ABS/PATH/TO/local_ai_mcp_fastapi/mcp_server.py
claude mcp list
```

No `uvicorn` required. Remove when finished: `claude mcp remove local-docs`.

---

## Option B — FastAPI + HTTP MCP (`main.py`)

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8765
```

- OpenAPI docs: [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)
- Health: `curl -s http://127.0.0.1:8765/health`

### Quick REST check (no MCP client)

```bash
curl -s http://127.0.0.1:8765/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"database caching","directory":"'$(pwd)'","top_n":3}'
```

The server must be allowed to read `directory`.

### Claude Code — Streamable HTTP

```bash
claude mcp add --transport http local-docs-http http://127.0.0.1:8765/mcp
claude mcp list
```

Remove: `claude mcp remove local-docs-http`.

### Claude Desktop — SSE via `mcp-remote`

1. Start `uvicorn` as above.
2. Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "local-docs-sse": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8765/mcp-sse/sse"]
    }
  }
}
```

3. Fully quit and reopen Claude Desktop.

If `mcp-remote` flags differ in your version, run `npx mcp-remote --help`. For hosted HTTPS + OAuth connectors, see Anthropic’s [remote MCP guide](https://modelcontextprotocol.io/docs/develop/connect-remote-servers).

---

## Security

The **`find_similar_files`** tool can read any **`directory`** the Python process can read. Use **trusted paths** only, especially if anything listens beyond `localhost`.

---

## Project layout

| File | Role |
|------|------|
| `semantic_core.py` | Embeddings + cosine ranking (Ollama `nomic-embed-text`) |
| `mcp_tools.py` | Registers MCP tools on a `FastMCP` instance (shared by stdio and HTTP) |
| `mcp_server.py` | **Stdio** MCP entrypoint (`mcp.run()`) |
| `main.py` | **FastAPI**: Streamable HTTP + SSE mounts, `/api/search`, `/health` |
| `tests/test_semantic_core.py` | Unit tests (mocked `ollama.embeddings`) |
| `requirements.txt`, `pytest.ini` | Dependencies and test config |

---

## Troubleshooting

| Symptom | Check |
|--------|--------|
| Empty search results | `directory` exists and contains `.md` / `.txt` / `.rst` / `.adoc` files |
| stdio server “does nothing” in a terminal | Expected — it speaks MCP on stdin; use an MCP client |
| `ModuleNotFoundError` for `mcp` | Use the **venv** `python` in `command`, not system Python |
| Connection refused (HTTP) | `uvicorn` running on `127.0.0.1:8765` |
| Ollama errors | `ollama list` includes `nomic-embed-text`; `ollama serve` running |
| `the input length exceeds the context length` (500) | Some files are longer than the embedding model allows; this project **truncates** text to `MAX_CHARS_FOR_EMBED` (see `semantic_core.py`) before calling Ollama. Delete `.mcp_embed_cache.json` in the search directory if you upgraded from an older version and still see errors. |
| Claude Code HTTP fails | URL exactly `http://127.0.0.1:8765/mcp` |
| Tools missing in Desktop | Restart Claude after config edits; check logs for `mcp-remote` |

---

## Further reading (blog)

The Jekyll post *Local AI Agents with Cline, Ollama, and MCP* (`_posts/2026-06-04-local-ai-agents-cline-ollama-mcp.md` in the blog repo) walks through the same example and adds context on **MCP directories** (Glama, MCP.so, Cline marketplace), the official **`modelcontextprotocol/servers`** reference repo, what “submitting” your own server usually entails, and a short **For students** note on security vs public listings (`#students-security` in the built HTML).

---

## Licence

Same as the parent blog repository (educational / personal use).

