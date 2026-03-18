"""
VLM Backend for Hailo-10H.

Wraps the Hailo VLM inference pipeline. Falls back to a demo mode
when the Hailo device or hailo_platform is not available.

Uses threading (not multiprocessing) to avoid fork-related issues
with Hailo's C library and /dev/hailo0 device handles.
"""

import time
import logging
import threading
from typing import Optional

import numpy as np
import cv2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing hailo_platform – graceful fallback if not available
# ---------------------------------------------------------------------------
HAILO_AVAILABLE = False
try:
    from hailo_platform import VDevice
    from hailo_platform.genai import VLM
    HAILO_AVAILABLE = True
    logger.info("hailo_platform loaded successfully")
except ImportError as e:
    logger.warning(f"hailo_platform not available: {e}")
    logger.warning("Running in DEMO mode — VLM responses will be simulated")


# ---------------------------------------------------------------------------
# Public Backend class
# ---------------------------------------------------------------------------
class VLMBackend:
    """Manages the Hailo VLM and provides a thread-safe inference API."""

    def __init__(self, hef_path: Optional[str] = None,
                 max_tokens: int = 200, temperature: float = 0.1,
                 seed: int = 42,
                 system_prompt: str = "You are a helpful assistant that analyzes images and answers questions about them."):
        self.hef_path = hef_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        self.system_prompt = system_prompt
        self._lock = threading.Lock()
        self._vlm = None
        self._vdevice = None

        # Initialise the Hailo device and model in the main thread
        self._init_model()

    def _init_model(self):
        """Load the VLM model on the Hailo device."""
        if not HAILO_AVAILABLE:
            logger.info("Running in demo mode (hailo_platform not installed)")
            return
        if not self.hef_path:
            logger.warning("No HEF path — running in demo mode")
            return

        try:
            logger.info(f"Loading VLM model: {self.hef_path}")
            params = VDevice.create_params()
            self._vdevice = VDevice(params)
            self._vlm = VLM(self._vdevice, self.hef_path)
            logger.info("VLM model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load VLM model: {e}")
            self._vlm = None
            self._vdevice = None

    def infer(self, image: np.ndarray, user_prompt: str,
              timeout: int = 120) -> dict:
        """Run VLM inference (thread-safe via lock)."""
        processed = self._prepare_image(image)
        logger.info(f"Starting inference, image shape: {processed.shape}")

        # Run inference in a thread so we can enforce a timeout
        result = [None]
        error = [None]

        def _do_inference():
            try:
                result[0] = self._run_inference(processed, user_prompt)
            except Exception as e:
                logger.error(f"Inference error: {e}", exc_info=True)
                error[0] = str(e)

        t = threading.Thread(target=_do_inference, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            logger.error(f"Inference timed out after {timeout}s")
            return {"answer": f"Timeout after {timeout}s — the model may be stuck. Try restarting the add-on.", "time": f"{timeout}s+"}
        if error[0]:
            return {"answer": f"Error: {error[0]}", "time": "error"}
        return result[0] or {"answer": "No response from model", "time": "error"}

    def _run_inference(self, image: np.ndarray, user_prompt: str) -> dict:
        """Execute a single inference (real or simulated)."""
        start = time.time()

        with self._lock:
            if self._vlm is None:
                # Demo mode
                time.sleep(1.5)
                answer = (
                    "[DEMO MODE] This is a simulated response. "
                    "Install and configure HailoRT + a VLM HEF model to get "
                    "real AI-powered image analysis. The image appears to contain "
                    "various objects and visual elements."
                )
                return {"answer": answer, "time": f"{time.time() - start:.2f}s"}

            logger.info("Sending prompt to VLM...")
            prompt = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": self.system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ]

            response_text = ""
            try:
                with self._vlm.generate(
                    prompt=prompt, frames=[image],
                    temperature=self.temperature, seed=self.seed,
                    max_generated_tokens=self.max_tokens,
                ) as generation:
                    for chunk in generation:
                        if chunk != "<|im_end|>":
                            response_text += chunk
                            logger.debug(f"Chunk: {chunk}")

                self._vlm.clear_context()
            except Exception as e:
                logger.error(f"VLM generate error: {e}", exc_info=True)
                return {"answer": f"VLM error: {e}", "time": f"{time.time() - start:.2f}s"}

        elapsed = time.time() - start
        answer = response_text.replace("<|im_end|>", "").strip()
        logger.info(f"Inference complete in {elapsed:.2f}s, {len(answer)} chars")
        return {"answer": answer, "time": f"{elapsed:.2f}s"}

    def close(self):
        try:
            if self._vlm:
                self._vlm.release()
            if self._vdevice:
                self._vdevice.release()
        except Exception:
            pass

    @staticmethod
    def _prepare_image(img: np.ndarray,
                       target: tuple = (336, 336)) -> np.ndarray:
        """Central crop + resize to target, convert BGR→RGB."""
        h, w = img.shape[:2]
        side = min(h, w)
        y0 = (h - side) // 2
        x0 = (w - side) // 2
        cropped = img[y0:y0 + side, x0:x0 + side]
        resized = cv2.resize(cropped, target, interpolation=cv2.INTER_LINEAR)
        if len(resized.shape) == 3 and resized.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return resized.astype(np.uint8)
