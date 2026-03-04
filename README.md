# VoiceInput

macOS system-wide voice input tool. Double-tap the right Option key to start/stop recording, and the transcribed text is automatically pasted at the current cursor position.

macOS 系统级语音输入工具 — 双击右 Option 键录音，识别后自动粘贴文字到光标处。

## Features

- **System-wide hotkey** — Double-tap right Option key to toggle recording. Works in any app: terminal, browser, editor, chat, etc.
- **Chinese + English** — Powered by [Whisper](https://github.com/openai/whisper). Optimized for Chinese with automatic English term preservation (e.g. "用 React 写一个 component").
- **Fully local** — No API key, no cloud. Audio never leaves your machine.
- **Auto-paste** — Transcription result is copied to clipboard and pasted at cursor via ⌘V.
- **Boot on login** — Optional LaunchAgent for auto-start.

## Requirements

- macOS 12+
- Python 3.8+
- A microphone (built-in / AirPods / external)

## Installation

```bash
git clone https://github.com/netmsglog/voiceinput.git
cd voiceinput
bash setup.sh
```

The setup script creates a Python virtual environment and installs all dependencies.

## macOS Permissions

Before running, grant the following permissions to your **terminal app** (Terminal / iTerm2) in **System Settings → Privacy & Security**:

| Permission | Purpose |
|---|---|
| Accessibility | Simulate ⌘V paste |
| Input Monitoring | Detect right Option key |
| Microphone | Record audio |

> If running via LaunchAgent (auto-start), grant these permissions to `Python.app` inside your Homebrew Python framework instead. See [Auto-start on login](#auto-start-on-login).

## Usage

```bash
./venv/bin/python voiceinput.py
```

1. Place your cursor in any text field
2. **Double-tap right Option** → recording starts (you'll hear a "Tink" sound)
3. Speak (primarily Chinese, English terms are preserved)
4. **Double-tap right Option** → recording stops (you'll hear a "Pop" sound)
5. Wait briefly — transcribed text is pasted at cursor

The Whisper model (~1.5 GB) downloads automatically on first run.

### Options

```
--model {tiny,base,small,medium,large-v3}
    Whisper model size (default: medium)
    tiny/base   — fast, lower accuracy
    small       — balanced
    medium      — recommended for Chinese + English
    large-v3    — best accuracy, slower

--language LANG
    Recognition language (default: zh)
```

Examples:

```bash
# Faster recognition
./venv/bin/python voiceinput.py --model small

# Best accuracy
./venv/bin/python voiceinput.py --model large-v3

# English-only mode
./venv/bin/python voiceinput.py --language en
```

## Auto-start on Login

A `VoiceInput.app` bundle is included so macOS can properly manage permissions for background execution.

**1. Create a LaunchAgent:**

```bash
cat > ~/Library/LaunchAgents/com.voiceinput.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voiceinput</string>
    <key>ProgramArguments</key>
    <array>
        <string>/FULL/PATH/TO/voiceinput/VoiceInput.app/Contents/MacOS/VoiceInput</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
</dict>
</plist>
EOF
```

Replace `/FULL/PATH/TO/voiceinput` with your actual project path.

**2. Load the service:**

```bash
launchctl load ~/Library/LaunchAgents/com.voiceinput.plist
```

**3. Grant permissions to Python.app:**

In **System Settings → Privacy & Security**, add the following path to Accessibility, Input Monitoring, and Microphone:

```
/opt/homebrew/Cellar/python@3.XX/VERSION/Frameworks/Python.framework/Versions/3.XX/Resources/Python.app
```

Find your exact path with:

```bash
python3 -c "import sys; print(sys.base_prefix + '/Resources/Python.app')"
```

### Managing the service

```bash
# Check status
launchctl list | grep voiceinput

# Stop
launchctl unload ~/Library/LaunchAgents/com.voiceinput.plist

# Restart
launchctl unload ~/Library/LaunchAgents/com.voiceinput.plist
launchctl load ~/Library/LaunchAgents/com.voiceinput.plist

# View logs
tail -f /path/to/voiceinput/voiceinput.log
```

## How It Works

1. **Hotkey** — `pynput` listens for global keyboard events and detects a double-tap of the right Option key (within 0.4s)
2. **Recording** — `sounddevice` captures 16kHz mono audio from the default microphone
3. **Transcription** — `faster-whisper` (CTranslate2 backend, int8 quantization) transcribes locally
4. **Paste** — Result is copied via `pbcopy` and pasted via AppleScript (`⌘V`)

## Troubleshooting

**"This process is not trusted"**
→ Grant Accessibility and Input Monitoring permission to the terminal app (or Python.app for LaunchAgent).

**"Error querying device -1"**
→ No microphone found. Check that a mic is connected and Microphone permission is granted.

**Recording works but no text appears**
→ Check that Accessibility permission is granted (needed for ⌘V simulation).

**Model download is slow**
→ First run downloads ~1.5 GB. Use `--model small` (~500 MB) or `--model tiny` (~75 MB) for a smaller download.

## License

MIT
