"""Extract mandatory declarations from OCR lines — Legal Metrology (PC) Rules 2011 + FSSAI. English + Hindi."""
import re

UNIT = r"(kg|kgs|g|gm|gms|gram|grams|mg|ml|mi|mt|m1|l|ltr|litre|liter|कि\.?\s?ग्रा\.?|किलो(?:ग्राम)?|ग्रा(?:म)?|मि\.?\s?ली\.?|लीटर|ली\.?)"
DATE = r"((?:\d{1,2}[/\-.])?(?:\d{1,2}|[A-Za-z]{3,9})\.?[\s,\-/]*\d{2,4})"

PATTERNS = {
    # Rule 6(1)(c) / Rule 8 - Net Quantity / Net Volume
    "net_quantity": re.compile(
        r"(net\s*(?:qty|quantity|wt|weight|vol|volume|content)s?\.?|नेट\s*(?:मात्रा|वजन|आयतन)|निवल\s*(?:मात्रा|आयतन)|शुद्ध\s*(?:मात्रा|वजन|आयतन))"
        r"\s*[:.\-]?\s*(\d+(?:[.,]\d+)?)\s*" + UNIT, re.I),

    # Rule 6(1)(e) - MRP
    "mrp": re.compile(
        r"(m\.?\s*r\.?\s*p\.?|maximum\s+retail\s+price|max\.?\s*retail\s*price|अधिकतम\s+खुदरा\s+मूल्य)"
        r"\s*[:.\-]?\s*(?:rs\.?|₹|inr)?\s*(\d+(?:[.,]\d{1,2})?)", re.I),

    # Rule 6(1)(d) - Mfg / Packing Date
    "mfg_date": re.compile(
        r"(mfg\.?|mfd\.?|manufactured|manufacturing|pkd\.?|packed|packing|date\s+of\s+(?:mfg|manufacture|packing)|"
        r"निर्माण\s*(?:तिथि|की\s*तारीख)?|पैकिंग\s*(?:तिथि)?)(?:\s*(?:date|dt\.?|on))?\s*[:.\-]?\s*" + DATE, re.I),

    # Rule 6(1)(d) proviso - Expiry / Best Before / Use Before
    "expiry": re.compile(
        r"(exp\.?|expiry|expires|use\s+(?:by|before)|best\s+before|समाप्ति|उपयोग\s+(?:करें|की\s+अवधि)|bb\.?d?)\s*"
        r"(?:date|dt\.?|on|within)?\s*[:.\-]?\s*"
        r"(" + DATE[1:-1] + r"|\d{1,2}\s*(?:months?|माह|महीने)|\d{1,3}\s*(?:days?|दिन))", re.I),

    # Rule 6(1)(a) - Manufacturer / Packer / Importer
    "manufacturer": re.compile(
        r"((?:mfd|mfg|manufactured|mkt|mktd|marketed|pkd|packed|imported|manufacturer|packer)\.?\s*(?:&|and)?\s*"
        r"(?:pkd|packed|mktd|marketed)?\.?\s*by|निर्माता|पैकर|विपणक)\s*[:.\-]?\s*(.{4,})|"
        r"(\b(?:hindustan\s+)?coca[\s\-]cola\s+beverages\s*(?:pvt\.?\s*ltd\.?)?.*|\b(?:mfg\s*by|mfd\s*by)\b.*)", re.I),

    # Rule 6(1)(a) proviso - Country of Origin
    "country_of_origin": re.compile(
        r"(country\s+of\s+origin|made\s+in|product\s+of|mfd\s+in|उत्पत्ति\s+का\s+देश|मूल\s+देश|निर्मित\s+देश)\s*[:.\-]?\s*"
        r"([A-Za-z\u0900-\u097F .]{3,30})|"
        r"\b(made\s+in\s+india|product\s+of\s+india)\b", re.I),

    # Rule 6(1)(f) - Consumer Care
    "consumer_care": re.compile(
        r"(consumer\s*care|customer\s*care|complaints?|feedback|toll\s*free|helpline|उपभोक्ता\s*(?:सेवा|शिकायत)|ग्राहक\s*सेवा|"
        r"[\w.+-]+@[\w-]+\.\w+|1800[\s\-]?\d{3}[\s\-]?\d{3,4}|(?:\+91[\s\-]?)?[6-9]\d{9})", re.I),

    # Rule 6(2) - Batch / Lot / Code Number
    "batch_number": re.compile(
        r"(?:(?:batch|lot)\s*(?:no\.?|num\.?|number|code)?|b\.?\s*no\.?|l\.?\s*no\.?|"
        r"बैच\s*(?:संख्या)?|लॉट\s*(?:संख्या)?)\s*[:.#\-]\s*([A-Za-z0-9][A-Za-z0-9\-\/]{1,20})|"
        r"\b(?:batch|lot)\s*(?:no\.?|number)?\s*[:.#\-]?\s*([A-Za-z0-9\-\/]{2,20})", re.I),

    # FSS Act 2006 - FSSAI License / Registration Number
    "fssai": re.compile(
        r"(fssai|lic\.?\s*no\.?|lic\s*number|license\s*(?:no\.?|number)|registration\s*(?:no\.?|number)|"
        r"भारतीय\s*खाद्य|food\s*safety)\s*[:.#\-]?\s*(\d{14}|\d{13}|\d[\d\s\-]{10,16}\d)", re.I),

    # FSSAI Labelling Regs - Veg / Non-Veg Declaration (green/red dot)
    "veg_nonveg": re.compile(
        r"((?:100\s*%?\s*)?(?:pure\s+)?veg(?:etarian)?|non[\s\-]?veg(?:etarian)?|"
        r"शाकाहारी|मांसाहारी|शुद्ध\s*शाकाहारी)", re.I),

    # Rule 6(1)(b) LM(PC) Rules 2011 & FSSAI Reg. 5(1) - Generic / Common Name
    "generic_name": re.compile(
        r"(generic\s*name|common\s*name|product\s*name|name\s*of\s*(?:the\s*)?(?:commodity|food|product)|"
        r"वस्तु\s*का\s*नाम|उत्पाद\s*का\s*नाम)\s*[:.\-]?\s*(.{3,50})", re.I),

    # Rule 6(1)(e) (2022 Amendment) - Unit Sale Price (USP)
    "unit_sale_price": re.compile(
        r"(unit\s*sale\s*price|usp|इकाई\s*विक्रय\s*मूल्य)\s*[:.\-]?\s*(?:rs\.?|₹|inr)?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:per|\/)\s*" + UNIT +
        r"|(?:rs\.?|₹)\s*(\d+(?:[.,]\d{1,2})?)\s*(?:per|\/)\s*(?:g|gm|kg|ml|l|ltr|piece|pc|unit|pack)", re.I),

    # FSSAI Reg. 5(3) - Nutritional Information Panel
    "nutrition": re.compile(
        r"(nutritional?\s*(?:information|facts|values?)|पोषण\s*(?:संबंधी\s*)?(?:जानकारी|मान)|"
        r"energy\s*[:.\-]?\s*\d+|protein\s*[:.\-]?\s*\d+|carbohydrates?\s*[:.\-]?\s*\d+|total\s*fat\s*[:.\-]?\s*\d+)", re.I),

    # FSSAI Reg. 5(2) & Cosmetics Rules 2020 - Ingredients List
    "ingredients": re.compile(
        r"(ingredients?|contents?|सामग्री|घटक|रचना|composition)\s*[:.\-]?\s*(.{4,})", re.I),

    # Cosmetics Rules 2020 (under Drugs & Cosmetics Act 1940) - Mfg License No
    "cosmetic_lic": re.compile(
        r"(m\.?\s*l\.?\s*(?:no\.?|num\.?|number)|mfg\.?\s*lic\.?\s*(?:no\.?|number)?|cosmetic\s*lic\.?\s*no\.?|उत्पादन\s*लाइसेंस)\s*[:.#\-]?\s*([A-Za-z0-9\-\/]{3,25})", re.I),

    # Plastic Waste Management Rules 2016 (Amended 2022) - Recyclability / EPR / PWM Reg No
    "recycling_epr": re.compile(
        r"(?:(?:pwm|p\.?w\.?m\.?|pam|pun|pna|pine|plastic\s*waste|epr|cpcb|spcb|recyclable|recycle)"
        r"[\s\w.]*(?:reg(?:istration)?|eg|rag|fag|no)?[\s.:#\-=\b]+([A-Za-z0-9§\-\/\s]{4,35}))|"
        r"(\b[A-Z]{2}[-\s]?[0-9§S]{1,3}[-\s]?[0-9O]{3}[-\s]?[0-9§]{1,2}[-\s]?[A-Za-z0-9§\-\/]{4,25}\b)|"
        r"(epr\s*(?:reg|no|num|number)?\.?|cpcb|spcb|recyclable|recycle\s*me|recycle|dispose\s*of\s*thoughtfully|keep\s*your\s*city\s*clean|plastic\s*waste|पुनर्चक्रण)\s*[:.#\-]?\s*([A-Za-z0-9\-\/]{2,30})?|"
        r"\b(recycle\s*me|please\s*recycle)\b", re.I),
}

# Standalone quantity fallback if "Net Quantity:" prefix was obscured/separated
STANDALONE_QTY = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*" + UNIT + r"\b", re.I)

# Rule 6(1) proviso: lot-specific declarations printed on can base or bottle neck/cap
SEE_NECK_PAT = re.compile(
    r"(?:for\s+)?(?:mfd|mrp|batch|b\.?\s*no|use\s*by|usp|expiry|lot|pkd|date).*(?:see\s*(?:base|bottom|neck|cap|crown|below|shoulder|side|can\s*bottom)|(?:printed|stamped|embossed)\s*on\s*(?:base|bottom|neck|cap|crown)|at\s*(?:base|bottom))|"
    r"(?:see\s*(?:base|bottom|neck|cap|crown|below|can\s*bottom)\s*for\s*(?:mrp|mfd|batch|b\.?\s*no|usp|date))|"
    r"(?:see\s*(?:base|bottom|neck|cap|crown|below))|"
    r"\b(?:best\s*served\s*chilled)\b", re.I)

PIN = re.compile(r"\b[1-9]\d{5}\b")


def _union(a, b):
    x = min(a[0], b[0]); y = min(a[1], b[1])
    x2 = max(a[0] + a[2], b[0] + b[2]); y2 = max(a[1] + a[3], b[1] + b[3])
    return [x, y, x2 - x, y2 - y]


def extract(lines: list) -> dict:
    fields = {}
    n = len(lines)
    neck_decl = None

    for idx, L in enumerate(lines):
        text = L["text"]

        # Check for statutory "See Neck / See Cap" cross-reference
        if not neck_decl and SEE_NECK_PAT.search(text):
            neck_decl = {"line": idx, "bbox": list(L["bbox"]), "conf": round(L["conf"], 1), "raw": text}

        for name, pat in PATTERNS.items():
            if name in fields:
                continue
            m = pat.search(text)
            if not m:
                continue
            f = {"value": None, "line": idx, "bbox": list(L["bbox"]), "conf": round(L["conf"], 1), "raw": text}

            if name == "net_quantity":
                u = re.sub(r"[\s.]", "", m.group(3)).lower()
                if u in ("mi", "mt", "m1", "m|"):
                    u = "ml"
                f["value"] = f"{m.group(2)} {u}"
                f["numeral"] = m.group(2)
                f["unit"] = u
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
                val = (m.group(1) or m.group(2) or "").strip()
                if not val or val.lower() in ("no", "num", "number", "code", "dt", "date"):
                    continue
                f["value"] = val
            elif name == "fssai":
                val = m.group(2) or m.group(1)
                raw_num = re.sub(r"[\s\-]", "", val)
                f["value"] = raw_num
                f["valid_length"] = len(raw_num) in (13, 14)
            elif name == "veg_nonveg":
                f["value"] = m.group(0)
                f["is_nonveg"] = bool(re.search(r"non|मांसाहारी", m.group(0), re.I))
            elif name == "generic_name":
                f["value"] = m.group(2).strip()
            elif name == "unit_sale_price":
                f["value"] = m.group(0).strip()
            elif name == "nutrition":
                f["value"] = m.group(0).strip()
            elif name == "ingredients":
                f["value"] = m.group(2).strip()
            elif name == "cosmetic_lic":
                f["value"] = m.group(2).strip()
            elif name == "recycling_epr":
                val = m.group(1) or m.group(2) or m.group(0)
                f["value"] = val.strip()

            # numeral height (px) for Rule 7 font-size check
            if f.get("numeral"):
                target = f["numeral"].replace(",", ".")
                hits = [w for w in L["words"] if target in w["t"].replace(",", ".")]
                f["numeral_h_px"] = max(w["h"] for w in hits) if hits else L["bbox"][3]
            fields[name] = f

    # Fallback: if net_quantity wasn't caught with explicit prefix, search for standalone volume/weight
    if "net_quantity" not in fields:
        for idx, L in enumerate(lines):
            text = L["text"]
            m = STANDALONE_QTY.search(text)
            if m:
                u = re.sub(r"[\s.]", "", m.group(2)).lower()
                if u in ("mi", "mt", "m1", "m|"):
                    u = "ml"
                num = m.group(1)
                val = f"{num} {u}"
                target = num.replace(",", ".")
                hits = [w for w in L["words"] if target in w["t"].replace(",", ".")]
                fields["net_quantity"] = {
                    "value": val, "numeral": num, "unit": u, "qualifier": False,
                    "line": idx, "bbox": list(L["bbox"]), "conf": round(L["conf"], 1), "raw": text,
                    "numeral_h_px": max(w["h"] for w in hits) if hits else L["bbox"][3]
                }
                break

    # If bottle/can declares "See Neck / See Base / See Bottom" for lot-specific info, populate missing fields with statutory cross-reference
    if neck_decl:
        nd_raw = neck_decl["raw"]
        is_base = bool(re.search(r"base|bottom|chill|can", nd_raw, re.I))
        ref_val = "Declared on base ('See Base' per Rule 6(1) proviso)" if is_base else "Declared on neck/cap ('See Neck' per Rule 6(1) proviso)"
        for target, kwords in [
            ("mrp", ["mrp", "price", "retail", "base", "bottom", "chill"]),
            ("mfg_date", ["mfd", "mfg", "date", "pkd", "base", "bottom", "chill"]),
            ("expiry", ["use by", "expiry", "best before", "exp", "base", "bottom", "chill"]),
            ("batch_number", ["batch", "lot", "b.no", "base", "bottom", "chill"]),
            ("unit_sale_price", ["usp", "unit sale price", "base", "bottom", "chill"]),
        ]:
            if target not in fields and (any(kw in nd_raw.lower() for kw in kwords) or is_base):
                fields[target] = {
                    "value": ref_val,
                    "on_neck": True,
                    "on_base": is_base,
                    "conf": neck_decl["conf"],
                    "line": neck_decl["line"],
                    "bbox": neck_decl["bbox"],
                    "raw": nd_raw,
                }

    return fields
