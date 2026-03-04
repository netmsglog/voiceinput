"""
Lightweight Silero VAD wrapper using ONNX Runtime (no PyTorch dependency).
Downloads silero_vad.onnx (~2MB) on first use to ~/.voiceinput/models/.
"""

import os
import urllib.request

import numpy as np
import onnxruntime

MODEL_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"
MODEL_DIR = os.path.expanduser("~/.voiceinput/models")
MODEL_PATH = os.path.join(MODEL_DIR, "silero_vad.onnx")

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512       # 32ms at 16kHz
CONTEXT_SIZE = 64          # context samples for 16kHz


def _ensure_model():
    """Download the ONNX model if not already cached."""
    if os.path.exists(MODEL_PATH):
        return
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"  下载 silero_vad.onnx 模型...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"  模型已保存到 {MODEL_PATH}")


class SileroVAD:
    """Silero VAD via ONNX Runtime. Call with a 512-sample float32 chunk → speech probability."""

    def __init__(self):
        _ensure_model()
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(
            MODEL_PATH, providers=["CPUExecutionProvider"], sess_options=opts,
        )
        self.reset()

    def reset(self):
        """Reset hidden state and context buffer."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT_SIZE), dtype=np.float32)

    def __call__(self, chunk: np.ndarray) -> float:
        """
        Feed a 512-sample float32 chunk, return speech probability [0, 1].
        """
        if chunk.ndim == 1:
            chunk = chunk[None, :]  # (1, 512)
        # Prepend context
        x = np.concatenate([self._context, chunk], axis=1).astype(np.float32)
        ort_inputs = {
            "input": x,
            "state": self._state,
            "sr": np.array(SAMPLE_RATE, dtype=np.int64),
        }
        out, state = self.session.run(None, ort_inputs)
        self._state = state
        self._context = x[:, -CONTEXT_SIZE:]
        return float(out[0, 0])
