# VoiceInput

macOS system-wide voice input tool. Double-tap the right Option key to start/stop recording, and the transcribed text is automatically pasted at the current cursor position.

macOS 系统级语音输入工具 — 双击右 Option 键录音，识别后自动粘贴文字到光标处。

---

## Features / 功能

- **System-wide hotkey / 全局快捷键** — Double-tap right Option key to toggle recording. Works in any app.
  双击右 Option 键开始/停止录音，任何应用中均可使用。
- **Chinese + English / 中英混合** — Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Handles mixed Chinese-English well (e.g. "用 React 写一个 component").
  基于 faster-whisper，中英混合识别，自动保留英文术语。
- **Fully local / 完全本地** — No API key, no cloud. Audio never leaves your machine.
  无需 API Key，无需联网，音频不出本机。
- **Auto-paste / 自动粘贴** — Transcription result is pasted at cursor via ⌘V.
  识别结果自动复制到剪贴板并粘贴到光标处。
- **Auto-start on login / 开机自启** — Runs as a background service via LaunchAgent.
  通过 LaunchAgent 后台运行，开机自动启动。

## Requirements / 系统要求

- macOS 12+
- Python 3.8+
- Microphone / 麦克风 (built-in / AirPods / external — 内置、AirPods 或外接均可)

---

## Installation / 安装

### One-Click Install / 一键安装 (Recommended / 推荐)

1. Download `VoiceInput-v1.0.0.zip` from [Releases](https://github.com/netmsglog/voiceinput/releases)
   从 [Releases](https://github.com/netmsglog/voiceinput/releases) 下载 `VoiceInput-v1.0.0.zip`
2. Unzip, then **right-click** `install.command` → **Open**
   解压后**右键点击** `install.command` → **打开**
3. Grant permissions when prompted
   按提示授权系统权限
4. Done — service auto-starts on login
   完成 — 服务会开机自动启动

> **macOS security warning / macOS 安全提示**:
> Since VoiceInput is not signed with an Apple Developer certificate, macOS will block it on first launch.
> 由于未经 Apple 开发者签名，macOS 首次会阻止运行。
>
> **Right-click → Open** bypasses this. / **右键 → 打开**即可绕过。
>
> Or run in Terminal / 或在终端运行：
> ```bash
> xattr -cr ~/Downloads/VoiceInput/
> ```

**Uninstall / 卸载**: double-click / 双击 `~/.voiceinput/uninstall.command`

### Manual Install / 手动安装 (from source / 从源码)

```bash
git clone https://github.com/netmsglog/voiceinput.git
cd voiceinput
bash setup.sh
```

Creates a Python virtual environment and installs all dependencies.
创建 Python 虚拟环境并安装所有依赖。

---

## macOS Permissions / macOS 权限

Grant the following in **System Settings → Privacy & Security**:
在**系统设置 → 隐私与安全性**中授权以下权限：

| Permission / 权限 | Purpose / 用途 |
|---|---|
| Accessibility / 辅助功能 | Simulate ⌘V paste / 模拟 ⌘V 粘贴 |
| Input Monitoring / 输入监控 | Detect right Option key / 检测右 Option 键 |
| Microphone / 麦克风 | Record audio / 录制音频 |

- **One-click install / 一键安装**: grant to **VoiceInput** or **Python** (the installer will prompt you).
  授权给 **VoiceInput** 或 **Python**（安装器会提示）。
- **Manual install / 手动安装**: grant to your **terminal app** (Terminal / iTerm2).
  授权给你的**终端应用**（Terminal / iTerm2）。

---

## Usage / 使用方法

1. Place your cursor in any text field / 将光标放在任意输入框中
2. **Double-tap right Option** → recording starts ("Tink" sound) / **双击右 Option** → 开始录音（听到"Tink"提示音）
3. Speak / 说话（中文为主，英文术语会自动保留）
4. **Double-tap right Option** → recording stops ("Pop" sound) / **双击右 Option** → 停止录音（听到"Pop"提示音）
5. Wait briefly — text is pasted at cursor / 稍等片刻 — 文字自动粘贴到光标处

The Whisper model (~1.5 GB) downloads automatically on first run.
Whisper 模型（约 1.5GB）会在首次使用时自动下载。

### Options / 可选参数

```
--model {tiny,base,small,medium,large-v3}
    Whisper model size (default: medium)
    模型大小（默认: medium）

    tiny/base   — fast, lower accuracy / 速度快，精度低
    small       — balanced / 均衡
    medium      — recommended for Chinese + English / 推荐，中英混合效果好
    large-v3    — best accuracy, slower / 最高精度，较慢

--language LANG
    Recognition language (default: zh)
    识别语言（默认: zh 中文）
```

Examples / 示例：

```bash
# Faster recognition / 更快识别
./venv/bin/python voiceinput.py --model small

# Best accuracy / 最高精度
./venv/bin/python voiceinput.py --model large-v3

# English-only mode / 纯英文模式
./venv/bin/python voiceinput.py --language en
```

---

## Auto-start on Login / 开机自启（手动安装用户）

> If you used the one-click installer, this is already configured. Skip this section.
> 如果使用了一键安装，此步骤已自动完成，可跳过。

A `VoiceInput.app` bundle is included for macOS to properly manage permissions.
项目自带 `VoiceInput.app`，用于 macOS 正确管理后台权限。

**1. Create LaunchAgent / 创建 LaunchAgent：**

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
将 `/FULL/PATH/TO/voiceinput` 替换为你的实际项目路径。

**2. Load the service / 加载服务：**

```bash
launchctl load ~/Library/LaunchAgents/com.voiceinput.plist
```

**3. Grant permissions to Python.app / 为 Python.app 授权：**

In **System Settings → Privacy & Security**, add the following to Accessibility, Input Monitoring, and Microphone:
在**系统设置 → 隐私与安全性**中，将以下路径添加到辅助功能、输入监控和麦克风：

```
/opt/homebrew/Cellar/python@3.XX/VERSION/Frameworks/Python.framework/Versions/3.XX/Resources/Python.app
```

Find your exact path with / 查找你的实际路径：

```bash
python3 -c "import sys; print(sys.base_prefix + '/Resources/Python.app')"
```

### Managing the service / 管理服务

```bash
# Check status / 查看状态
launchctl list | grep voiceinput

# Stop / 停止
launchctl unload ~/Library/LaunchAgents/com.voiceinput.plist

# Restart / 重启
launchctl unload ~/Library/LaunchAgents/com.voiceinput.plist
launchctl load ~/Library/LaunchAgents/com.voiceinput.plist

# View logs / 查看日志
tail -f ~/.voiceinput/voiceinput.log
```

---

## How It Works / 工作原理

1. **Hotkey / 快捷键** — `pynput` listens for global keyboard events, detects double-tap of right Option key (within 0.4s).
   `pynput` 监听全局键盘事件，检测 0.4 秒内双击右 Option 键。
2. **Recording / 录音** — `sounddevice` captures mono audio from the microphone.
   `sounddevice` 从麦克风采集单声道音频。
3. **Transcription / 转录** — `faster-whisper` (CTranslate2 backend, int8 quantization) transcribes locally.
   `faster-whisper`（CTranslate2 后端，int8 量化）本地转录。
4. **Paste / 粘贴** — Result is copied via `pbcopy` and pasted via AppleScript (⌘V).
   结果通过 `pbcopy` 复制，AppleScript 模拟 ⌘V 粘贴。

---

## Troubleshooting / 常见问题

**"This process is not trusted" / 提示进程不受信任**
→ Grant Accessibility and Input Monitoring permission.
→ 授权辅助功能和输入监控权限。

**"Error querying device -1" / 找不到音频设备**
→ No microphone found. Check that a mic is connected and Microphone permission is granted.
→ 未找到麦克风，检查麦克风是否连接并已授权。

**Recording works but no text appears / 录音正常但文字不出现**
→ Check that Accessibility permission is granted (needed for ⌘V simulation).
→ 检查辅助功能权限是否已授权（用于模拟 ⌘V）。

**Model download is slow / 模型下载慢**
→ First run downloads ~1.5 GB. Use `--model small` (~500 MB) or `--model tiny` (~75 MB) for a smaller download.
→ 首次运行下载约 1.5GB。可用 `--model small`（约 500MB）或 `--model tiny`（约 75MB）减小下载量。

**macOS blocks the installer / macOS 阻止安装器运行**
→ Right-click → Open, or run `xattr -cr` on the unzipped folder. See [Installation](#installation--安装).
→ 右键 → 打开，或对解压文件夹运行 `xattr -cr`。详见[安装](#installation--安装)。

---

## License / 许可证

MIT
