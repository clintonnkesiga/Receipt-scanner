"""Image preprocessing + Tesseract OCR.

Preprocessing matters more than Tesseract config for thermal receipts, so we
grayscale, upscale, denoise, deskew, and threshold before recognition.
"""
import cv2
import numpy as np
import pytesseract

from .config import settings

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Rotate the image so text lines are horizontal."""
    coords = np.column_stack(np.where(gray < 128))
    if coords.size == 0:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, m, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small images — Tesseract likes ~300 DPI equivalents.
    h, w = gray.shape
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = _deskew(gray)

    # Adaptive threshold copes with uneven receipt lighting.
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11,
    )
    return thresh


def run_ocr(image_path: str) -> str:
    """Preprocess then return raw OCR text. Falls back to raw image on failure."""
    try:
        processed = preprocess(image_path)
        config = "--oem 3 --psm 6"  # assume a single uniform block of text
        return pytesseract.image_to_string(processed, config=config)
    except Exception:
        # Last-ditch: OCR the untouched image so we still return something.
        return pytesseract.image_to_string(image_path)
