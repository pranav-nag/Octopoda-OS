# Contributing to Octopoda

Thanks for your interest in contributing to Octopoda! We welcome contributions of all kinds.

## Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/RyjoxTechnologies/octopoda.git
cd octopoda
```

### 2. Set up development environment

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### 3. Run tests

```bash
pytest tests/test_sqlite.py tests/test_backend.py tests/test_memory.py tests/test_mcp_server.py -v
```

The cloud API tests (`test_cloud_api.py`) require a running PostgreSQL instance and are skipped locally.

## What to Contribute

### Good first issues
Look for issues labeled `good first issue` on GitHub. These are specifically chosen to be approachable for new contributors.

### Areas we need help with
- **Documentation:** Improving guides, adding examples, fixing typos
- **Examples:** Real-world use cases showing Octopoda in action
- **Framework integrations:** New integrations beyond LangChain, CrewAI, AutoGen, OpenAI Agents
- **Tests:** Improving coverage, edge cases, performance tests
- **Bug fixes:** Check the issue tracker

## Code Style

- We use **Black** for formatting (line length 100)
- Type hints on all public methods
- Docstrings on all public methods
- Keep imports sorted (stdlib, third-party, local)

```bash
black --line-length 100 .
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all tests pass: `pytest -v`
4. Update CHANGELOG.md if applicable
5. Submit a PR with a clear description of what changed and why

### PR checklist
- [ ] Tests pass locally
- [ ] No secrets or credentials in the diff
- [ ] New public methods have docstrings and type hints
- [ ] CHANGELOG.md updated (for user-facing changes)

## Testing

### Running specific test suites
```bash
# Core memory engine
pytest tests/test_sqlite.py -v

# Backend operations
pytest tests/test_backend.py -v

# MCP server
pytest tests/test_mcp_server.py -v

# Framework integrations
pytest tests/test_integrations.py -v

# All local tests
pytest tests/ -v --ignore=tests/test_cloud_api.py --ignore=tests/test_live_api.py
```

## Architecture Overview

```
octopoda/              # Public entry point (pip install octopoda)
synrix/                # Core SDK (client, embeddings, cloud connector)
synrix_runtime/        # Runtime engine
  api/
    runtime.py         # AgentRuntime — the main developer API
    cloud_server.py    # FastAPI cloud server (multi-tenant)
    tenant.py          # Tenant management and isolation
    mcp_server.py      # MCP server for Claude/Cursor
  integrations/        # Framework adapters (LangChain, CrewAI, etc.)
  monitoring/          # Brain system, metrics, audit
  core/                # Daemon, config
tests/                 # Test suite
examples/              # Usage examples
```

## Questions?

Open a GitHub Discussion or reach out at ryjoxtechnologies@gmail.com.
