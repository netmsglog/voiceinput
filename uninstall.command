#!/bin/bash
# VoiceInput Uninstaller
# Double-click this file in Finder to uninstall.
set -e

clear
echo
echo "  ══════════════════════════════════════"
echo "    VoiceInput · 卸载"
echo "  ══════════════════════════════════════"
echo

INSTALL_DIR="$HOME/.voiceinput"
PLIST_PATH="$HOME/Library/LaunchAgents/com.voiceinput.plist"
LABEL="com.voiceinput"

# ── Confirm ──────────────────────────────────────────────────────
read -p "  确定要卸载 VoiceInput 吗？(y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "  已取消。"
    echo
    read -n 1 -s -r -p "  按任意键关闭..."
    exit 0
fi

echo

# ── Stop and remove LaunchAgent ──────────────────────────────────
if launchctl list "$LABEL" &>/dev/null; then
    echo "  停止服务..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    echo "  ✓ 服务已停止"
fi

if [ -f "$PLIST_PATH" ]; then
    rm -f "$PLIST_PATH"
    echo "  ✓ LaunchAgent 已移除"
fi

# ── Remove install directory ─────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "  ✓ $INSTALL_DIR 已删除"
fi

echo
echo "  ══════════════════════════════════════"
echo "    ✅ VoiceInput 已完全卸载"
echo "  ══════════════════════════════════════"
echo
echo "  你可能还需要手动移除系统设置中的权限授权。"
echo
read -n 1 -s -r -p "  按任意键关闭此窗口..."
