#!/usr/bin/env python3
"""
VoiceInput - macOS 系统级语音输入工具
双击右 Option 键开始/停止录音，自动转文字并粘贴到当前光标位置。
支持中文（含英文单词/术语混合）。
支持 VAD 自动停止（说完自动停）和 LLM 纠错（本地小模型修正转写文字）。
"""

import argparse
import json
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
VAD_SILENCE_MS = 1500  # default silence duration to auto-stop (ms)

# ── Global State ───────────────────────────────────────────────────

_recording = False
_audio_frames = []
_stream = None
_model = None
_llm_model = None  # (model, tokenizer) tuple for LLM correction
_last_option_time = 0
_lock = threading.Lock()
_busy = False  # True while transcribing, prevents new recordings
_actual_rate = SAMPLE_RATE  # actual sample rate used (may differ from SAMPLE_RATE)
_vad_enabled = True
_vad_silence_ms = VAD_SILENCE_MS
_correction_enabled = True


# ── User Config ───────────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.voiceinput")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "model": "medium",
    "language": "zh",
    "vad": True,
    "vad_silence_ms": 1500,
    "correction": True,
    "correction_model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
}


def load_config():
    """Load user config from ~/.voiceinput/config.json. Create default if missing."""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"  已创建默认配置: {CONFIG_PATH}")
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        # Merge with defaults (user config overrides)
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(user_cfg)
        return cfg
    except Exception as e:
        print(f"  配置文件读取失败，使用默认值: {e}")
        return dict(DEFAULT_CONFIG)


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


# ── LLM Correction ────────────────────────────────────────────────

def load_llm_model(model_name="mlx-community/Qwen2.5-1.5B-Instruct-4bit"):
    """Load MLX LLM model for text correction (Apple Silicon only)."""
    global _llm_model
    if _llm_model is not None:
        return _llm_model

    import platform
    if platform.machine() != "arm64":
        print("  LLM 纠错仅支持 Apple Silicon，已跳过")
        return None

    try:
        os.environ.setdefault("HF_HOME", os.path.expanduser("~/.voiceinput/models"))
        from mlx_lm import load
        print(f"  正在加载 LLM 纠错模型 {model_name}（首次需下载）...")
        model, tokenizer = load(model_name)
        _llm_model = (model, tokenizer)
        print("  LLM 纠错模型加载完成")
        return _llm_model
    except Exception as e:
        print(f"  LLM 纠错模型加载失败，已跳过: {e}")
        return None


def correct_text(text, language="zh"):
    """Use LLM to correct transcription errors. Returns original text on failure."""
    if not _llm_model or not text.strip():
        return text

    try:
        from mlx_lm import generate
        model, tokenizer = _llm_model

        if language == "zh":
            system_prompt = (
                "你是语音转文字的纠错助手。输入是语音识别(ASR)的原始输出，可能包含以下错误：\n"
                "1. 同音/近音字错误（如「流逝」应为「流式」，「权限」误为「全线」）\n"
                "2. 多字、少字、重复字（如「特性性」应为「特性」）\n"
                "3. 英文术语被错误转为中文或拼写错误（如「瑞安特」应为「React」）\n"
                "4. 标点符号缺失或错误\n"
                "规则：根据上下文语义修正错误，保持原意，不要改写或润色。直接输出修正后的文本。"
            )
        else:
            system_prompt = (
                "You are an ASR post-correction assistant. The input is raw speech-to-text output "
                "that may contain: homophone errors, missing/extra/repeated words, "
                "misspelled technical terms, and punctuation issues.\n"
                "Rules: Fix errors based on context. Preserve original meaning. "
                "Do not rephrase or embellish. Output only the corrected text."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        corrected = generate(model, tokenizer, prompt=prompt, max_tokens=len(text) * 3 + 50)
        corrected = corrected.strip()
        if corrected:
            return corrected
    except Exception as e:
        print(f"  LLM 纠错出错: {e}")

    return text


# ── Audio Recording ────────────────────────────────────────────────

def _try_open_device(device, rate):
    """Try to open a device at a given sample rate. Returns True if it works."""
    try:
        s = sd.InputStream(device=device, samplerate=rate, channels=CHANNELS,
                           dtype="float32", blocksize=1024)
        s.close()
        return True
    except Exception:
        return False


def _refresh_devices():
    """Force PortAudio to rescan audio devices (picks up newly connected devices)."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        pass


def _find_input_device():
    """Find a working input device, return (device_index_or_None, sample_rate)."""
    _refresh_devices()
    # Try the system default first
    try:
        info = sd.query_devices(kind="input")
        if info and info["max_input_channels"] > 0:
            if _try_open_device(None, SAMPLE_RATE):
                return None, SAMPLE_RATE
            # Try the device's own default sample rate
            native_rate = int(info["default_samplerate"])
            if native_rate != SAMPLE_RATE and _try_open_device(None, native_rate):
                print(f"  默认设备不支持 {SAMPLE_RATE}Hz，使用 {native_rate}Hz")
                return None, native_rate
    except Exception:
        pass

    # Fall back: scan all devices for one that actually opens
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                if _try_open_device(i, SAMPLE_RATE):
                    print(f"  使用音频设备: {dev['name']}")
                    return i, SAMPLE_RATE
                native_rate = int(dev["default_samplerate"])
                if native_rate != SAMPLE_RATE and _try_open_device(i, native_rate):
                    print(f"  使用音频设备: {dev['name']} ({native_rate}Hz)")
                    return i, native_rate
    except Exception:
        pass

    return None, SAMPLE_RATE


def _audio_callback(indata, frames, time_info, status):
    """sounddevice stream callback — accumulate frames."""
    if _recording:
        _audio_frames.append(indata.copy())


def _vad_monitor(language):
    """Background thread: monitor audio for speech/silence and auto-stop."""
    try:
        from silero_vad_onnx import SileroVAD, CHUNK_SAMPLES
    except Exception as e:
        print(f"  VAD 加载失败: {e}")
        return

    vad = SileroVAD()
    speech_detected = False
    silence_chunks = 0
    # How many consecutive silent chunks = silence threshold
    # Each chunk is 32ms, so 1500ms / 32ms ≈ 47 chunks
    silence_threshold = max(1, _vad_silence_ms // 32)
    speech_prob_threshold = 0.5
    # Buffer for accumulating audio for VAD
    vad_buf = np.array([], dtype=np.float32)
    frame_idx = 0  # track how many frames we've consumed from _audio_frames

    while _recording:
        # Gather new frames since last check
        current_frames = _audio_frames[frame_idx:]
        if not current_frames:
            time.sleep(0.016)  # ~16ms
            continue

        frame_idx += len(current_frames)
        new_audio = np.concatenate(current_frames, axis=0).flatten()

        # Resample to 16kHz if needed for VAD
        if _actual_rate != SAMPLE_RATE:
            ratio = SAMPLE_RATE / _actual_rate
            new_len = int(len(new_audio) * ratio)
            indices = np.linspace(0, len(new_audio) - 1, new_len)
            new_audio = np.interp(indices, np.arange(len(new_audio)), new_audio).astype(np.float32)

        vad_buf = np.concatenate([vad_buf, new_audio])

        # Process complete chunks
        while len(vad_buf) >= CHUNK_SAMPLES and _recording:
            chunk = vad_buf[:CHUNK_SAMPLES]
            vad_buf = vad_buf[CHUNK_SAMPLES:]

            prob = vad(chunk)
            if prob >= speech_prob_threshold:
                speech_detected = True
                silence_chunks = 0
            else:
                if speech_detected:
                    silence_chunks += 1

            if speech_detected and silence_chunks >= silence_threshold:
                print(f"  VAD: 检测到 {_vad_silence_ms}ms 静默，自动停止")
                stop_recording_and_transcribe(language)
                return


def start_recording(language="zh"):
    """Begin capturing audio from the default microphone."""
    global _recording, _audio_frames, _stream, _actual_rate

    with _lock:
        if _recording or _busy:
            return
        try:
            device, rate = _find_input_device()
            _actual_rate = rate
            _recording = True
            _audio_frames = []
            _stream = sd.InputStream(
                device=device,
                samplerate=rate,
                channels=CHANNELS,
                dtype="float32",
                callback=_audio_callback,
            )
            _stream.start()
        except Exception as e:
            _recording = False
            print(f"  无法打开麦克风: {e}")
            notify("语音输入", "无法打开麦克风，请检查权限或连接音频设备")
            return

    play_sound("Tink")
    if _vad_enabled:
        print("  🎤 录音中… (说完自动停止 / 双击右Option手动停止)")
        threading.Thread(target=_vad_monitor, args=(language,), daemon=True).start()
    else:
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
    recorded_rate = _actual_rate

    # Resample to 16kHz if recorded at a different rate (Whisper expects 16kHz)
    if recorded_rate != SAMPLE_RATE:
        duration = len(audio) / recorded_rate
        ratio = SAMPLE_RATE / recorded_rate
        new_len = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_len)
        audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
        print(f"  重采样: {int(recorded_rate)}Hz → {SAMPLE_RATE}Hz")
    else:
        duration = len(audio) / SAMPLE_RATE

    if duration < MIN_DURATION:
        print(f"  录音太短 ({duration:.1f}s)，已忽略")
        _busy = False
        return

    # Check if audio is mostly silent (device might be stale/wrong)
    peak = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio ** 2))
    print(f"  音频时长: {duration:.1f}s  峰值: {peak:.4f}  RMS: {rms:.4f}")

    if peak < 0.005:
        print("  音频几乎无声，可能麦克风未正确连接")
        notify("语音输入", "录音无声，请检查麦克风连接")
        _busy = False
        return

    def _do():
        global _busy
        try:
            text = transcribe(audio, language)
            if text:
                if _correction_enabled and _llm_model:
                    print(f"  原文: {text}")
                    text = correct_text(text, language)
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
                start_recording(language)
        else:
            _last_option_time = now

    return on_press


# ── Entry Point ────────────────────────────────────────────────────

def main():
    global _vad_enabled, _vad_silence_ms, _correction_enabled

    cfg = load_config()

    parser = argparse.ArgumentParser(description="macOS 系统级语音输入工具")
    parser.add_argument(
        "--model",
        default=None,
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper 模型大小 (配置默认: %(default)s)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="识别语言 (配置默认: %(default)s)",
    )
    parser.add_argument(
        "--no-vad",
        action="store_true",
        default=None,
        help="禁用 VAD 自动停止（回到手动双击停止）",
    )
    parser.add_argument(
        "--vad-silence-ms",
        type=int,
        default=None,
        help="VAD 静默阈值毫秒数",
    )
    parser.add_argument(
        "--no-correction",
        action="store_true",
        default=None,
        help="禁用 LLM 文本纠错",
    )
    parser.add_argument(
        "--correction-model",
        default=None,
        help="LLM 纠错模型名称",
    )
    args = parser.parse_args()

    # CLI args override config; config overrides defaults
    model_size = args.model or cfg["model"]
    language = args.language or cfg["language"]
    _vad_enabled = cfg["vad"] if args.no_vad is None else (not args.no_vad)
    _vad_silence_ms = args.vad_silence_ms if args.vad_silence_ms is not None else cfg["vad_silence_ms"]
    _correction_enabled = cfg["correction"] if args.no_correction is None else (not args.no_correction)
    correction_model = args.correction_model or cfg["correction_model"]

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║       VoiceInput · 语音输入工具      ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    load_model(model_size)

    if _correction_enabled:
        load_llm_model(correction_model)

    features = []
    if _vad_enabled:
        features.append(f"VAD 自动停止 ({_vad_silence_ms}ms)")
    if _correction_enabled and _llm_model:
        features.append("LLM 纠错")

    print()
    if _vad_enabled:
        print("  就绪！双击右 Option 键 → 开始录音（说完自动停止）")
    else:
        print("  就绪！双击右 Option 键 → 开始/停止录音")
    if features:
        print(f"  已启用: {' | '.join(features)}")
    print("  Ctrl+C → 退出")
    print()

    with keyboard.Listener(on_press=make_on_press(language)) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n  再见！")


if __name__ == "__main__":
    main()
