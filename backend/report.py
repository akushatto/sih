import io, os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT = "Helvetica"
_p = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansDevanagari-Regular.ttf")
if os.path.exists(_p):
    pdfmetrics.registerFont(TTFont("Noto", _p)); FONT = "Noto"

_strip = re.compile(r"<[^>]+>")


def build_pdf(insp: dict, annotated_path: str | None) -> io.BytesIO:
    buf = io.BytesIO(); c = rl.Canvas(buf, pagesize=A4); W, H = A4
    y = H - 18 * mm
    c.setFont(FONT, 18); c.drawString(18 * mm, y, "LabelGuard — Compliance Report"); y -= 8 * mm
    c.setFont(FONT, 10)
    for line in [f"Inspection ID: {insp['id']}    Date: {insp['created_at'][:19].replace('T', ' ')} UTC",
                 f"Product: {insp.get('product_name') or '-'}    Category: {insp.get('category')}",
                 f"Status: {insp['status']}    Score: {insp['score']}%    Violations: {insp['violations']}",
                 f"Evidence SHA-256: {insp.get('sha256')}",
                 "Basis: Legal Metrology (Packaged Commodities) Rules, 2011"]:
        c.drawString(18 * mm, y, line); y -= 5.5 * mm
    if annotated_path and os.path.exists(annotated_path):
        try:
            c.drawImage(annotated_path, 18 * mm, y - 80 * mm, width=90 * mm, height=78 * mm, preserveAspectRatio=True, anchor="nw")
            y -= 84 * mm
        except Exception:
            pass
    c.setFont(FONT, 12); c.drawString(18 * mm, y, "Rule-by-rule findings"); y -= 7 * mm; c.setFont(FONT, 9)
    for ch in insp["checks"]:
        if y < 30 * mm:
            c.showPage(); c.setFont(FONT, 9); y = H - 18 * mm
        mark = {"ok": "[OK]", "warn": "[REVIEW]", "bad": "[VIOLATION]", "info": "[INFO]"}[ch["s"]]
        c.drawString(18 * mm, y, f"{mark} {ch['name']}  ({ch['conf']})"); y -= 4.5 * mm
        for t in [ch["ref"], ch["found"], ch.get("fix") or "", "  ".join(ch.get("measure") or [])]:
            t = _strip.sub("", t or "")
            while t:
                c.drawString(22 * mm, y, t[:105]); t = t[105:]; y -= 4.2 * mm
        y -= 2 * mm
    c.showPage(); c.save(); buf.seek(0)
    return buf 