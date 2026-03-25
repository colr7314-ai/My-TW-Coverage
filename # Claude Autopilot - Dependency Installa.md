# Claude Autopilot - Dependency Installation Guide

❌ Claude Code: Missing
WSL Installation Required:
1. Install WSL: wsl --install
2. Restart your computer
3. Install Claude CLI inside WSL
4. Verify: wsl claude --version

WSL is required because the extension uses PTY functionality that requires Unix-like system calls.

❌ Python: Missing
Python Installation (Windows):
1. Download from: https://python.org/downloads
2. During installation, check "Add Python to PATH"
3. Restart VS Code
4. Verify installation: python --version

✅ PTY Wrapper: Ready

✅ ngrok: Not required (external server disabled)


---

**After installing dependencies:**
1. Restart VS Code
2. Run the "Check Dependencies" command again
3. All dependencies should show as available