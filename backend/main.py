import os, io, time, uuid, base64, hashlib, socket
from datetime import datetime
from pathlib import Path

import cv2, numpy as np, qrcode
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from ocr import preprocess, ocr_lines, estimate_scale, annotate
from extractor import extract
from rules import evaluate, summarize
from db import init_db, save_inspection, list_inspections, get_inspection, stats
from report import build_pdf

ROOT = Path(__file__).resolve().parent
EVID = ROOT / "evidence"; EVID.mkdir(exist_ok=True)
FRONT = ROOT.parent / "frontend"
DEFAULT_WIDTH_MM = {"FMCG Food": 150, "Personal Care": 60, "Grocery Staples": 200}

app = FastAPI(title="LabelGuard API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
init_db()


def _guess_name(lines, H):
    top = [l for l in lines if l["bbox"][1] < 0.4 * H and len(l["text"]) > 3]
    return max(top, key=lambda l: l["bbox"][3])["text"][:60] if top else None


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}


@app.post("/api/scan")
async def scan(file: UploadFile = File(...), mode: str = "live", save: bool = False, lang: str = "eng+hin",
               category: str = "FMCG Food", pack_width_mm: float | None = None, pack_height_mm: float | None = None,
               product_name: str | None = None):
    t0 = time.time()
    raw = await file.read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Invalid image")

    img, gray = preprocess(img, deskew=(mode != "live"))
    H, W = gray.shape
    lines = ocr_lines(gray, lang)
    fields = extract(lines)
    scale = estimate_scale(img, pack_width_mm or DEFAULT_WIDTH_MM.get(category, 150), pack_height_mm, assumed=pack_width_mm is None)
    checks = evaluate(fields, scale, category, full_text=" ".join(l["text"] for l in lines))

    annotated_b64 = buf = None
    if mode != "live" or save:
        ann = annotate(img, checks)
        _, buf = cv2.imencode(".jpg", ann, [cv2.IMWRITE_JPEG_QUALITY, 85])
        annotated_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

    for c in checks:
        if c.get("bbox"):
            x, y, w, h = c["bbox"]; c["bbox"] = [round(x / W, 4), round(y / H, 4), round(w / W, 4), round(h / H, 4)]

    res = {"id": None, "mode": mode, "lang": lang, "category": category,
           "product_name": product_name or _guess_name(lines, H), "scale": scale, "fields": fields, "checks": checks,
           **summarize(checks), "ocr_lines": [l["text"] for l in lines][:80], "image_size": [W, H],
           "timing_ms": int((time.time() - t0) * 1000), "annotated_image": annotated_b64}

    if save:
        iid = "LG-" + datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5].upper()
        (EVID / f"{iid}.jpg").write_bytes(raw)
        (EVID / f"{iid}_annotated.jpg").write_bytes(buf.tobytes())
        res.update(id=iid, sha256=hashlib.sha256(raw).hexdigest())
        save_inspection(res, str(EVID / f"{iid}.jpg"))
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


@app.get("/api/stats")
def api_stats(days: int = 30):
    return stats(days)


@app.get("/api/report/{iid}.pdf")
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


app.mount("/", StaticFiles(directory=str(FRONT), html=True), name="frontend")
