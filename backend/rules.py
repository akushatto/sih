"""Rule engine – Legal Metrology (Packaged Commodities) Rules, 2011."""
import os

CONF_THRESHOLD = int(os.getenv("CONF_THRESHOLD", "85"))
STD_UNITS = {"g", "gm", "gms", "gram", "grams", "kg", "kgs", "mg", "ml", "l", "ltr", "litre", "liter",
             "किग्रा", "किलो", "किलोग्राम", "ग्राम", "ग्रा", "मिली", "लीटर", "ली"}
FOOD_LIKE = {"FMCG Food", "Grocery Staples", "Personal Care"}

# Rule 7 + Second Schedule (printed labels): min numeral height by Principal Display Panel area
_MIN_H = [(100, 1.0), (500, 2.0), (2500, 4.0), (float("inf"), 6.0)]


def min_height_mm(pdp_cm2: float) -> float:
    return next(h for lim, h in _MIN_H if pdp_cm2 <= lim)


def evaluate(fields: dict, scale: dict | None, category: str, full_text: str = "") -> list:
    C = []
    ft = full_text.lower()

    def add(key, name, s, ref, found, fix=None, measure=None, f=None, severity="major"):
        c = {"key": key, "name": name, "s": s, "severity": severity, "ref": ref, "found": found,
             "fix": fix, "measure": measure, "bbox": f["bbox"] if f else None,
             "conf": f"{f['conf']:.0f}%" if f else "—"}
        if s == "ok" and f and f["conf"] < CONF_THRESHOLD:
            c["s"] = "warn"
            c["found"] += f" OCR confidence {f['conf']:.0f}% is below the {CONF_THRESHOLD}% auto-approve threshold — routed to human sign-off."
            c["fix"] = c["fix"] or "<b>Action:</b> Inspector confirms this field. No label change needed if verified."
        C.append(c)

    def font_check(key, label, f):
        if not f or not f.get("numeral_h_px") or not scale:
            return
        h_mm = f["numeral_h_px"] * scale["mm_per_px"]
        req = min_height_mm(scale["pdp_cm2"])
        note = " (scale assumed from category default — enter pack width for exact measurement)" if scale.get("assumed") else ""
        meas = [f"Measured: {h_mm:.2f} mm", f"Required: ≥ {req:.1f} mm", f"PDP ≈ {scale['pdp_cm2']} cm²"]
        ref = "Rule 7 + Second Schedule — minimum letter/numeral height by PDP area" + note
        if h_mm < req * 0.95:
            add(key + "_font", f"{label} — Numeral Height", "bad", ref,
                f"{label} numerals measured at {h_mm:.2f} mm; PDP area ≈ {scale['pdp_cm2']} cm² requires ≥ {req:.1f} mm.",
                f"<b>Correction:</b> Increase {label} numeral height to ≥ {req:.1f} mm (recommended {req * 1.2:.1f} mm), width ≥ ⅓ of height.",
                meas, f)
        else:
            add(key + "_font", f"{label} — Numeral Height", "ok", ref,
                f"{label} numerals ≈ {h_mm:.2f} mm ≥ required {req:.1f} mm.", None, meas, f)

    # 1. Manufacturer / Packer / Importer — Rule 6(1)(a)
    f = fields.get("manufacturer")
    ref = "Rule 6(1)(a) — Name & complete address of manufacturer / packer / importer"
    if not f:
        add("manufacturer", "Manufacturer / Packer Details", "bad", ref,
            "No 'Mfd by / Pkd by / Marketed by' declaration detected on visible panels.",
            "<b>Correction:</b> Add name and complete address (with PIN code) of the manufacturer / packer / importer.",
            severity="critical")
    elif not f.get("has_pin"):
        add("manufacturer", "Manufacturer / Packer Details", "warn", ref,
            f"Detected: {f['value'][:100]}. No 6-digit PIN code found — address may be incomplete.",
            "<b>Action:</b> Verify 'complete address' (Rule 2(e)) — include PIN code.", f=f)
    else:
        add("manufacturer", "Manufacturer / Packer Details", "ok", ref, f"Detected: {f['value'][:120]}", f=f)

    # 2. Net Quantity — Rule 6(1)(c) / Rule 8
    f = fields.get("net_quantity")
    ref = "Rule 6(1)(c) · Rule 8 — Net quantity in standard units, no qualifying words"
    if not f:
        add("net_quantity", "Net Quantity", "bad", ref, "No net quantity declaration detected.",
            "<b>Correction:</b> Declare 'Net Quantity: <value> <standard unit>' (g / kg / ml / L) on the principal display panel.",
            severity="critical")
    elif f.get("unit") not in STD_UNITS:
        add("net_quantity", "Net Quantity", "bad", ref, f"Detected '{f['value']}' — unit '{f['unit']}' is not a standard SI unit.",
            "<b>Correction:</b> Use standard units only (g, kg, ml, L).", f=f)
    elif f.get("qualifier"):
        add("net_quantity", "Net Quantity", "bad", ref, f"Detected '{f['value']}' with qualifying words (approx./minimum).",
            "<b>Correction:</b> Remove qualifying words such as 'approx.', 'about', 'minimum'.", f=f)
    else:
        add("net_quantity", "Net Quantity", "ok", ref, f"Detected '{f['value']}' — standard unit, no qualifying words.", f=f)
    font_check("net_quantity", "Net Quantity", f)

    # 3. Month & Year of Manufacture — Rule 6(1)(d)
    f = fields.get("mfg_date")
    ref = "Rule 6(1)(d) — Month and year of manufacture / pre-packing / import"
    if not f:
        add("mfg_date", "Month & Year of Manufacture", "bad", ref, "No manufacturing / packing date detected.",
            "<b>Correction:</b> Print 'Mfg. Date: MM/YYYY' (month and year at minimum).", severity="critical")
    else:
        add("mfg_date", "Month & Year of Manufacture", "ok", ref, f"Detected: {f['value']}", f=f)

    # 4. Retail Sale Price — Rule 6(1)(e)
    f = fields.get("mrp")
    ref = "Rule 6(1)(e) — 'Maximum Retail Price ₹… inclusive of all taxes'"
    if not f:
        add("mrp", "Retail Sale Price (MRP)", "bad", ref, "No MRP declaration detected.",
            "<b>Correction:</b> Print 'MRP ₹<amount> (inclusive of all taxes)'.", severity="critical")
    elif not f.get("incl_taxes"):
        add("mrp", "Retail Sale Price (MRP)", "warn", ref, f"Detected MRP {f['value']} but 'inclusive of all taxes' not found nearby.",
            "<b>Correction:</b> Add the words 'inclusive of all taxes' with the MRP.", f=f)
    else:
        add("mrp", "Retail Sale Price (MRP)", "ok", ref, f"Detected MRP {f['value']} (inclusive of all taxes).", f=f)
    font_check("mrp", "MRP", f)

    # 5. Consumer care — Rule 6(1)(f)
    f = fields.get("consumer_care")
    ref = "Rule 6(1)(f) — Name, address, telephone number, e-mail of the person/office to be contacted for complaints"
    if not f:
        add("consumer_care", "Consumer Care Details", "bad", ref,
            "No consumer-care telephone / e-mail / address detected on visible panels.",
            "<b>Correction:</b> Add 'Consumer Care: <phone>, <e-mail>, <address>' on any panel.")
    else:
        add("consumer_care", "Consumer Care Details", "ok", ref, f"Detected: {f['value'][:110]}", f=f)

    # 6. Expiry / Best Before (sector regs; LM cross-check)
    f = fields.get("expiry")
    ref = "Rule 6(1)(d) proviso + FSSAI Labelling Regs (food) / D&C Rules (cosmetics) — Best before / Use by"
    if f:
        add("expiry", "Expiry / Best Before", "ok", ref, f"Detected: {f['value']}", f=f)
    elif category in FOOD_LIKE:
        add("expiry", "Expiry / Best Before", "warn", ref, "No 'Best before / Use by / Expiry' found — required for this category.",
            "<b>Correction:</b> Add 'Best before <n> months from manufacture' or an expiry date.", severity="minor")

    # 7. Country of origin — imported packages
    f = fields.get("country_of_origin")
    ref = "Rule 6(1)(a) proviso — Country of origin (mandatory for imported packages)"
    imported = "import" in ft or "आयात" in ft
    if f:
        add("country_of_origin", "Country of Origin", "ok", ref, f"Detected: {f['value']}", f=f)
    elif imported:
        add("country_of_origin", "Country of Origin", "bad", ref, "Package indicates import but no country of origin found.",
            "<b>Correction:</b> Declare 'Country of Origin: <country>'.", severity="critical")
    else:
        add("country_of_origin", "Country of Origin", "info", ref, "Not detected — not applicable unless the package is imported.")

    return C


def summarize(checks: list) -> dict:
    scored = [c for c in checks if c["s"] in ("ok", "warn", "bad")]
    pts = sum(1 if c["s"] == "ok" else 0.5 if c["s"] == "warn" else 0 for c in scored)
    score = round(100 * pts / max(1, len(scored)))
    ok = sum(c["s"] == "ok" for c in checks)
    warn = sum(c["s"] == "warn" for c in checks)
    bad = sum(c["s"] == "bad" for c in checks)
    critical = any(c["s"] == "bad" and c.get("severity") == "critical" for c in checks)
    status = "Non-Compliant" if (critical or score < 60) else "Needs Review" if (bad or warn) else "Compliant"
    return {"score": score, "status": status, "counts": {"ok": ok, "warn": warn, "bad": bad}, "violations": bad}
    