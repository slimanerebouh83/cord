# 🚀 CORD CLI — Autonomous Software Engineering & Computer-Use Agent

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/Tests-173%20Passing-brightgreen.svg" alt="Tests" />
  <img src="https://img.shields.io/badge/Status-Alpha%20%2F%20WIP-orange.svg" alt="Status" />
  <img src="https://img.shields.io/badge/Swarm-Peer--to--Peer%20Mesh-purple.svg" alt="Swarm Mesh" />
</p>

> **English & العربية**
> An advanced terminal-native autonomous coding assistant, multi-agent peer swarm, and computer-use intelligence inspired by Claude Code, OpenAI Codex, and OpenCode Interpreter.
>
> وكيل برمجي مستقل وذكي يعمل من سطر الأوامر مباشرة، يدعم شبكة الوكلاء المتكافئين (السوارم)، التحكم بالكمبيوتر، التفكير العميق، والتحقق الذاتي من الأكواد.

---

## ⚠️ Alpha Warning & Active Development Notice (تنبيه الشفافية والتطوير)

> [!WARNING]
> **This project is currently under active alpha development and contains known bugs, rough edges, and evolving features!**
>
> ⚠️ **تنبيه:** هذا المشروع حالياً في مرحلة **التطوير الأولي (Alpha)**، ويحتوي على أخطاء برمجية ونقاط قيد التحسين والتطوير المستمر. على الرغم من اجتياز **173 اختباراً آلياً (Unit & Integration Tests)**، إلا أن بعض الميزات قد تواجه سلوكاً غير متوقع في بيئات معينة. نرحب بشدة بالمساهمات، وبلاغات الأخطاء (*Issues*)، وطلبات الدمج (*Pull Requests*)!

---

## 🌟 Key Highlights & Standout Features (أبرز المزايا والقدرات)

### 1. 🤖 Peer Swarm Mesh Architecture (شبكة الوكلاء المتكافئين — كلهم سواسية)
* **Equal Peers on Mesh**: The main orchestrator and spawned subagents operate as equal peers on a shared pub/sub swarm message bus (`swarm_bus`), sharing plans, insights, and telemetry without rigid central bottlenecks.
* **Specialized Agent Roles**: Dynamic creation of specialized agents:
  - 💻 `Coder`: Implements features, refactors architecture, writes tests.
  - 🔍 `Researcher`: Explores codebases, documentation, and web sources.
  - 🛡️ `Reviewer`: Security audits, memory safety, vulnerability triage.
  - 🧪 `Tester`: Unit test generation, regression tracking.
  - 📐 `Architect`: High-level system design and decomposition.
  - ⚙️ `Custom`: User-defined custom personas with isolated prompts and toolsets.

### 2. 🖱️ Interactive Mouse-Clickable Dashboard & Observation Deck
* **Full Mouse & Keyboard TUI**: Built with `prompt_toolkit` and `rich`, allowing direct mouse clicking on subagent rows, buttons, and navigation tabs.
* **Dedicated Observation Deck (`open_subagent_monitor`)**:
  - **Live Tabs**:
    - `📜 1. Activity Stream`: Chronological transcript of tasks and execution milestones.
    - `🧠 2. Thoughts & Reasoning`: Real-time streaming of internal `<thought>` chains.
    - `🛠️ 3. Tool Executions`: Detailed audit log of invoked tools, arguments, and return codes.
    - `💬 4. Swarm Bus`: Live peer-to-peer message exchanges across the swarm.
    - `📊 5. Telemetry & Specs`: Token consumption, latency, memory tokens, and uptime.
  - **Centralized Orchestration**: Direct chatting remains centralized with the Main Agent (**المستخدم يتحدث مع الرئيسي فقط**) — any user directive entered in the observation deck is automatically routed to the Main Agent to coordinate the swarm.

### 3. 🧠 Deep Reasoning & Chain-of-Thought
* **Streaming Thinking Boxes**: Real-time display of the model's inner thoughts inside styled terminal containers.
* **No Auto-Failover Glitches**: Respects your chosen model and performs smart exponential-backoff retries on rate limits (HTTP 429) rather than forcefully switching models.

### 4. 🛠️ Comprehensive Modular Tool Suite (45+ Native Tools)
Organized into decoupled domain packages under `cord/tools/`:
- **Filesystem**: `list_directory`, `read_file`, `write_file`, `edit_file`, `move_file`, `copy_file`, `delete_file`, `search_files`
- **Execution & Shell**: `execute_command` (isolated subprocess execution with timeouts and output capture)
- **Processes**: `start_process`, `stop_process`, `get_processes`
- **System Telemetry**: `get_system_info`, `get_cpu_usage`, `get_memory_usage`, `get_disk_usage`, `clipboard`
- **Network**: `http_request`, `download_file`, `inspect_url`, `fetch_web_page`
- **Git**: `git_status`, `git_diff`, `git_log`, `git_branch`, `git_checkout`, `git_commit`
- **Developer**: `run_tests` (pytest, npm, cargo, go), `run_formatter`, `run_linter`, `install_dependencies`
- **Windows Computer-Use**: `computer_screenshot`, `computer_mouse`, `computer_keyboard`, `computer_window`
- **Swarm & Interactive**: `ask_user`, `create_plan`, `update_plan_step`, `spawn_subagent`, `create_custom_subagent`

### 5. 🖥️ Native Windows Computer-Use & Vision
* **Desktop Automation**: Direct OS interaction via native Windows `user32` APIs and Pillow.
* **Events**: Smooth mouse movements, clicks, double-clicks, drags, mouse wheel scrolling, Unicode keystroke injection (`SendInput`), and system hotkeys.
* **4-Tier Safety Policy**:
  - `OFF`: Automation completely disabled.
  - `READ_ONLY`: Screenshots and window enumeration only.
  - `INTERACTION`: Bounded coordinate verification and mouse/keyboard interaction.
  - `FULL_CONTROL`: Unrestricted autonomous operation.
* **Emergency Kill Switch (`Esc` or `/stop`)**: Instantly halts all mouse, keyboard, and subprocess actions.

### 6. 🌐 Universal Model & Provider Layer
Supports all major commercial and local AI providers:
- **OpenRouter** (DeepSeek V3/R1, Qwen 2.5 Coder, Claude 3.7 Sonnet, Llama 3.3)
- **Google Gemini** (`gemini-2.5-flash`, `gemini-2.0-flash`)
- **OpenAI** (`gpt-4o`, `o3-mini`, `o1`)
- **Anthropic Claude** (`claude-3-7-sonnet`, `claude-3-5-sonnet`)
- **Groq** (Ultra-fast 300+ tok/s inference)
- **DeepSeek Official API**
- **Nvidia NIM** (`nemotron-3-super-120b`, `gpt-oss-20b`)
- **Moonshot / Kimi** (`kimi-k1.5`, `kimi-128k`)
- **Local Ollama** (`ollama run qwen2.5-coder`)
- **Custom Endpoints** (Local vLLM, FastChat, LM Studio, or local API gateways at `http://localhost:8000/v1`)

### 7. 🌍 Multilingual Interface (i18n)
Full internationalization with native Right-to-Left (RTL) support:
- 🇸🇦 Arabic (العربية)
- 🇬🇧 English
- 🇫🇷 French
- 🇪🇸 Spanish
- 🇩🇪 German
- 🇨🇳 Chinese
- 🇯🇵 Japanese
- 🇷🇺 Russian
- 🇹🇷 Turkish

---

## 📦 Installation & Setup (طريقة التثبيت والتشغيل)

### 1. Prerequisites (المتطلبات)
- **Python**: Version 3.10 or higher (Python 3.11+ recommended).
- **OS**: Windows 10/11 (fully supported including Computer-Use), Linux, or macOS.
- **Git**: Installed and available in PATH.

### 2. Clone the Repository (استنساخ المشروع)
```bash
git clone https://github.com/slimanerebouh83/cord.git
cd cord
```

### 3. Create a Virtual Environment (بيئة افتراضية)
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies (تثبيت الحزم)
```bash
pip install -e .
```
Or install directly via pip:
```bash
pip install -r pyproject.toml
```

---

## 🚀 How to Run (طرق التشغيل)

### 1. Launch Interactive REPL (التشغيل التفاعلي)
```bash
# Using the installed command
cord

# Or directly through Python module
python -m cord

# Or using the Windows batch/PowerShell launchers
.\cord.bat
.\cord.ps1
```

On first run, CORD greets you with an **Interactive Onboarding Wizard** to select your interface language, default AI provider, API key, and safety permissions.

### 2. Run Direct Autonomous Goals (أمر مباشر)
```bash
cord agent "Create a complete FastAPI authentication service with SQLite and pytest"
# Or short flag:
cord -g "Find all failing unit tests, diagnose the root cause, and fix them"
```

### 3. Run System Health Doctor
```bash
cord doctor
```

### 4. Inspect Available Models & Tools
```bash
cord models
cord tools
```

---

## ⌨️ Essential Keybindings & Shortcuts (اختصارات لوحة المفاتيح)

| Shortcut | Action | الوظيفة |
|---|---|---|
| **`F2`** or **`Ctrl + A`** | Open Swarm Monitor Dashboard | فتح لوحة تحكم وكلاء السوارم التفاعلية |
| **`Ctrl + T`** | Quick Models Switcher | التبديل السريع بين النماذج المحفوظة |
| **`Ctrl + P`** | Action Menu | القائمة التفاعلية الرئيسية |
| **`Ctrl + S`** | Terminal Split View | تقسيم نافذة الطرفية |
| **`Alt + Enter`** | Insert Newline (Multiline prompt) | سطر جديد في كتابة الأوامر الطويلة |
| **`Esc`** | Emergency Interrupt / Kill switch | إيقاف فوري للعمليات الجارية |

---

## 🧭 Slash Commands Reference (أوامر سطر الأوامر)

Inside the interactive chat prompt:

| Slash Command | Description | الوصف |
|---|---|---|
| `/agents` or `/swarm` | Open mouse-clickable subagent dashboard | فتح لوحة السوارم التفاعلية بالماوس |
| `/inspect <name>` | Open Live Observation Deck for a subagent | فتح شاشة المراقبة المباشرة لوكيل محدد |
| `/provider <name>` | Quick switch AI provider (`openrouter`, `gemini`, etc.) | التبديل السريع لمزود الذكاء الاصطناعي |
| `/settings` | Open full interactive configuration menu | فتح قائمة الإعدادات والمفاتيح |
| `/models` | Browse and activate saved AI models | استعراض وتبديل نماذج الذكاء الاصطناعي |
| `/lang <ar\|en\|...>` | Switch interface language | تغيير لغة الواجهة فوراً |
| `/thinking <stream\|off>` | Toggle live thinking/reasoning display | تشغيل أو إيقاف استعراض التفكير المباشر |
| `/tools` | Inspect all 45+ registered tools and schemas | استعراض قائمة الأدوات ومعاملاتها |
| `/tasks` | Render hierarchical task tree status | عرض شجرة المهام ونسب الإنجاز |
| `/undo` | Revert the last file modification made by CORD | التراجع الفوري عن آخر تعديل في الملفات |
| `/compact` | Compact conversation history to save tokens | ضغط سياق المحادثة لتوفير الذاكرة |
| `/yolo` | Switch to YOLO permission mode (Autonomous) | تفعيل وضع التنفيذ الذاتي الكامل |
| `/exit` or `/quit` | Exit CORD CLI | الخروج من البرنامج |

---

## 🧪 Testing & Verification (الاختبارات الآلية)

CORD is rigorously tested with automated unit and integration tests covering the agent loop, thinking box closers, mouse-enabled TUI, peer swarm messaging, permissions guard, and tool execution:

```bash
pytest -v
```

```
============================ 173 passed in 33.00s =============================
```

All **173 tests** pass consistently!

---

## 🤝 Contributing (المساهمة في المشروع)

Contributions, bug reports, ideas, and feature requests are very welcome!
1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License (رخصة المشروع)

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with passion for autonomous software engineering. 🚀</b><br>
  <i>صُمم بشغف لتمكين البرمجة الذاتية وهندسة البرمجيات المستقلة.</i>
</p>
