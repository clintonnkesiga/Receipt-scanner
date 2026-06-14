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


def _rotate(img: np.ndarray, angle: int) -> np.ndarray:
    """Rotate by a right angle (0/90/180/270, clockwise)."""
    return {
        0: img,
        90: cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
        180: cv2.rotate(img, cv2.ROTATE_180),
        270: cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }[angle % 360]


def _best_orientation(img: np.ndarray) -> int:
    """Probe 0/90/180/270 on a downscaled copy and return the angle Tesseract
    reads with the highest confidence. Phone photos of receipts are often
    sideways/upside-down, which _deskew (sub-degree tilt only) can't fix and
    Tesseract's OSD detects unreliably on noisy thermal paper."""
    h, w = img.shape[:2]
    scale = 1000 / max(h, w) if max(h, w) > 1000 else 1.0
    small = (
        cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale != 1.0
        else img
    )
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    best_angle, best_conf = 0, -1.0
    for angle in (0, 90, 180, 270):
        tmp = _write_temp(_rotate(gray, angle))
        try:
            _, conf = _ocr_path(tmp)
        except Exception:
            conf = -1.0
        finally:
            _safe_remove(tmp)
        if conf > best_conf:
            best_angle, best_conf = angle, conf
    return best_angle


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

# Cap the longest side before full OCR. Phone photos are 3000-4000px, but
# receipt text stays legible at ~2400px and Tesseract runs much faster on
# fewer pixels (cost scales with area).
_MAX_OCR_DIM = 2400


def _cap_size(img: np.ndarray, max_dim: int = _MAX_OCR_DIM) -> np.ndarray:
    """Downscale so the longest side is at most `max_dim` (no-op if smaller)."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return img
    scale = max_dim / longest
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


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
    """OCR an image file; return (reconstructed text, mean confidence 0-100).

    Uses a single `image_to_data` call and rebuilds the line text from it,
    instead of also calling `image_to_string` — that halves the number of
    (relatively expensive) Tesseract invocations per image.
    """
    data = pytesseract.image_to_data(path, config=OCR_CONFIG, output_type=Output.DICT)
    n = len(data["text"])
    confs: list[float] = []
    lines: dict[tuple, list[str]] = {}
    order: list[tuple] = []
    for i in range(n):
        word = data["text"][i]
        if not word.strip():
            continue
        c = float(data["conf"][i])
        if c >= 0:
            confs.append(c)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(word)
    text = "\n".join(" ".join(lines[k]) for k in order)
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

    img = cv2.imread(file_path)
    if img is None:
        # Unreadable by OpenCV — let Tesseract try the file directly.
        try:
            return _ocr_path(file_path)[0]
        except Exception:
            return ""

    # Correct page orientation first (90°/180° phone photos) — otherwise all
    # downstream OCR is garbage no matter how good the thresholding is.
    angle = _best_orientation(img)
    if angle:
        img = _rotate(img, angle)

    # Cap resolution so full-size recognition isn't needlessly slow.
    img = _cap_size(img)

    # Photos of thermal receipts OCR better after preprocessing; clean digital
    # scans OCR better raw. Run both on the oriented image and keep whichever
    # Tesseract is more confident about (raw is tried first, so it wins ties).
    candidates = [_write_temp(img)]
    try:
        candidates.append(_write_temp(_preprocess_array(img)))
    except Exception:
        pass

    best_text, best_conf = "", -2.0
    try:
        for path in candidates:
            try:
                text, conf = _ocr_path(path)
            except Exception:
                continue
            if conf > best_conf:
                best_text, best_conf = text, conf
    finally:
        for path in candidates:
            _safe_remove(path)
    return best_text


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
