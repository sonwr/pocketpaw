# 🐾 PocketPaw

> **Hi, I'm PocketPaw! The AI agent that lives on YOUR laptop, not some corporate datacenter.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![UV](https://img.shields.io/badge/uv-package%20manager-blueviolet)](https://docs.astral.sh/uv/)

I'm your self-hosted, cross-platform personal AI agent. You talk to me through **Telegram**, and I do the work on your computer. Unlike those fancy cloud AIs, I run on _your_ machine, respect _your_ privacy, and I'm always here - even on that dusty laptop in your closet.

**No subscription. No cloud lock-in. Just you and me.**

---

## 🎬 What Can I Do?

```
You: "Find all the PDFs in my Downloads and organize them by date"
Me:  *runs commands, moves files around*
Me:  "Done! I moved 23 PDFs into dated folders. Your Downloads is clean now!"

You: "Go to GitHub and star the PocketPaw repo"
Me:  *opens browser, navigates, clicks star*
Me:  "Starred! Thanks for the support 🐾"

You: "What's eating up my disk space?"
Me:  *analyzes filesystem*
Me:  "Found it! You have 47GB of node_modules. Want me to clean them up?"
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔋 **Sleep Mode** | I use near-zero CPU when idle, wake instantly on your message |
| 🔒 **Local-First** | I run on YOUR machine. Your data never leaves your computer |
| 🌐 **Browser Control** | I can browse the web, fill forms, click buttons for you |
| 🧠 **Dual Agent Backend** | Open Interpreter or Claude Code - your choice |
| 🤖 **Multi-LLM** | Ollama (100% local), OpenAI, or Anthropic |
| 📱 **Telegram-First** | Control me from anywhere, no port forwarding needed |
| 🖥️ **Cross-Platform** | macOS, Windows, Linux - I go where you go |
| 🛡️ **Guardian AI** | Built-in safety checks before running dangerous commands |

---

## 🚀 Quick Start

### 1. Install UV (if you don't have it)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Run Me!

```bash
# Clone and run
git clone https://github.com/pocketpaw/pocketpaw.git
cd pocketpaw
uv run pocketpaw
```

That's it! I'll:
1. Set up my environment automatically
2. Open your browser for quick setup
3. Help you connect your Telegram bot
4. Be ready to help!

### One-liner (coming soon)

```bash
uvx pocketpaw
```

---

## 🌐 Browser Superpowers (New!)

I can control a web browser for you! I see pages as a semantic tree and can:

- **Navigate** to any URL
- **Click** buttons and links
- **Type** into forms
- **Scroll** through pages
- **Take screenshots**

```
You: "Log into my GitHub and check my notifications"
Me:  *navigates to GitHub, sees login form*
Me:  "I see the login page. I found: textbox [ref=1], password field [ref=2],
      and Sign In button [ref=3]. Should I proceed?"
```

I use your existing Chrome if you have it - no extra downloads. If you don't have Chrome, I'll download a small browser automatically on first use.

---

## 🤖 Agent Backends

### Open Interpreter (Default)
Works with any LLM. I can run shell commands and Python code.

### Claude Code
Uses Anthropic's computer use. I can see your screen and control GUI apps.

Switch anytime in settings!

---

## ⚙️ Configuration

I store my config in `~/.pocketclaw/config.json`:

```json
{
  "telegram_bot_token": "your-bot-token",
  "allowed_user_id": 123456789,
  "agent_backend": "open_interpreter",
  "llm_provider": "ollama",
  "ollama_model": "llama3.2"
}
```

Or use environment variables:

```bash
export POCKETCLAW_ANTHROPIC_API_KEY="sk-ant-..."
export POCKETCLAW_AGENT_BACKEND="claude_code"
```

---

## 🛠️ Telegram Controls

| Button | What I Do |
|--------|-----------|
| 🟢 **Status** | Show you CPU, RAM, disk, battery info |
| 📁 **Fetch** | Browse and download files from your computer |
| 📸 **Screenshot** | Capture what's on your screen |
| 🧠 **Agent Mode** | Toggle my autonomous thinking |
| 🛑 **Panic** | Emergency stop - I'll halt immediately |
| ⚙️ **Settings** | Switch my brain (LLM) or capabilities |

---

## 🔐 Security

I take your safety seriously:

- **Single User Lock** — Only YOU can control me
- **File Jail** — I stay within allowed directories
- **Guardian AI** — I check dangerous commands before running them
- **Panic Button** — You can stop me instantly, always
- **Local LLM Option** — Use Ollama and I'll never phone home

---

## 🧑‍💻 Development

Want to make me better? Here's how:

```bash
# Clone
git clone https://github.com/pocketpaw/pocketpaw.git
cd pocketpaw

# Install with dev tools
uv sync --dev

# Run my tests
uv run pytest

# Check my code style
uv run ruff check .
```

---

## 🤝 Join the Pack

- 🐦 Twitter: [@PocketPawAI](https://twitter.com/PocketPawAI)
- 💬 Discord: [Coming Soon]
- 📧 Email: hello@pocketpaw.ai

PRs welcome! Let's build the future of personal AI together.

---

## 📄 License

MIT © PocketPaw Team

---

<p align="center">
  <b>🐾 Made with love for humans who want AI on their own terms 🐾</b>
</p>
