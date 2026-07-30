# Langshark

```

▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓▓▒▒▓▓▒▓░▒▒▓░▓▓▒▒░▓░▒▓▒░▓▒▓▓▒▒▒▓▓▒▓░▓░▓▓▓▓▒░▓▒▒▓▒▒▓▒▒▒▒▓▓░░▒░░▓▒▒▓░▓░▓
░▓░▓░▒░▓▓▓▒▒▓▓░▒▒▒▓░▓▓▓▒▓░▓▒▓▓▓▓░▓▓░▓▓▓▓▓▒▒▓▒▓░▒▓▒▒▒░▒▓▓▓▓▓▒░░▓░▒▒░░▓▒
▓▒▒▒░▓░▓▒▓▒▒▓▒▒▓▓░▒▓░░░░▓▒░▓▓░▓▓▓▓░▓▒░░▓▓██▓▓▓▓░▒▒▒▓▒▓▒▒▓▓▓▓▒▒▒▒▓▒░▓░▓
▒▓▓░▒▓▓░▓▒░▒░░▓░▒▒▓▓▓▓▓▒▓▒▓▓░▓▓░▒▓▓▓▒░░████▓▒▓▓▓░▓▒▒▓▒▓▒▓▒▒▒░▒▒▓▓▓░▒▓▒
▒▓░▓▒▒▓▒▓▓░▓▓▒▓░▓▒▓▒▓▓▒▓▓▓▓▓▓▓▓▓▓▓▓░▓▓██████▓▓▓▓▓▒▓▓▓▒▒▓▓▓▒░▒▒▓▓▓▓▓▒▓░
▓▒░▓▒▓▒░▓░▒▓░▒▓░░▒░▓▓░▓▓░▓▓░░▒▓▒▒▓░░█████████░▓▓░▒▓░▒░▒▓▓░▒░▓▒▓▓▓░▓▓▓▓
▓▒░░░▒▒░▓▒▓░▓▓▓▒▓▒▒▓▓▓░░▓░▒▒░░▓▒░▓▓░░▒▒▓▒▒▓▓▒░▒▓▒░░░▒░░▒░░▓▓▓▒▓▓░▒░▒▓▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

                          L A N G S H A R K
               A friendly LangGraph inspector — v0.1.3

```

A friendly TUI for inspecting [LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence) [threads](https://docs.langchain.com/oss/python/langgraph/persistence#threads) and [checkpoints](https://docs.langchain.com/oss/python/langgraph/checkpointers).

## Quick reference

- **Source repository**: [github.com/stokomax/langshark](https://github.com/stokomax/langshark)
- **Supported tags**: `latest`, `0.1`, `0.1.3` (see [full tag list](https://hub.docker.com/r/martinstokoe43/langshark/tags))
- **License**: [MIT](https://github.com/stokomax/langshark/blob/main/LICENSE)

## Features

- Connect to a running LangGraph server — a local
  [`langgraph dev`](https://docs.langchain.com/oss/python/langgraph/local-server)
  instance or a [self-hosted
  deployment](https://docs.langchain.com/langsmith/deploy-standalone-server)
- Browse [LangGraph threads](https://docs.langchain.com/oss/python/langgraph/persistence#threads), [checkpoint](https://docs.langchain.com/oss/python/langgraph/checkpointers) history and LLM calls.
- Inspect individual checkpoint state/values
- One-key copy (`c`) of any thread or checkpoint as formatted JSON
- Server stats screen (`s`) — connection info, queue depth, and worker
  pool metrics at a glance
- Optional [Arize Phoenix](https://arizeai.github.io/phoenix) deep-linking
- Keyboard-driven navigation

## Usage

### Pull the image

```bash
docker pull martinstokoe43/langshark:latest
```

### TUI mode (interactive terminal)

```bash
# Show CLI help
docker run --rm martinstokoe43/langshark --help

# Connect to a LangGraph dev server (default port 2024)
docker run -it --rm --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark -c http://host.docker.internal:2024

# Connect to a self-hosted LangGraph server (default port 8123)
docker run -it --rm --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark -c http://host.docker.internal:8123

# With optional filters
docker run -it --rm --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark -c http://host.docker.internal:2024 --graph supervisor --status idle

# Phoenix trace deep-linking (requires OpenInference instrumentation)
docker run -it --rm --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark -c http://host.docker.internal:2024 --phoenix http://localhost:6006
```

### Web UI mode (browser)

```bash
# Launch web UI on port 8000 — open http://localhost:8000
docker run -it --rm -p 8000:8000 \
  --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark web "-c http://host.docker.internal:8123"

# Custom host port (e.g. 8000 is already in use)
docker run -it --rm -p 8001:8000 \
  -e PUBLIC_URL=http://localhost:8001 \
  --add-host host.docker.internal:host-gateway \
  martinstokoe43/langshark web "-c http://host.docker.internal:8123"
# Then open http://localhost:8001
```

> **Note:** `--rm` removes the container when you quit. `-it` allocates a TTY
> (required for the TUI). `--add-host host.docker.internal:host-gateway` lets
> the container reach a LangGraph server running on the host (required on
> Linux/WSL2 where `host.docker.internal` does not resolve by default).
>
> For the web UI, `PUBLIC_URL` must match the address you type into the
> browser — the served page builds its websocket URL from it. It defaults
> to `http://localhost:8000`.

### Docker aliases (copy-paste into your shell config)

**Bash / Zsh** (Linux, macOS, WSL — add to `~/.bashrc` or `~/.zshrc`):
```bash
alias langshark-tui='docker run -it --rm --add-host host.docker.internal:host-gateway martinstokoe43/langshark'
alias langshark-web='docker run -it --rm -p 8000:8000 --add-host host.docker.internal:host-gateway martinstokoe43/langshark web'
alias langshark-web-alt='docker run -it --rm -p 8001:8000 -e PUBLIC_URL=http://localhost:8001 --add-host host.docker.internal:host-gateway martinstokoe43/langshark web'
```

**PowerShell** (add to `$PROFILE`):
```powershell
function langshark-tui { docker run -it --rm martinstokoe43/langshark @args }
function langshark-web { docker run -it --rm -p 8000:8000 martinstokoe43/langshark web @args }
function langshark-web-alt { docker run -it --rm -p 8001:8000 -e PUBLIC_URL=http://localhost:8001 martinstokoe43/langshark web @args }
```

**CMD** (paste into a terminal session or `.bat` file):
```cmd
doskey langshark-tui=docker run -it --rm martinstokoe43/langshark $*
doskey langshark-web=docker run -it --rm -p 8000:8000 martinstokoe43/langshark web $*
doskey langshark-web-alt=docker run -it --rm -p 8001:8000 -e PUBLIC_URL=http://localhost:8001 martinstokoe43/langshark web $*
```

Usage (same across all shells):
```bash
langshark-tui -c http://host.docker.internal:8123
langshark-web "-c http://host.docker.internal:8123"        # open http://localhost:8000
langshark-web-alt "-c http://host.docker.internal:8123"    # open http://localhost:8001
```

> **Note:** The Bash/Zsh aliases include `--add-host host.docker.internal:host-gateway`
> because `host.docker.internal` does not resolve automatically on Linux/WSL2.
> PowerShell and CMD omit it — Docker Desktop for Windows provides the
> resolution automatically.
