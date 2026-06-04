"""Image preprocessing + Tesseract OCR.

Preprocessing matters more than Tesseract config for thermal receipts, so we
grayscale, upscale, denoise, deskew, and threshold before recognition.
"""
import os
import tempfile

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

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


# Cap how many PDF pages we OCR so a large statement can't tie up the worker.
MAX_PDF_PAGES = 10

OCR_CONFIG = "--oem 3 --psm 6"  # assume a single uniform block of text


def _preprocess_array(img: np.ndarray) -> np.ndarray:
    """Grayscale, upscale, denoise, deskew, threshold a BGR image array."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small images — Tesseract likes ~300 DPI equivalents.
    h, w = gray.shape
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = _deskew(gray)

    # Adaptive threshold copes with uneven receipt lighting.
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11,
    )


def preprocess(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    return _preprocess_array(img)


def _write_temp(img: np.ndarray) -> str:
    """Write an array to a temp PNG and return its path (caller deletes it).
    pytesseract chokes on in-memory images on some platforms, so we OCR paths."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path


def _ocr_path(path: str) -> tuple[str, float]:
    """OCR an image file; return (text, mean Tesseract confidence 0-100)."""
    data = pytesseract.image_to_data(path, config=OCR_CONFIG, output_type=Output.DICT)
    confs = [
        float(c)
        for c, t in zip(data["conf"], data["text"])
        if t.strip() and float(c) >= 0
    ]
    text = pytesseract.image_to_string(path, config=OCR_CONFIG)
    return text, (sum(confs) / len(confs) if confs else -1.0)


def _pdf_to_images(pdf_path: str) -> list[np.ndarray]:
    """Render PDF pages to BGR image arrays (first MAX_PDF_PAGES pages)."""
    import fitz  # PyMuPDF — imported lazily so image-only setups don't need it

    images: list[np.ndarray] = []
    with fitz.open(pdf_path) as doc:
        for page in doc[:MAX_PDF_PAGES]:
            pix = page.get_pixmap(dpi=200)  # render at a readable resolution
            arr = np.frombuffer(pix.tobytes("png"), np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)
    return images


def run_ocr(file_path: str) -> str:
    """Return raw OCR text for an image or PDF."""
    if file_path.lower().endswith(".pdf"):
        try:
            texts = []
            for img in _pdf_to_images(file_path):
                tmp = _write_temp(img)
                try:
                    texts.append(_ocr_path(tmp)[0])
                finally:
                    _safe_remove(tmp)
            return "\n".join(texts).strip()
        except Exception:
            return ""

    # Photos of thermal receipts OCR better after preprocessing; clean digital
    # scans OCR better raw. Run both and keep whichever Tesseract is more
    # confident about (raw is tried first, so it wins ties).
    tmp = None
    try:
        tmp = _write_temp(preprocess(file_path))
    except Exception:
        tmp = None

    best_text, best_conf = "", -2.0
    try:
        for path in [file_path] + ([tmp] if tmp else []):
            try:
                text, conf = _ocr_path(path)
            except Exception:
                continue
            if conf > best_conf:
                best_text, best_conf = text, conf
    finally:
        if tmp:
            _safe_remove(tmp)
    return best_text


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
