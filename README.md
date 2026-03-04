# VoiceInput

macOS 系统级语音输入工具。双击右 Option 键即可录音，松手后自动识别并粘贴文字到当前光标位置。

适用于终端、编辑器、浏览器、聊天软件等任何可输入文字的地方。

## 特性

- **系统级快捷键** — 双击右 Option 键触发，不与其他快捷键冲突
- **中英混合识别** — 基于 Whisper 模型，中文为主、自动保留英文术语
- **纯本地运行** — 无需 API Key，语音数据不离开本机
- **即粘即用** — 识别结果自动粘贴到当前光标位置

## 系统要求

- macOS 12+
- Python 3.8+
- 麦克风（内置 / AirPods / 外接均可）

## 快速开始

```bash
# 1. 克隆项目
git clone git@github.com:<你的用户名>/voiceinput.git
cd voiceinput

# 2. 安装依赖
bash setup.sh

# 3. 运行
./venv/bin/python voiceinput.py
```

首次运行会自动下载 Whisper medium 模型（约 1.5 GB），之后启动无需网络。

## macOS 权限设置

运行前需在 **系统设置 → 隐私与安全性** 中为终端应用授予以下权限：

| 权限 | 用途 |
|------|------|
| 辅助功能 (Accessibility) | 模拟 ⌘V 粘贴 |
| 输入监控 (Input Monitoring) | 检测双击右 Option |
| 麦克风 (Microphone) | 录音 |

## 使用方法

1. 启动程序后，将光标定位到任意输入位置
2. **双击右 Option 键** → 开始录音（听到提示音）
3. 说话（中文为主，可夹杂英文单词）
4. **再次双击右 Option 键** → 停止录音
5. 等待识别，文字自动粘贴到光标处

## 命令行参数

```
--model {tiny,base,small,medium,large-v3}
    Whisper 模型大小，默认 medium
    tiny/base: 快但精度低
    small:     速度与精度平衡
    medium:    推荐，中英混合效果好
    large-v3:  最高精度，速度较慢

--language LANG
    识别语言，默认 zh（中文）
```

示例：

```bash
# 使用 small 模型（更快）
./venv/bin/python voiceinput.py --model small

# 使用 large 模型（更准）
./venv/bin/python voiceinput.py --model large-v3
```

## 工作原理

1. `pynput` 监听全局键盘事件，检测右 Option 键双击
2. `sounddevice` 从默认麦克风采集 16kHz 单声道音频
3. `faster-whisper`（CTranslate2 后端）本地转写语音为文字
4. 通过 `pbcopy` + AppleScript 模拟 ⌘V 粘贴到当前应用

## License

MIT
