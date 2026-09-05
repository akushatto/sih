"""Rule engine – Legal Metrology (Packaged Commodities) Rules, 2011 + FSS Act 2006 (FSSAI)."""
import os

CONF_THRESHOLD = int(os.getenv("CONF_THRESHOLD", "85"))
STD_UNITS = {"g", "gm", "gms", "gram", "grams", "kg", "kgs", "mg", "ml", "l", "ltr", "litre", "liter",
             "किग्रा", "किलो", "किलोग्राम", "ग्राम", "ग्रा", "मिली", "लीटर", "ली"}
FOOD_LIKE = {"FMCG Food", "Grocery Staples"}
PERSONAL_CARE = {"Personal Care"}

# Rule 7 + Second Schedule: min numeral height by Principal Display Panel area
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

    # ── 1. Manufacturer / Packer / Importer — Rule 6(1)(a) ──
    f = fields.get("manufacturer")
    ref = "Rule 6(1)(a) LM(PC) Rules 2011 — Name & complete address of manufacturer / packer / importer"
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

    # ── 2. Net Quantity — Rule 6(1)(c) / Rule 8 ──
    f = fields.get("net_quantity")
    ref = "Rule 6(1)(c) · Rule 8 LM(PC) Rules 2011 — Net quantity in standard units, no qualifying words"
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

    # ── 3. Month & Year of Manufacture — Rule 6(1)(d) ──
    f = fields.get("mfg_date")
    ref = "Rule 6(1)(d) LM(PC) Rules 2011 — Month and year of manufacture / pre-packing / import"
    if not f:
        add("mfg_date", "Month & Year of Manufacture", "bad", ref, "No manufacturing / packing date detected.",
            "<b>Correction:</b> Print 'Mfg. Date: MM/YYYY' (month and year at minimum).", severity="critical")
    else:
        add("mfg_date", "Month & Year of Manufacture", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 4. Retail Sale Price — Rule 6(1)(e) ──
    f = fields.get("mrp")
    ref = "Rule 6(1)(e) LM(PC) Rules 2011 — 'Maximum Retail Price ₹… inclusive of all taxes'"
    if not f:
        add("mrp", "Retail Sale Price (MRP)", "bad", ref, "No MRP declaration detected.",
            "<b>Correction:</b> Print 'MRP ₹<amount> (inclusive of all taxes)'.", severity="critical")
    elif not f.get("incl_taxes"):
        add("mrp", "Retail Sale Price (MRP)", "warn", ref, f"Detected MRP {f['value']} but 'inclusive of all taxes' not found nearby.",
            "<b>Correction:</b> Add the words 'inclusive of all taxes' with the MRP.", f=f)
    else:
        add("mrp", "Retail Sale Price (MRP)", "ok", ref, f"Detected MRP {f['value']} (inclusive of all taxes).", f=f)
    font_check("mrp", "MRP", f)

    # ── 5. Consumer Care — Rule 6(1)(f) ──
    f = fields.get("consumer_care")
    ref = "Rule 6(1)(f) LM(PC) Rules 2011 — Name, address, telephone / e-mail for consumer complaints"
    if not f:
        add("consumer_care", "Consumer Care Details", "bad", ref,
            "No consumer-care telephone / e-mail / address detected on visible panels.",
            "<b>Correction:</b> Add 'Consumer Care: <phone>, <e-mail>, <address>' on any panel.")
    else:
        add("consumer_care", "Consumer Care Details", "ok", ref, f"Detected: {f['value'][:110]}", f=f)

    # ── 6. Batch / Lot Number — Rule 6(2) ──
    f = fields.get("batch_number")
    ref = "Rule 6(2) LM(PC) Rules 2011 — Batch number / Lot number / Code number mandatory"
    if not f:
        add("batch_number", "Batch / Lot Number", "warn", ref,
            "No batch / lot / code number detected.",
            "<b>Correction:</b> Print 'Batch No.: XXXX' or 'Lot No.: XXXX' on the package.")
    else:
        add("batch_number", "Batch / Lot Number", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 7. FSSAI License Number — FSS Act 2006, Reg. 2.2.2 ──
    f = fields.get("fssai")
    ref = "FSS Act 2006 · FSSAI Reg. 2.2.2 — 14-digit FSSAI license/registration number mandatory for food products"
    if category in FOOD_LIKE:
        if not f:
            add("fssai", "FSSAI License / Reg. Number", "bad", ref,
                "No FSSAI license or registration number detected — mandatory for all food products.",
                "<b>Correction:</b> Print 'FSSAI Lic. No.: <14-digit number>' on the label.",
                severity="critical")
        elif not f.get("valid_length"):
            add("fssai", "FSSAI License / Reg. Number", "warn", ref,
                f"Detected number '{f['value']}' but FSSAI numbers must be 13–14 digits.",
                "<b>Action:</b> Verify the FSSAI license/registration number is complete.", f=f)
        else:
            add("fssai", "FSSAI License / Reg. Number", "ok", ref,
                f"Detected FSSAI number: {f['value']}", f=f)
    elif f:
        add("fssai", "FSSAI License / Reg. Number", "ok", ref,
            f"Detected: {f['value']}", f=f)

    # ── 8. Veg / Non-Veg Symbol — FSSAI Food Safety & Standards (Labelling) Reg. 2011 ──
    f = fields.get("veg_nonveg")
    ref = "FSSAI Food Safety & Standards (Labelling & Display) Regs. 2020 — Green dot (veg) / Brown dot (non-veg) mandatory"
    if category in FOOD_LIKE:
        if not f:
            add("veg_nonveg", "Veg / Non-Veg Declaration", "warn", ref,
                "No vegetarian / non-vegetarian declaration detected — mandatory for packaged food.",
                "<b>Correction:</b> Print green filled circle ● for vegetarian OR brown/red filled circle ● for non-vegetarian on the PDP.")
        elif f.get("is_nonveg"):
            add("veg_nonveg", "Veg / Non-Veg Declaration", "ok", ref,
                f"Non-vegetarian declaration detected: '{f['value']}'. Ensure brown/red dot symbol is present.", f=f)
        else:
            add("veg_nonveg", "Veg / Non-Veg Declaration", "ok", ref,
                f"Vegetarian declaration detected: '{f['value']}'. Ensure green dot symbol is present.", f=f)

    # ── 9. Expiry / Best Before ──
    f = fields.get("expiry")
    ref = "Rule 6(1)(d) proviso LM(PC) Rules 2011 + FSSAI Reg. 2.1.5 — Best before / Use by date"
    if f:
        add("expiry", "Expiry / Best Before", "ok", ref, f"Detected: {f['value']}", f=f)
    elif category in FOOD_LIKE | PERSONAL_CARE:
        add("expiry", "Expiry / Best Before", "warn", ref,
            "No 'Best before / Use by / Expiry' found — required for this category.",
            "<b>Correction:</b> Add 'Best before <n> months from manufacture' or an expiry date.", severity="minor")

    # ── 10. Country of Origin — imported packages, Rule 6(1)(a) proviso ──
    f = fields.get("country_of_origin")
    ref = "Rule 6(1)(a) proviso LM(PC) Rules 2011 — Country of origin mandatory for imported packages"
    imported = "import" in ft or "आयात" in ft
    if f:
        add("country_of_origin", "Country of Origin", "ok", ref, f"Detected: {f['value']}", f=f)
    elif imported:
        add("country_of_origin", "Country of Origin", "bad", ref,
            "Package indicates import but no country of origin found.",
            "<b>Correction:</b> Declare 'Country of Origin: <country>'.", severity="critical")
    else:
        add("country_of_origin", "Country of Origin", "info", ref,
            "Not detected — not applicable unless the package is imported.")

    # ── 11. Generic / Common Name — Rule 6(1)(b) LM(PC) Rules 2011 & FSSAI Reg. 5(1) ──
    f = fields.get("generic_name")
    ref = "Rule 6(1)(b) LM(PC) Rules 2011 · FSSAI Reg. 5(1) — Common / generic name of commodity on PDP"
    if f:
        add("generic_name", "Generic / Commodity Name", "ok", ref, f"Detected generic name: '{f['value']}'", f=f)
    else:
        add("generic_name", "Generic / Commodity Name", "warn", ref,
            "No explicit 'Generic Name / Common Name' prefix detected on visible panels.",
            "<b>Correction:</b> Clearly declare the common/generic name of the commodity (e.g. 'Pure Ghee', 'Shampoo', 'Biscuits') on the Principal Display Panel.",
            severity="minor")

    # ── 12. Unit Sale Price (USP) — Rule 6(1)(e) (2022 Amendment) LM(PC) Rules ──
    f = fields.get("unit_sale_price")
    ref = "Rule 6(1)(e) (2022 Amendment) LM(PC) Rules 2011 — Unit Sale Price (₹/g, ₹/ml, ₹/kg, ₹/L) mandatory"
    if f:
        add("unit_sale_price", "Unit Sale Price (USP)", "ok", ref, f"Detected: {f['value']}", f=f)
    elif fields.get("mrp") and fields.get("net_quantity"):
        add("unit_sale_price", "Unit Sale Price (USP)", "warn", ref,
            "Unit Sale Price (₹/g, ₹/ml, ₹/kg, ₹/L) not detected alongside MRP.",
            "<b>Correction:</b> Print Unit Sale Price (e.g. '₹ 0.50 / g' or '₹ 1.20 / ml') mandatory under LM(PC) 2022 Amendment.")
    else:
        add("unit_sale_price", "Unit Sale Price (USP)", "info", ref,
            "Unit Sale Price required where package contains more than 1 unit/g/ml.")

    # ── 13. Nutritional Information — FSSAI (Labelling & Display) Regs. 2020, Reg. 5(3) ──
    f = fields.get("nutrition")
    ref = "FSSAI (Labelling & Display) Regs. 2020 Reg. 5(3) — Nutritional info (Energy, Protein, Carbs, Fats) per 100g/ml"
    if category in FOOD_LIKE:
        if f:
            add("nutrition", "Nutritional Information Panel", "ok", ref, f"Detected: {f['value']}", f=f)
        else:
            add("nutrition", "Nutritional Information Panel", "warn", ref,
                "Nutritional Information panel (Energy, Protein, Carbs, Sugars, Fat) not detected.",
                "<b>Correction:</b> Print mandatory nutritional facts table per 100g/ml or per serve.", severity="minor")
    elif f:
        add("nutrition", "Nutritional Information Panel", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 14. Ingredients List — FSSAI Reg. 5(2) & Cosmetics Rules 2020 Rule 34 ──
    f = fields.get("ingredients")
    ref = "FSSAI Reg. 5(2) · Cosmetics Rules 2020 Rule 34 — Complete list of ingredients in descending order"
    if category in FOOD_LIKE | PERSONAL_CARE:
        if f:
            add("ingredients", "Ingredients Declaration", "ok", ref, f"Detected ingredients: {f['value'][:100]}", f=f)
        else:
            add("ingredients", "Ingredients Declaration", "warn", ref,
                "No 'Ingredients / Contents' declaration detected.",
                "<b>Correction:</b> Add 'Ingredients: ...' listed in descending order of ingoing weight/volume.", severity="minor")
    elif f:
        add("ingredients", "Ingredients Declaration", "ok", ref, f"Detected: {f['value'][:100]}", f=f)

    # ── 15. Cosmetic Manufacturing License — Cosmetics Rules, 2020 ──
    f = fields.get("cosmetic_lic")
    ref = "Cosmetics Rules, 2020 (Drugs & Cosmetics Act, 1940) — Manufacturing License Number (M.L. No.)"
    if category in PERSONAL_CARE:
        if f:
            add("cosmetic_lic", "Cosmetic Mfg. License (M.L. No.)", "ok", ref, f"Detected License: {f['value']}", f=f)
        else:
            add("cosmetic_lic", "Cosmetic Mfg. License (M.L. No.)", "bad", ref,
                "No Cosmetic Manufacturing License ('Mfg. Lic. No.' / 'M.L. No.') detected — mandatory for cosmetics.",
                "<b>Correction:</b> Print State Licensing Authority manufacturing license number on personal care packaging.",
                severity="critical")

    # ── 16. Plastic Waste Management & EPR — PWM Rules 2016, Rule 11 ──
    f = fields.get("recycling_epr")
    ref = "Plastic Waste Management Rules 2016 (Amended 2022) Rule 11 — Recyclability mark & CPCB/SPCB EPR registration"
    if f:
        add("recycling_epr", "Plastic Waste & Recyclability / EPR", "ok", ref, f"Detected: {f['value']}", f=f)
    elif "plastic" in ft or "pet" in ft or "hdpe" in ft:
        add("recycling_epr", "Plastic Waste & Recyclability / EPR", "warn", ref,
            "Plastic packaging indicated but no recyclability symbol or EPR registration number detected.",
            "<b>Correction:</b> Print plastic resin code symbol and EPR Registration Number issued by CPCB.")
    else:
        add("recycling_epr", "Plastic Waste & Recyclability / EPR", "info", ref,
            "Not detected — mandatory for plastic packaging under PWM Rules 2016.")

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
