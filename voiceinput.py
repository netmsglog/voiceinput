#!/usr/bin/env python3
"""
VoiceInput - macOS 系统级语音输入工具
双击右 Option 键开始/停止录音，自动转文字并粘贴到当前光标位置。
支持中文（含英文单词/术语混合）。
"""

import argparse
import os
import sys
import time
import threading
import tempfile
import subprocess
import wave

import numpy as np
import sounddevice as sd
from pynput import keyboard
from pynput.keyboard import Key

# ── Configuration ──────────────────────────────────────────────────

DOUBLE_TAP_INTERVAL = 0.4  # seconds between taps to count as double-tap
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_DURATION = 0.5  # ignore recordings shorter than this

# ── Global State ───────────────────────────────────────────────────

_recording = False
_audio_frames = []
_stream = None
_model = None
_last_option_time = 0
_lock = threading.Lock()
_busy = False  # True while transcribing, prevents new recordings


# ── Helpers ────────────────────────────────────────────────────────

def play_sound(name):
    """Play a macOS system sound asynchronously."""
    path = f"/System/Library/Sounds/{name}.aiff"
    if os.path.exists(path):
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def notify(title, message):
    """Show a macOS notification."""
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.Popen(
        [
            "osascript", "-e",
            f'display notification "{escaped}" with title "{title}"',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def paste_text(text):
    """Copy text to clipboard, then simulate ⌘V to paste at cursor."""
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-8"))
    time.sleep(0.05)
    subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ── Model ──────────────────────────────────────────────────────────

def load_model(model_size="medium"):
    """Load the Whisper model (downloads on first run)."""
    global _model
    if _model is not None:
        return _model

    from faster_whisper import WhisperModel

    print(f"  正在加载 Whisper {model_size} 模型（首次需下载）...")
    _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("  模型加载完成")
    return _model


# ── Audio Recording ────────────────────────────────────────────────

def _find_input_device():
    """Find a working input device, return its index or None for default."""
    # Try the system default first
    try:
        info = sd.query_devices(kind="input")
        if info and info["max_input_channels"] > 0:
            return None  # default works
    except Exception:
        pass

    # Fall back: scan all devices for one with input channels
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                print(f"  使用音频设备: {dev['name']}")
                return i
    except Exception:
        pass

    return None


def _audio_callback(indata, frames, time_info, status):
    """sounddevice stream callback — accumulate frames."""
    if _recording:
        _audio_frames.append(indata.copy())


def start_recording():
    """Begin capturing audio from the default microphone."""
    global _recording, _audio_frames, _stream

    with _lock:
        if _recording or _busy:
            return
        try:
            device = _find_input_device()
            _recording = True
            _audio_frames = []
            _stream = sd.InputStream(
                device=device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=_audio_callback,
            )
            _stream.start()
        except Exception as e:
            _recording = False
            print(f"  无法打开麦克风: {e}")
            notify("语音输入", "无法打开麦克风，请检查权限")
            return

    play_sound("Tink")
    print("  🎤 录音中… (双击右Option停止)")


def stop_recording_and_transcribe(language):
    """Stop recording, then transcribe in a background thread."""
    global _recording, _stream, _busy

    with _lock:
        if not _recording:
            return
        _recording = False
        _busy = True
        if _stream:
            _stream.stop()
            _stream.close()
            _stream = None
        frames = list(_audio_frames)

    play_sound("Pop")
    print("  ⏹  录音结束，识别中…")

    if not frames:
        print("  没有录到音频")
        _busy = False
        return

    audio = np.concatenate(frames, axis=0).flatten()
    duration = len(audio) / SAMPLE_RATE

    if duration < MIN_DURATION:
        print(f"  录音太短 ({duration:.1f}s)，已忽略")
        _busy = False
        return

    print(f"  音频时长: {duration:.1f}s")

    def _do():
        global _busy
        try:
            text = transcribe(audio, language)
            if text:
                print(f"  >>> {text}")
                paste_text(text)
                notify("语音输入", text[:80])
            else:
                print("  未识别到有效文字")
                notify("语音输入", "未识别到有效文字")
        except Exception as e:
            print(f"  识别出错: {e}")
            notify("语音输入", f"出错: {str(e)[:60]}")
        finally:
            _busy = False

    threading.Thread(target=_do, daemon=True).start()


# ── Transcription ──────────────────────────────────────────────────

def transcribe(audio_data, language="zh"):
    """Transcribe float32 audio array → text string."""
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(SAMPLE_RATE)
            pcm = (audio_data * 32767).astype(np.int16)
            wf.writeframes(pcm.tobytes())

        segments, _info = _model.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        return "".join(s.text for s in segments).strip()
    finally:
        os.close(fd)
        os.unlink(tmp_path)


# ── Hotkey Detection ───────────────────────────────────────────────

def make_on_press(language):
    """Return a key-press handler that detects double-tap right Option."""

    def on_press(key):
        global _last_option_time

        # Detect right Option key
        is_right_opt = key == Key.alt_r

        if not is_right_opt:
            return

        now = time.time()
        if now - _last_option_time < DOUBLE_TAP_INTERVAL:
            _last_option_time = 0
            if _recording:
                stop_recording_and_transcribe(language)
            else:
                start_recording()
        else:
            _last_option_time = now

    return on_press


# ── Entry Point ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="macOS 系统级语音输入工具")
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper 模型大小 (默认: medium)",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="识别语言 (默认: zh, 中英混合)",
    )
    args = parser.parse_args()

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║       VoiceInput · 语音输入工具      ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    load_model(args.model)

    print()
    print("  就绪！双击右 Option 键 → 开始/停止录音")
    print("  Ctrl+C → 退出")
    print()

    with keyboard.Listener(on_press=make_on_press(args.language)) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n  再见！")


if __name__ == "__main__":
    main()
