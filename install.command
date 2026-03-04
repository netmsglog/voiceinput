#!/bin/bash
# VoiceInput One-Click Installer
# Double-click this file in Finder to install.
set -e

# ── Ensure we run in the directory where this script lives ────────
cd "$(dirname "$0")"

clear
echo
echo "  ══════════════════════════════════════"
echo "    VoiceInput · 一键安装"
echo "  ══════════════════════════════════════"
echo

# ── Check Python 3.8+ ────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "  ❌ 未找到 Python 3"
    echo
    echo "  请先安装 Python:"
    echo "    方法1: brew install python"
    echo "    方法2: https://www.python.org/downloads/"
    echo
    echo "  安装 Python 后重新双击此文件即可。"
    echo
    read -n 1 -s -r -p "  按任意键退出..."
    exit 1
fi

PY_VER=$(python3 -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
    echo "  ❌ 需要 Python 3.8+，当前版本: $PY_VER"
    echo
    read -n 1 -s -r -p "  按任意键退出..."
    exit 1
fi
echo "  ✓ Python $PY_VER"

# ── Install directory ─────────────────────────────────────────────
INSTALL_DIR="$HOME/.voiceinput"
PLIST_PATH="$HOME/Library/LaunchAgents/com.voiceinput.plist"
LABEL="com.voiceinput"

# Stop existing service if running
if launchctl list "$LABEL" &>/dev/null; then
    echo "  停止已有服务..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
fi

# ── Copy project files ───────────────────────────────────────────
echo "  安装到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"

cp -f voiceinput.py "$INSTALL_DIR/"
cp -f silero_vad_onnx.py "$INSTALL_DIR/"
cp -f requirements.txt "$INSTALL_DIR/"
cp -Rf VoiceInput.app "$INSTALL_DIR/"

# ── Rewrite the .app launcher to use installed paths ─────────────
cat > "$INSTALL_DIR/VoiceInput.app/Contents/MacOS/VoiceInput" << 'LAUNCHER'
#!/bin/bash
DIR="$HOME/.voiceinput"
cd "$DIR"
exec env PYTHONUNBUFFERED=1 "$DIR/venv/bin/python" "$DIR/voiceinput.py" >> "$DIR/voiceinput.log" 2>&1
LAUNCHER
chmod +x "$INSTALL_DIR/VoiceInput.app/Contents/MacOS/VoiceInput"

# ── Create virtual environment + install deps ────────────────────
echo "  创建 Python 虚拟环境..."
python3 -m venv "$INSTALL_DIR/venv"

echo "  安装依赖（首次可能需要几分钟）..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q 2>&1 | tail -1
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q 2>&1 | tail -1
echo "  ✓ 依赖安装完成"

# ── Generate LaunchAgent plist ───────────────────────────────────
echo "  配置开机自启..."
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/VoiceInput.app/Contents/MacOS/VoiceInput</string>
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
echo "  ✓ LaunchAgent 已生成"

# ── Load and start the service ───────────────────────────────────
echo "  启动服务..."
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true
echo "  ✓ 服务已启动（开机自动运行）"

# ── Copy uninstaller next to install location ────────────────────
if [ -f "uninstall.command" ]; then
    cp -f uninstall.command "$INSTALL_DIR/uninstall.command"
    chmod +x "$INSTALL_DIR/uninstall.command"
fi

# ── Prompt for permissions ───────────────────────────────────────
echo
echo "  ══════════════════════════════════════"
echo "    ✅ 安装成功！"
echo "  ══════════════════════════════════════"
echo
echo "  用法: 双击右 Option 键 → 开始录音，说完自动停止"
echo
echo "  📝 自定义配置: 编辑 ~/.voiceinput/config.json"
echo "     可配置: 模型大小、语言、VAD、LLM 纠错等"
echo
echo "  ⚠️  首次使用需要授权三个权限："
echo "     1. 辅助功能 (Accessibility)"
echo "     2. 输入监控 (Input Monitoring)"
echo "     3. 麦克风   (Microphone)"
echo
echo "  正在打开系统设置..."
echo

# Open System Settings to the privacy page
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

# Show a dialog with instructions
osascript -e '
display dialog "VoiceInput 安装成功！

请在「系统设置 → 隐私与安全性」中，为 VoiceInput 授权：
  1. 辅助功能 (Accessibility)
  2. 输入监控 (Input Monitoring)
  3. 麦克风 (Microphone)

授权后即可使用：双击右 Option 键 → 开始录音，说完自动停止。

模型会在首次录音时自动下载（Whisper ~1.5GB, LLM ~900MB）。

自定义配置：编辑 ~/.voiceinput/config.json
卸载方式：运行 ~/.voiceinput/uninstall.command" with title "VoiceInput" buttons {"好的"} default button "好的"
'

echo
echo "  安装日志: $INSTALL_DIR/voiceinput.log"
echo
read -n 1 -s -r -p "  按任意键关闭此窗口..."
