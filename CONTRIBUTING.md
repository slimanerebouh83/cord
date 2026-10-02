# 🤝 Contributing to CORD

Welcome to the CORD developer community! CORD is an autonomous, open-source terminal coding agent engineered for speed, swarm deliberation, and zero-regression software engineering.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/slimanerebouh83/cord.git
   cd cord
   ```

2. **Create and Activate Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install in Editable Mode with Test Tools:**
   ```bash
   pip install -e .
   pip install pytest pytest-asyncio rich httpx
   ```

4. **Verify the Test Suite:**
   ```bash
   pytest tests/ -v
   ```
   All 202+ tests should pass cleanly!

---

## 🧭 Architectural Principles

1. **Zero Regressions:** Never break existing features. Always use `cord impact <target>` to inspect the AST blast radius before making surgical edits.
2. **Multi-Agent Deliberation:** Complex architectural proposals go through the **Autonomous Sentinel Council** (`cord sentinel triage "<title>"`).
3. **Pluggable Tools & MCP:** Any new capability should be implemented as an atomic tool adhering to `BaseTool` or published as a community MCP server via `cord radar`.

---

## 📜 Pull Request Process

1. Create a descriptive branch: `git checkout -b feature/awesome-feature`
2. Commit with semantic commit messages: `feat(swarm): add ...` or `fix(llm): resolve ...`
3. Push to your fork and submit a Pull Request.
4. The GitHub Actions CI/CD matrix will automatically verify your code across Python 3.10, 3.11, 3.12 on Linux and Windows!
