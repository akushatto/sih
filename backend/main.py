import os, io, time, uuid, base64, hashlib, socket
from datetime import datetime
from pathlib import Path

import cv2, numpy as np, qrcode
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from ocr import preprocess, ocr_lines, estimate_scale, annotate, detect_qr
from extractor import extract
from rules import evaluate, summarize
from catalog import enrich_fields
from db import init_db, save_inspection, list_inspections, get_inspection, stats
from report import build_pdf

ROOT = Path(__file__).resolve().parent
EVID = ROOT / "evidence"; EVID.mkdir(exist_ok=True)
UPLOADS = ROOT / "uploads"; UPLOADS.mkdir(exist_ok=True)
FRONT = ROOT.parent / "frontend"
DEFAULT_WIDTH_MM = {"FMCG Food": 150, "Personal Care": 60, "Grocery Staples": 200}

app = FastAPI(title="LabelGuard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
init_db()


def _guess_name(lines, H):
    valid = []
    for l in lines:
        txt = l.get("text", "").strip()
        alnum = sum(1 for c in txt if c.isalnum())
        # Filter out noisy OCR artifacts like '; ae Ty' or punctuation lines
        if l["bbox"][1] < 0.5 * H and len(txt) >= 4 and alnum >= 4 and (alnum / len(txt)) >= 0.6 and l.get("conf", 0) >= 35:
            # exclude lines that look like headers, dates, or measurements
            if not any(k in txt.lower() for k in ["mrp", "mfd", "exp", "net", "qty", "vol", "batch", "lic"]):
                valid.append(l)
    return max(valid, key=lambda l: l["bbox"][3])["text"][:60] if valid else None


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}


def _decode_image(raw: bytes) -> np.ndarray | None:
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is not None:
        return img
    try:
        from PIL import Image, ImageOps
        pil_img = Image.open(io.BytesIO(raw))
        pil_img = ImageOps.exif_transpose(pil_img)
        pil_img = pil_img.convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


@app.post("/api/scan")
async def scan(request: Request, file: UploadFile = File(...), mode: str = "live", save: bool = False, lang: str = "eng+hin",
               category: str = "FMCG Food", pack_width_mm: float | None = None, pack_height_mm: float | None = None,
               product_name: str | None = None):
    t0 = time.time()
    try:
        form = await request.form()
        if "save" in form:
            save = str(form["save"]).lower() in ("true", "1", "yes")
        if "mode" in form:
            mode = str(form["mode"])
        if "category" in form:
            category = str(form["category"])
        if "product_name" in form:
            product_name = str(form["product_name"])
    except Exception:
        pass

    raw = await file.read()
    img = _decode_image(raw)
    if img is None:
        raise HTTPException(400, "Invalid image: could not decode file")

    if mode == "upload":
        save = True

    img, gray = preprocess(img, deskew=(mode != "live"))
    H, W = gray.shape
    lines = ocr_lines(gray, lang)
    qr_codes = detect_qr(img)
    fields = extract(lines)

    # Multi-angle OCR scan if fewer than 3 fields detected (essential for cans, bottles, or rotated packaging)
    if len(fields) < 3:
        for rot_flag in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180]:
            im_rot = cv2.rotate(img, rot_flag)
            _, gray_rot = preprocess(im_rot, deskew=False)
            lines_rot = ocr_lines(gray_rot, lang)
            fields_rot = extract(lines_rot)
            if fields_rot:
                for k, v in fields_rot.items():
                    if k not in fields:
                        fields[k] = v
                lines.extend(lines_rot)
            if len(fields) >= 4:
                break

    # Include QR-decoded text in full_text so rules engine can see it
    qr_text = " ".join(q["data"] for q in qr_codes if q.get("data"))
    full_text = " ".join(l["text"] for l in lines) + (" " + qr_text if qr_text else "")

    # Enrich extracted declarations via GS1 India & statutory FMCG catalog
    fields, detected_pname = enrich_fields(fields, qr_codes, full_text=full_text)

    scale = estimate_scale(img, pack_width_mm or DEFAULT_WIDTH_MM.get(category, 150), pack_height_mm, assumed=pack_width_mm is None)
    pname = product_name or detected_pname or _guess_name(lines, H)
    checks = evaluate(fields, scale, category, full_text=full_text, product_name=pname)

    annotated_b64 = buf = None
    if mode != "live" or save:
        ann = annotate(img, checks)
        _, buf = cv2.imencode(".jpg", ann, [cv2.IMWRITE_JPEG_QUALITY, 85])
        annotated_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

    for c in checks:
        if c.get("bbox"):
            x, y, w, h = c["bbox"]; c["bbox"] = [round(x / W, 4), round(y / H, 4), round(w / W, 4), round(h / H, 4)]

    # Normalize QR bounding boxes to 0-1 like compliance check bboxes
    for q in qr_codes:
        if q.get("bbox"):
            x, y, w, h = q["bbox"]
            q["bbox"] = [round(x/W, 4), round(y/H, 4), round(w/W, 4), round(h/H, 4)]

    res = {"id": None, "mode": mode, "lang": lang, "category": category,
           "product_name": pname, "scale": scale, "fields": fields, "checks": checks,
           **summarize(checks), "qr_codes": qr_codes, "ocr_lines": [l["text"] for l in lines][:80], "image_size": [W, H],
           "timing_ms": int((time.time() - t0) * 1000), "annotated_image": annotated_b64}

    if save:
        iid = "LG-" + datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5].upper()
        evid_img = EVID / f"{iid}.jpg"
        evid_ann = EVID / f"{iid}_annotated.jpg"
        upload_img = UPLOADS / f"{iid}.jpg"
        evid_img.write_bytes(raw)
        upload_img.write_bytes(raw)
        if buf is not None:
            evid_ann.write_bytes(buf.tobytes())
        res.update(
            id=iid,
            sha256=hashlib.sha256(raw).hexdigest(),
            image_url=f"/evidence/{iid}.jpg",
            annotated_url=f"/evidence/{iid}_annotated.jpg",
            upload_url=f"/uploads/{iid}.jpg",
            saved=True,
        )
        save_inspection(res, str(evid_img))
    return res


@app.get("/api/inspections")
def api_list(limit: int = 50, status: str | None = None):
    return list_inspections(limit, status)


@app.get("/api/inspections/{iid}")
def api_get(iid: str):
    r = get_inspection(iid)
    if not r:
        raise HTTPException(404, "Not found")
    return r


@app.api_route("/api/inspections/{iid}/image", methods=["GET", "HEAD"])
def api_get_image(iid: str):
    p = EVID / f"{iid}.jpg"
    if not p.exists():
        p = UPLOADS / f"{iid}.jpg"
    if not p.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(p, media_type="image/jpeg")


@app.api_route("/api/inspections/{iid}/annotated", methods=["GET", "HEAD"])
def api_get_annotated(iid: str):
    p = EVID / f"{iid}_annotated.jpg"
    if not p.exists():
        raise HTTPException(404, "Annotated image not found")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/stats")
def api_stats(days: int = 30):
    return stats(days)


@app.api_route("/api/report/{iid}.pdf", methods=["GET", "HEAD"])
def api_report(iid: str):
    r = get_inspection(iid)
    if not r:
        raise HTTPException(404, "Not found")
    pdf = build_pdf(r, str(EVID / f"{iid}_annotated.jpg"))
    return StreamingResponse(pdf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{iid}.pdf"'})


@app.get("/api/whereami")
def whereami(request: Request):
    return {"public_url": os.getenv("PUBLIC_URL") or None,
            "lan_url": f"http://{_lan_ip()}:{request.url.port or 8000}/",
            "note": "Phone camera needs HTTPS. Use cloudflared/ngrok (set PUBLIC_URL) or mkcert."}


@app.get("/api/qr")
def qr(request: Request, url: str | None = None):
    target = url or os.getenv("PUBLIC_URL") or f"{request.url.scheme}://{request.headers.get('host')}/"
    target = target.rstrip("/") + "/#demo"
    img = qrcode.make(target, box_size=8, border=2)
    b = io.BytesIO(); img.save(b, "PNG"); b.seek(0)
    return StreamingResponse(b, media_type="image/png", headers={"X-Target-URL": target, "Cache-Control": "no-store"})


app.mount("/evidence", StaticFiles(directory=str(EVID)), name="evidence")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")
app.mount("/", StaticFiles(directory=str(FRONT), html=True), name="frontend")

