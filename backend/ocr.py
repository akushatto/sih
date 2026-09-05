"""Preprocessing (OpenCV) + OCR (Tesseract) + physical-scale estimation + evidence annotation."""
import os
import cv2
import numpy as np
import pytesseract
from pytesseract import Output

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

PSM = os.getenv("OCR_PSM", "6")


# ---------------- Preprocessing ----------------
def _skew_angle(img_bgr: np.ndarray) -> float:
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    th = cv2.dilate(th, np.ones((3, 25), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angles = []
    for c in cnts:
        if cv2.contourArea(c) < 600:
            continue
        a = cv2.minAreaRect(c)[2]
        if a > 45:
            a -= 90
        angles.append(a)
    return float(np.median(angles)) if angles else 0.0


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess(img_bgr: np.ndarray, deskew: bool = False, max_side: int = 1600):
    """Returns (colour_image_used_for_boxes, grayscale_for_ocr). Boxes are relative to the returned colour image."""
    h, w = img_bgr.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        img_bgr = cv2.resize(img_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    elif max(h, w) < 900:  # tiny images → upscale helps Tesseract
        img_bgr = cv2.resize(img_bgr, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    if deskew:
        a = _skew_angle(img_bgr)
        if 0.5 < abs(a) < 15:
            img_bgr = _rotate(img_bgr, a)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.bilateralFilter(gray, 5, 40, 40)  # light denoise (fast enough for live mode)
    return img_bgr, gray


# ---------------- OCR ----------------
def ocr_lines(gray: np.ndarray, lang: str = "eng+hin"):
    """Word-level OCR grouped into lines with bounding boxes + mean confidence."""
    d = pytesseract.image_to_data(gray, lang=lang, config=f"--oem 3 --psm {PSM}", output_type=Output.DICT)
    lines = {}
    for i, txt in enumerate(d["text"]):
        t = (txt or "").strip()
        try:
            c = float(d["conf"][i])
        except (TypeError, ValueError):
            c = -1
        if not t or c < 0:
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        L = lines.setdefault(key, {"words": [], "confs": []})
        L["words"].append({"t": t, "x": d["left"][i], "y": d["top"][i], "w": d["width"][i], "h": d["height"][i], "c": c})
        L["confs"].append(c)

    out = []
    for L in lines.values():
        ws = L["words"]
        x = min(w["x"] for w in ws); y = min(w["y"] for w in ws)
        x2 = max(w["x"] + w["w"] for w in ws); y2 = max(w["y"] + w["h"] for w in ws)
        out.append({
            "text": " ".join(w["t"] for w in ws),
            "bbox": [x, y, x2 - x, y2 - y],
            "conf": sum(L["confs"]) / len(L["confs"]),
            "words": ws,
        })
    out.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))
    return out


# ---------------- Physical scale (mm per pixel) ----------------
def estimate_scale(img_bgr: np.ndarray, pack_width_mm: float, pack_height_mm: float | None = None, assumed: bool = False):
    """Detect the pack (largest contour) → mm/px. PDP area = width × height of the visible front panel."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = 0, 0, W, H
    if cnts:
        bx, by, bw, bh = cv2.boundingRect(max(cnts, key=cv2.contourArea))
        if bw * bh >= 0.2 * W * H:  # sane detection
            x, y, w, h = bx, by, bw, bh
    mm_per_px = pack_width_mm / max(w, 1)
    pack_h_mm = pack_height_mm or h * mm_per_px
    return {
        "mm_per_px": round(mm_per_px, 5),
        "pack_width_mm": pack_width_mm,
        "pack_height_mm": round(pack_h_mm, 1),
        "pdp_cm2": round(pack_width_mm * pack_h_mm / 100, 1),
        "pack_bbox_px": [int(x), int(y), int(w), int(h)],
        "assumed": assumed,
    }


# ---------------- Evidence annotation ----------------
_COL = {"ok": (88, 209, 48), "warn": (10, 159, 255), "bad": (58, 69, 255)}  # BGR


def annotate(img_bgr: np.ndarray, checks: list):
    out = img_bgr.copy()
    for c in checks:
        if not c.get("bbox"):
            continue
        x, y, w, h = map(int, c["bbox"])
        col = _COL.get(c["s"], (200, 200, 200))
        cv2.rectangle(out, (x, y), (x + w, y + h), col, 2)
        label = f"{c['name'][:30]} {c['conf']}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x, max(0, y - th - 8)), (x + tw + 6, y), col, -1)
        cv2.putText(out, label, (x + 3, max(10, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out