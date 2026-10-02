# ⚡ CORD CLI — The Autonomous AI Software Engineer & Swarm Mesh

<p align="center">
  <img src="https://img.shields.io/badge/Release-v1.4.0-blue.svg" alt="Release: v1.4.0" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg" alt="Python Versions" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/Tests-207%20Passing%20(100%25)-brightgreen.svg" alt="Tests" />
  <img src="https://img.shields.io/badge/Swarm-10k%2B%20Virtual%20Mesh-purple.svg" alt="Swarm Mesh" />
  <img src="https://img.shields.io/badge/i18n-العربية%20%26%20English-cyan.svg" alt="Multilingual" />
</p>

> **English & العربية**
> An ultra-advanced terminal-native autonomous coding agent, deliberative multi-agent swarm, self-healing tool synthesizer, and AST semantic code-graph engine. Built for zero-regression software engineering, desktop automation, and multi-model frontier intelligence.
>
> أقوى وكيل برمجي مستقل يعمل مباشرة من سطر الأوامر (CLI): يدعم شبكة السرب متعددة الوكلاء المتكافئين، التوليد والإصلاح الذاتي للأدوات، تحليل شجرة الكود البرمجي (AST Code Graph)، ومجلس الرقابة التشاركي لإدارة وحل قضايا المجتمع.

---

## 🥊 CORD vs Other AI Coding CLIs (مقارنة CORD بالأدوات الأخرى)

| Capability / Feature | ⚡ CORD CLI | 🤖 Claude Code | 🎯 Cursor | 🛠️ Aider | 🧑‍💻 Devin / OpenHands |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-Agent Deliberation Swarm** | ✅ **10,000+ Mesh with Consensus Voting** | ❌ Single Agent | ❌ Single Model | ❌ Single Turn | ⚠️ Coarse Planner |
| **Self-Creating & Self-Repairing Tools** | ✅ **Live AST Compilation & Live Unit Tests** | ❌ Fixed Tools | ❌ Fixed Tools | ❌ Fixed Tools | ❌ Fixed Tools |
| **AST Semantic Blast Radius Analysis** | ✅ **Live Call-Graph & Test Mapping** | ❌ String Search | ⚠️ Vector Index | ⚠️ Repo Map Only | ❌ File Grep |
| **Autonomous Community Sentinel Council** | ✅ **4-Role RFC Deliberation & Triage** | ❌ None | ❌ None | ❌ None | ❌ None |
| **Frontier Internet Radar & MCP Marketplace** | ✅ **1-Click MCP Config & Model Radar** | ⚠️ MCP Client Only | ❌ None | ❌ None | ⚠️ Manual MCP |
| **Desktop & Computer-Use Automation** | ✅ **NITEE & Kinetic GUI Automation** | ❌ Terminal Only | ❌ IDE Only | ❌ Terminal Only | ⚠️ Browser VM |
| **Time-Travel Checkpoint & Rewind** | ✅ **Automatic AST Snapshots & /rewind** | ⚠️ Git Checkout | ⚠️ Checkpoints | ⚠️ Git Commits | ❌ None |
| **Full Arabic RTL & Multilingual Support** | ✅ **Native RTL Arabic & 9 Languages** | ❌ English Only | ⚠️ English Focused | ❌ English Only | ❌ English Only |
| **Any LLM Provider (OpenRouter, Gemini, Ollama)** | ✅ **50+ Frontier & Local Models** | ❌ Anthropic Only | ⚠️ Proprietary Proxy | ⚠️ LiteLLM | ⚠️ Cloud Sandbox |

---

## 🌟 Standout Innovations (أبرز المزايا والقدرات الثورية)

### 1. 🧬 Self-Creating & Self-Healing Dynamic Tools (الأدوات ذاتية الإنشاء والإصلاح)
CORD does not wait for developers to release new updates when a capability is needed:
- **`create_dynamic_tool`**: The agent dynamically writes Python code, verifies syntax with AST, sandboxes, and hot-registers the new tool into all active agents in milliseconds!
- **`repair_dynamic_tool`**: If a tool hits a runtime exception (`ZeroDivisionError`, `KeyError`, API mutation), CORD automatically records the exception type, analyzes the stack trace, patches the tool code, and runs a live verification test before reactivating it.

### 2. 🧠 AST Semantic Code Graph & Blast Radius Radar (`cord graph` / `cord impact`)
Never break existing codebases again:
- Parses workspace Python source into an in-memory symbol graph: classes, functions, calls, and imports.
- **Blast Radius Analysis**: Before editing any function or file, calculates:
  - Exact call sites and dependent modules.
  - Required regression verification test suites.
  - Risk classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).

### 3. 🛡️ Autonomous Community Sentinel Council (`cord sentinel` / `/sentinel`)
An autonomous maintenance supervisor for GitHub issues, discussions, and feature suggestions:
- Convenes a 4-role multi-agent deliberation council:
  1. 📐 **Lead Architect**: Evaluates modularity, clean architecture, and backwards compatibility.
  2. 🔒 **Security Auditor**: Checks permissions, sandboxing integrity, and attack surface.
  3. ⚡ **Pragmatist / DX Lead**: Ensures real user utility and prevents code bloat.
  4. 🧪 **QA Engineer**: Validates testability and regression mitigation.
- Produces binding consensus decisions with weighted votes, RFC numbers, and actionable implementation plans.

### 4. 📡 Internet Tech Radar & MCP Server Marketplace (`cord radar` / `/radar`)
- **Frontier Intelligence Radar**: Live metrics, SWE-bench scores, and context limits for 2025/2026 models (Claude 3.7 Sonnet with hybrid reasoning, Gemini 2.5 Flash, DeepSeek R1, Qwen 2.5 Coder 32B).
- **1-Click MCP Marketplace**: Auto-configure popular Model Context Protocol servers (`github`, `postgres`, `puppeteer`, `brave-search`, `memory`, `filesystem`, `docker`) into `~/.cord/mcp_servers.json` with a single command:
  ```bash
  cord radar install github
  cord radar install postgres
  ```

### 5. 🐝 10,000+ Swarm Mesh & Collaborative Orchestration Matrix
- Visual execution blueprint displayed before multi-phase goals launch, assigning explicit roles (`CODER`, `RESEARCHER`, `TESTER`, `REVIEWER`).
- Peer Deliberation & Consensus Voting across agents via `swarm_bus`.
- Distinct phase cards with real-time progress indicators.

### 6. 🎨 Ultra-Sleek 1-Line Tool Cards & Docked Blue Prompt Box (`v1.4.0`)
- **Micro-Card Tool Telemetry**: Eliminated vertical panel clutter. Tool invocations (`Read`, `Edit`, `Run`, `Grep`, `Glob`, `Desktop`) now render as crisp, single-line micro-cards with diff line counts (`+12 -3`) and millisecond execution timers.
- **Docked Glowing Blue Prompt Box**: Sticky bottom prompt container with glowing cobalt/cyan accents, placeholder text, and active model telemetry toolbar.

### 7. ⚡ Animated `/about` Command & Live Telemetry (`v1.4.0`)
- Type `/about` (or `cord about`) to trigger a cyber ASCII reveal animation, live system telemetry (Python, OS, active LLM model, Swarm status), full features overview, and official GitHub repository link: [slimanerebouh83/cord](https://github.com/slimanerebouh83/cord).

### 8. 🛡️ Dynamic AI UI Customizer with Immutable App Identity (`v1.4.0`)
- **`customize_ui` Tool**: Enables the agent to dynamically switch themes (`cord_blue`, `cyberpunk`, `nord`, `monokai`, `dracula`), toggle compact display mode, or change interface language on user command.
- **Security Policy Guard**: The application identity and name `CORD` is strictly immutable—any attempt to rename or disguise the application is automatically blocked.

---

## 📦 Quick Installation (طريقة التثبيت والتشغيل)

### 1. Requirements
- Python 3.10+ (Python 3.11 or 3.12 recommended).
- Git installed.

### 2. One-Line Install from Source
```bash
git clone https://github.com/slimanerebouh83/cord.git
cd cord
pip install -e .
```

### 3. Launch CORD
```bash
# Interactive REPL
cord

# Or Windows launchers
.\cord.bat
.\cord.ps1

# Direct Autonomous Goal Execution
cord agent "Build a high-performance REST API with FastAPI, SQLite, and 100% pytest coverage"
```

---

## 🧭 Command & Shortcut Quick Reference

| Command / Shortcut | Description | الوظيفة |
|---|---|---|
| `cord about` / `/about` | Animated system specs, features & GitHub link | عرض مواصفات النظام والمزايا التفاعلية |
| `cord graph` / `/graph` | View AST code graph & module hubs | عرض شجرة الكود والاعتماديات البرمجية |
| `cord impact <target>` / `/impact` | Calculate blast radius & test dependencies | فحص أثر التعديلات والملفات المعتمدة |
| `cord sentinel` / `/sentinel` | Convene Sentinel Council for issue triage | تشغيل مجلس الرقابة لتقييم الاقتراحات |
| `cord radar` / `/radar` | Explore frontier AI models & MCP marketplace | استعراض رادار الذكاء الاصطناعي وخوادم MCP |
| `/rewind` or `/undo` | Time-travel rollback of last file changes | التراجع الفوري عن تعديلات الملفات |
| `/skills` | Browse & manage modular skills library | استعراض وإدارة مكتبة المهارات |
| `/provider <name>` | Quick switch AI provider (`openrouter`, `gemini`) | التبديل السريع لمزود الذكاء الاصطناعي |
| `F2` or `Ctrl + A` | Open Interactive Mouse Swarm Monitor | فتح لوحة تحكم الوكلاء التفاعلية بالماوس |

---

## 🧪 Rigorous Automated Testing (الاختبارات الآلية)

CORD is continuously verified with a multi-OS CI/CD test matrix:

```bash
pytest tests/ -v
```

```text
======================= 207 passed in 35.59s =======================
```
✅ **207 unit and integration tests passing at 100% with zero regressions.**

---

## 🤝 Community & Contributing

We welcome community pull requests, issue reports, and architectural RFCs!
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, testing instructions, and our zero-regression philosophy.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

<p align="center">
  <b>Engineered with passion for autonomous software engineering. 🚀</b><br>
  <i>صُمم بشغف لتمكين البرمجة الذاتية وهندسة البرمجيات المستقلة.</i>
</p>
