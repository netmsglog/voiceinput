#!/bin/bash
set -e
cd "$(dirname "$0")"

echo
echo "  ══════════════════════════════════════"
echo "    VoiceInput 语音输入工具 · 安装"
echo "  ══════════════════════════════════════"
echo

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  ❌ 需要 Python 3.8+，请先安装"
    echo "     brew install python"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PY_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "  创建虚拟环境..."
    python3 -m venv venv
fi

echo "  安装依赖..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q

echo
echo "  ✅ 安装完成！"
echo
echo "  ── 运行 ──────────────────────────────"
echo "  ./venv/bin/python voiceinput.py"
echo
echo "  ── 配置 ──────────────────────────────"
echo "  首次运行会自动创建 ~/.voiceinput/config.json"
echo "  编辑该文件可自定义:"
echo "    - model: Whisper 模型大小 (tiny/base/small/medium/large-v3)"
echo "    - language: 识别语言 (zh/en/...)"
echo "    - vad: 是否启用 VAD 自动停止 (true/false)"
echo "    - vad_silence_ms: 静默阈值毫秒数"
echo "    - correction: 是否启用 LLM 纠错 (true/false)"
echo "    - correction_model: LLM 纠错模型名称"
echo
echo "  ── 首次运行须知 ──────────────────────"
echo "  系统设置 → 隐私与安全性 中授予终端应用以下权限:"
echo "    1. 辅助功能 (Accessibility)"
echo "    2. 输入监控 (Input Monitoring)"
echo "    3. 麦克风   (Microphone)"
echo
echo "  模型会在首次运行时自动下载 (Whisper ~1.5GB, LLM ~900MB)"
echo
