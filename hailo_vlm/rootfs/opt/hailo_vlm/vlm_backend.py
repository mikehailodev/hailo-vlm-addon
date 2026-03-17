"""
VLM Backend for Hailo-10H.

Wraps the Hailo VLM inference pipeline. Falls back to a demo mode
when the Hailo device or hailo_platform is not available.
"""

import time
import logging
import multiprocessing as mp
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
# Worker process (runs VLM inference in a separate process)
# ---------------------------------------------------------------------------
def _vlm_worker(request_q: mp.Queue, response_q: mp.Queue,
                hef_path: Optional[str], max_tokens: int,
                temperature: float, seed: int) -> None:
    """Long-running worker process that owns the Hailo VDevice."""
    try:
        if HAILO_AVAILABLE and hef_path:
            params = VDevice.create_params()
            vdevice = VDevice(params)
            vlm = VLM(vdevice, hef_path)
            logger.info("VLM model loaded in worker process")
        else:
            vlm = None
            vdevice = None
            logger.info("Worker running in demo mode (no Hailo device)")

        while True:
            item = request_q.get()
            if item is None:
                break

            try:
                result = _run_inference(
                    item["image"], item["prompts"],
                    vlm, max_tokens, temperature, seed
                )
                response_q.put({"result": result, "error": None})
            except Exception as e:
                logger.error(f"Inference error: {e}")
                response_q.put({"result": None, "error": str(e)})

    except Exception as e:
        logger.error(f"Worker process error: {e}")
        response_q.put({"result": None, "error": str(e)})
    finally:
        try:
            if vlm:
                vlm.release()
            if vdevice:
                vdevice.release()
        except Exception:
            pass


def _run_inference(image: np.ndarray, prompts: dict,
                   vlm, max_tokens: int, temperature: float,
                   seed: int) -> dict:
    """Execute a single inference (real or simulated)."""
    start = time.time()

    if vlm is None:
        # Demo mode — simulate a response
        time.sleep(1.5)
        answer = (
            "[DEMO MODE] This is a simulated response. "
            "Install and configure HailoRT + a VLM HEF model to get "
            "real AI-powered image analysis. The image appears to contain "
            "various objects and visual elements."
        )
        return {"answer": answer, "time": f"{time.time() - start:.2f}s"}

    prompt = [
        {
            "role": "system",
            "content": [{"type": "text", "text": prompts["system_prompt"]}],
        },
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompts["user_prompt"]},
            ],
        },
    ]

    response_text = ""
    with vlm.generate(
        prompt=prompt, frames=[image],
        temperature=temperature, seed=seed,
        max_generated_tokens=max_tokens,
    ) as generation:
        for chunk in generation:
            if chunk != "<|im_end|>":
                response_text += chunk

    vlm.clear_context()
    elapsed = time.time() - start
    return {
        "answer": response_text.replace("<|im_end|>", "").strip(),
        "time": f"{elapsed:.2f}s",
    }


# ---------------------------------------------------------------------------
# Public Backend class
# ---------------------------------------------------------------------------
class VLMBackend:
    """Manages the VLM worker process and provides a simple inference API."""

    def __init__(self, hef_path: Optional[str] = None,
                 max_tokens: int = 200, temperature: float = 0.1,
                 seed: int = 42,
                 system_prompt: str = "You are a helpful assistant that analyzes images and answers questions about them."):
        self.hef_path = hef_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        self.system_prompt = system_prompt

        self._req_q: mp.Queue = mp.Queue(maxsize=2)
        self._res_q: mp.Queue = mp.Queue(maxsize=2)
        self._process = mp.Process(
            target=_vlm_worker,
            args=(self._req_q, self._res_q, hef_path,
                  max_tokens, temperature, seed),
            daemon=True,
        )
        self._process.start()
        logger.info("VLM backend started")

    def infer(self, image: np.ndarray, user_prompt: str,
              timeout: int = 60) -> dict:
        """Send an image + prompt to the worker and return the result."""
        # Resize / normalise image for the model (336×336 RGB)
        processed = self._prepare_image(image)

        self._req_q.put({
            "image": processed,
            "prompts": {
                "system_prompt": self.system_prompt,
                "user_prompt": user_prompt,
            },
        })
        try:
            resp = self._res_q.get(timeout=timeout)
            if resp["error"]:
                return {"answer": f"Error: {resp['error']}", "time": "error"}
            return resp["result"]
        except Exception:
            return {"answer": f"Timeout after {timeout}s", "time": f"{timeout}s+"}

    def close(self):
        try:
            self._req_q.put(None)
            self._process.join(timeout=3)
            if self._process.is_alive():
                self._process.terminate()
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
