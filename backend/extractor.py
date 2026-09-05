"""Extract mandatory declarations from OCR lines — Legal Metrology (PC) Rules 2011 + FSSAI. English + Hindi."""
import re

UNIT = r"(kg|kgs|g|gm|gms|gram|grams|mg|ml|l|ltr|litre|liter|कि\.?\s?ग्रा\.?|किलो(?:ग्राम)?|ग्रा(?:म)?|मि\.?\s?ली\.?|लीटर|ली\.?)"
DATE = r"((?:\d{1,2}[/\-.])?(?:\d{1,2}|[A-Za-z]{3,9})\.?[\s,\-/]*\d{2,4})"

PATTERNS = {
    # Rule 6(1)(c) / Rule 8 - Net Quantity
    "net_quantity": re.compile(
        r"(net\s*(?:qty|quantity|wt|weight|content)s?\.?|नेट\s*(?:मात्रा|वजन)|निवल\s*मात्रा|शुद्ध\s*(?:मात्रा|वजन))"
        r"\s*[:.\-]?\s*(\d+(?:[.,]\d+)?)\s*" + UNIT, re.I),

    # Rule 6(1)(e) - MRP
    "mrp": re.compile(
        r"(m\.?\s*r\.?\s*p\.?|maximum\s+retail\s+price|max\.?\s*retail\s*price|अधिकतम\s+खुदरा\s+मूल्य)"
        r"\s*[:.\-]?\s*(?:rs\.?|₹|inr)?\s*(\d+(?:[.,]\d{1,2})?)", re.I),

    # Rule 6(1)(d) - Mfg / Packing Date
    "mfg_date": re.compile(
        r"(mfg\.?|mfd\.?|manufactured|manufacturing|pkd\.?|packed|packing|date\s+of\s+(?:mfg|manufacture|packing)|"
        r"निर्माण\s*(?:तिथि|की\s*तारीख)?|पैकिंग\s*(?:तिथि)?)(?:\s*(?:date|dt\.?|on))?\s*[:.\-]?\s*" + DATE, re.I),

    # Rule 6(1)(d) proviso - Expiry / Best Before
    "expiry": re.compile(
        r"(exp\.?|expiry|expires|use\s+by|best\s+before|समाप्ति|उपयोग\s+(?:करें|की\s+अवधि)|bb\.?d?)\s*"
        r"(?:date|dt\.?|on|within)?\s*[:.\-]?\s*"
        r"(" + DATE[1:-1] + r"|\d{1,2}\s*(?:months?|माह|महीने)|\d{1,3}\s*(?:days?|दिन))", re.I),

    # Rule 6(1)(a) - Manufacturer / Packer / Importer
    "manufacturer": re.compile(
        r"((?:mfd|mfg|manufactured|mkt|mktd|marketed|pkd|packed|imported|manufacturer|packer)\.?\s*(?:&|and)?\s*"
        r"(?:pkd|packed|mktd|marketed)?\.?\s*by|निर्माता|पैकर|विपणक)\s*[:.\-]?\s*(.{4,})", re.I),

    # Rule 6(1)(a) proviso - Country of Origin
    "country_of_origin": re.compile(
        r"(country\s+of\s+origin|made\s+in|product\s+of|उत्पत्ति\s+का\s+देश|मूल\s+देश|निर्मित\s+देश)\s*[:.\-]?\s*"
        r"([A-Za-z\u0900-\u097F .]{3,30})", re.I),

    # Rule 6(1)(f) - Consumer Care
    "consumer_care": re.compile(
        r"(consumer\s*care|customer\s*care|complaints?|feedback|toll\s*free|helpline|उपभोक्ता\s*(?:सेवा|शिकायत)|ग्राहक\s*सेवा|"
        r"[\w.+-]+@[\w-]+\.\w+|1800[\s\-]?\d{3}[\s\-]?\d{3,4}|(?:\+91[\s\-]?)?[6-9]\d{9})", re.I),

    # Rule 6(2) - Batch / Lot / Code Number
    "batch_number": re.compile(
        r"(batch\s*(?:no|num|number|code)?\.?|lot\s*(?:no|num|number)?\.?|b\.?\s*no\.?|l\.?\s*no\.?|"
        r"बैच\s*(?:संख्या)?|लॉट\s*(?:संख्या)?)\s*[:.#\-]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{1,20})", re.I),

    # FSS Act 2006 - FSSAI License / Registration Number
    "fssai": re.compile(
        r"(fssai|lic\.?\s*no\.?|lic\s*number|license\s*(?:no\.?|number)|registration\s*(?:no\.?|number)|"
        r"भारतीय\s*खाद्य|food\s*safety)\s*[:.#\-]?\s*(\d{14}|\d{13}|\d[\d\s\-]{10,16}\d)", re.I),

    # FSSAI Labelling Regs - Veg / Non-Veg Declaration (green/red dot)
    "veg_nonveg": re.compile(
        r"((?:100\s*%?\s*)?(?:pure\s+)?veg(?:etarian)?|non[\s\-]?veg(?:etarian)?|"
        r"शाकाहारी|मांसाहारी|शुद्ध\s*शाकाहारी)", re.I),
}

PIN = re.compile(r"\b[1-9]\d{5}\b")


def _union(a, b):
    x = min(a[0], b[0]); y = min(a[1], b[1])
    x2 = max(a[0] + a[2], b[0] + b[2]); y2 = max(a[1] + a[3], b[1] + b[3])
    return [x, y, x2 - x, y2 - y]


def extract(lines: list) -> dict:
    fields = {}
    n = len(lines)
    for idx, L in enumerate(lines):
        text = L["text"]
        for name, pat in PATTERNS.items():
            if name in fields:
                continue
            m = pat.search(text)
            if not m:
                continue
            f = {"value": None, "line": idx, "bbox": list(L["bbox"]), "conf": round(L["conf"], 1), "raw": text}

            if name == "net_quantity":
                f["value"] = f"{m.group(2)} {m.group(3)}"
                f["numeral"] = m.group(2)
                f["unit"] = re.sub(r"[\s.]", "", m.group(3)).lower()
                f["qualifier"] = bool(re.search(r"approx|about|minimum|min\.|not\s+less|लगभग|न्यूनतम", text, re.I))
            elif name == "mrp":
                f["value"] = "₹" + m.group(2)
                f["numeral"] = m.group(2)
                ctx = text + " " + (lines[idx + 1]["text"] if idx + 1 < n else "")
                f["incl_taxes"] = bool(re.search(r"incl|inclusive|सहित", ctx, re.I))
            elif name in ("mfg_date", "expiry", "country_of_origin"):
                f["value"] = m.group(2).strip()
            elif name == "manufacturer":
                txt = m.group(2).strip()
                for j in (idx + 1, idx + 2):
                    if j < n:
                        txt += ", " + lines[j]["text"]
                        f["bbox"] = _union(f["bbox"], lines[j]["bbox"])
                        if PIN.search(lines[j]["text"]):
                            break
                f["value"] = txt
                f["has_pin"] = bool(PIN.search(txt))
            elif name == "consumer_care":
                f["value"] = text
            elif name == "batch_number":
                f["value"] = m.group(2).strip()
            elif name == "fssai":
                raw_num = re.sub(r"[\s\-]", "", m.group(2))
                f["value"] = raw_num
                f["valid_length"] = len(raw_num) in (13, 14)
            elif name == "veg_nonveg":
                f["value"] = m.group(0)
                f["is_nonveg"] = bool(re.search(r"non|मांसाहारी", m.group(0), re.I))

            # numeral height (px) for Rule 7 font-size check
            if f.get("numeral"):
                target = f["numeral"].replace(",", ".")
                hits = [w for w in L["words"] if target in w["t"].replace(",", ".")]
                f["numeral_h_px"] = max(w["h"] for w in hits) if hits else L["bbox"][3]
            fields[name] = f
    return fields
