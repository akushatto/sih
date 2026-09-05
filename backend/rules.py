"""
Rule engine — Legal Metrology (Packaged Commodities) Rules, 2011 + FSS Act 2006 (FSSAI).

Every citation below is checked against the actual notified text of GSR 202(E),
7 March 2011 ("The Legal Metrology (Packaged Commodities) Rules, 2011").
Where a requirement comes from a different law (FSSAI food labelling, veg/non-veg
symbol) that is called out explicitly in the `ref` string — it is NOT part of the
LM(PC) Rules 2011 itself.
"""
import os

CONF_THRESHOLD = int(os.getenv("CONF_THRESHOLD", "85"))

FOOD_LIKE = {"FMCG Food", "Grocery Staples"}
PERSONAL_CARE = {"Personal Care"}

# ── Unit table: every recognised unit -> (base unit family, multiplier to base) ──
# Weight family is normalised to grams, volume family to millilitres, per Rule 13.
_WEIGHT_UNITS = {
    "g": 1, "gm": 1, "gms": 1, "gram": 1, "grams": 1, "mg": 0.001, "kg": 1000, "kgs": 1000,
    "ग्राम": 1, "ग्रा": 1, "किग्रा": 1000, "किलो": 1000, "किलोग्राम": 1000,
}
_VOLUME_UNITS = {
    "ml": 1, "l": 1000, "ltr": 1000, "litre": 1000, "liter": 1000,
    "मिली": 1, "लीटर": 1000, "ली": 1000,
}
STD_UNITS = set(_WEIGHT_UNITS) | set(_VOLUME_UNITS)


def to_base_qty(numeral: str, unit: str):
    """Rule 13 — convert a declared numeral+unit to (value, family) in base grams/millilitres.
    Returns None if the unit isn't a recognised standard unit."""
    try:
        val = float(str(numeral).replace(",", "."))
    except (TypeError, ValueError):
        return None
    u = (unit or "").strip().lower()
    if u in _WEIGHT_UNITS:
        return val * _WEIGHT_UNITS[u], "weight"
    if u in _VOLUME_UNITS:
        return val * _VOLUME_UNITS[u], "volume"
    return None


# ── Rule 7(2) + Table I — numeral height when net quantity is declared by WEIGHT/VOLUME ──
# (Sl. 1-3 of Table I, First column values only — "normal case" height in mm)
_TABLE_I = [(200, 1.0), (500, 2.0), (float("inf"), 4.0)]


def table_i_height_mm(qty_base: float) -> float:
    return next(h for lim, h in _TABLE_I if qty_base <= lim)


# ── Rule 7(2) + Table II — numeral height when net quantity is declared by LENGTH/AREA/NUMBER ──
# (keyed to Principal Display Panel area in cm², "normal case" column)
_TABLE_II = [(100, 1.0), (500, 2.0), (2500, 4.0), (float("inf"), 6.0)]


def table_ii_height_mm(pdp_cm2: float) -> float:
    return next(h for lim, h in _TABLE_II if pdp_cm2 <= lim)


def required_numeral_height_mm(qty_base, qty_family, pdp_cm2: float | None):
    """Rule 7(2): pick Table I or Table II depending on how net quantity is declared."""
    if qty_base is not None and qty_family in ("weight", "volume"):
        return table_i_height_mm(qty_base), "Table-I (net quantity by weight/volume)"
    if pdp_cm2:
        return table_ii_height_mm(pdp_cm2), "Table-II (net quantity by length/area/number, keyed to PDP area)"
    return 1.0, "Rule 7(3) floor (no PDP/quantity basis available)"


# ── Rule 26 — packages exempt from Chapter II declarations ──
def exemption_status(qty_base, qty_family):
    """Rule 26(a) + proviso: <=10 g/ml -> fully exempt from Chapter II;
    10-20 g/ml -> exempt EXCEPT retail sale price and net quantity remain mandatory."""
    if qty_base is None or qty_family not in ("weight", "volume"):
        return "normal"
    if qty_base <= 10:
        return "full_exempt"
    if qty_base <= 20:
        return "partial_exempt"
    return "normal"


def bulk_exclusion(qty_base, qty_family) -> bool:
    """Rule 3(a): Chapter II (this whole checklist) does not apply to packages
    of more than 25 kg / 25 litre (cement & fertiliser bags up to 50 kg excluded from this cap)."""
    return qty_family in ("weight", "volume") and qty_base is not None and qty_base > 25000


def evaluate(fields: dict, scale: dict | None, category: str, full_text: str = "", product_name: str | None = None) -> list:
    C = []
    ft = full_text.lower()

    def add(key, name, s, ref, found, fix=None, measure=None, f=None, severity="major"):
        c = {"key": key, "name": name, "s": s, "severity": severity, "ref": ref, "found": found,
             "fix": fix, "measure": measure, "bbox": f.get("bbox") if f else None,
             "conf": f"{f.get('conf', 0):.0f}%" if (f and 'conf' in f) else "—"}
        if s == "ok" and f and f.get("conf", 100) < CONF_THRESHOLD:
            c["s"] = "warn"
            c["found"] += f" OCR confidence {f['conf']:.0f}% is below the {CONF_THRESHOLD}% auto-approve threshold — routed to human sign-off."
            c["fix"] = c["fix"] or "<b>Action:</b> Inspector confirms this field. No label change needed if verified."
        C.append(c)

    def font_check(key, label, f, qty_base, qty_family):
        if not f or f.get("on_neck") or not f.get("numeral_h_px") or not scale:
            return
        h_mm = f["numeral_h_px"] * scale["mm_per_px"]
        req, table_used = required_numeral_height_mm(qty_base, qty_family, scale.get("pdp_cm2"))
        note = " (scale assumed from category default — enter pack width for exact measurement)" if scale.get("assumed") else ""
        meas = [f"Measured: {h_mm:.2f} mm", f"Required: ≥ {req:.1f} mm", f"Basis: {table_used}"]
        ref = f"Rule 7(2)+(3) LM(PC) Rules 2011 — minimum numeral height, {table_used}" + note
        if h_mm < req * 0.95:
            add(key + "_font", f"{label} — Numeral Height", "bad", ref,
                f"{label} numerals measured at {h_mm:.2f} mm; required ≥ {req:.1f} mm ({table_used}).",
                f"<b>Correction:</b> Increase {label} numeral height to ≥ {req:.1f} mm (recommended {req * 1.2:.1f} mm); "
                f"width must be ≥ ⅓ of height except for numeral '1' (Rule 7(3) proviso).",
                meas, f)
        else:
            add(key + "_font", f"{label} — Numeral Height", "ok", ref,
                f"{label} numerals ≈ {h_mm:.2f} mm ≥ required {req:.1f} mm ({table_used}).", None, meas, f)

    # ── Net Quantity first — everything else's applicability under Chapter II depends on it ──
    nq = fields.get("net_quantity")
    qty_base = qty_family = None
    if nq and nq.get("numeral") is not None:
        conv = to_base_qty(nq["numeral"], nq.get("unit"))
        if conv:
            qty_base, qty_family = conv

    if bulk_exclusion(qty_base, qty_family):
        add("applicability", "Chapter II Applicability", "info",
            "Rule 3(a) LM(PC) Rules 2011 — Chapter II does not apply to packages > 25 kg / 25 litre",
            f"Net quantity {nq['value']} exceeds the 25 kg/25 L retail-package threshold — "
            "this appears to be a bulk/wholesale package; Chapter II retail declarations are not mandatory "
            "(Chapter III wholesale-package rules apply instead).")
        return C  # nothing further to check under the retail-package chapter

    exemption = exemption_status(qty_base, qty_family)
    if exemption == "full_exempt":
        add("applicability", "Chapter II Applicability", "info",
            "Rule 26(a) LM(PC) Rules 2011 — packages of 10 g/10 ml or less are exempt",
            f"Net quantity {nq['value']} is at or below the 10 g/10 ml exemption threshold — "
            "this package is exempt from Chapter II declarations.")
        # FSSAI / veg-nonveg obligations still apply below — they come from the FSS Act, not LM(PC) Rules.

    # ── 1. Manufacturer / Packer / Importer — Rule 6(1)(a) + Rule 10(1) Explanation ──
    if exemption == "normal":
        f = fields.get("manufacturer")
        ref = "Rule 6(1)(a) · Rule 10(1) Explanation LM(PC) Rules 2011 — Name & complete address of manufacturer / packer / importer"
        if not f:
            add("manufacturer", "Manufacturer / Packer Details", "bad", ref,
                "No 'Mfd by / Pkd by / Marketed by' declaration detected on visible panels.",
                "<b>Correction:</b> Add name and complete address of the manufacturer / packer / importer.",
                severity="critical")
        elif not f.get("has_pin"):
            add("manufacturer", "Manufacturer / Packer Details", "warn", ref,
                f"Detected: {f['value'][:100]}. No 6-digit PIN code found — 'complete address' under Rule 10(1) "
                "Explanation is satisfied by street+city/state OR PIN, but PIN is the clearest identifier.",
                "<b>Action:</b> Verify the address enables the consumer to locate the manufacturer/packer/importer.", f=f)
        else:
            add("manufacturer", "Manufacturer / Packer Details", "ok", ref, f"Detected: {f['value'][:120]}", f=f)

    # ── 2. Common / Generic Name of Commodity — Rule 6(1)(b) ──
    if exemption == "normal":
        ref = "Rule 6(1)(b) LM(PC) Rules 2011 — Common or generic name of the commodity"
        if product_name:
            add("commodity_name", "Common / Generic Name", "ok", ref, f"Detected product name: {product_name}")
        else:
            add("commodity_name", "Common / Generic Name", "info", ref,
                "Automated name/OCR detection not conclusive — verify the common or generic name of the "
                "commodity is legibly declared on the principal display panel.", severity="minor")

    # ── 3. Net Quantity — Rule 6(1)(c) · Rule 12 (unit) · Rule 12(6) (no qualifying words) ──
    f = nq
    ref_base = "Rule 6(1)(c) LM(PC) Rules 2011 — Net quantity in standard units"
    if not f:
        add("net_quantity", "Net Quantity", "bad", ref_base, "No net quantity declaration detected.",
            "<b>Correction:</b> Declare 'Net Quantity: <value> <standard unit>' (g / kg / ml / L) on the principal display panel.",
            severity="critical")
    elif qty_base is None:
        add("net_quantity", "Net Quantity", "bad", "Rule 13 LM(PC) Rules 2011 — Statement of units",
            f"Detected '{f['value']}' — unit '{f.get('unit')}' is not a standard SI unit under Rule 13.",
            "<b>Correction:</b> Use standard units only (g, kg, ml, L) per Rule 13.", f=f)
    elif f.get("qualifier"):
        add("net_quantity", "Net Quantity", "bad", "Rule 12(6) LM(PC) Rules 2011 — No qualifying/exaggerating words",
            f"Detected '{f['value']}' with qualifying words (approx./minimum/about etc.), prohibited by Rule 12(6).",
            "<b>Correction:</b> Remove qualifying words such as 'approx.', 'about', 'minimum', 'not less than'.", f=f)
    else:
        add("net_quantity", "Net Quantity", "ok", ref_base, f"Detected '{f['value']}' — standard unit, no qualifying words.", f=f)
    font_check("net_quantity", "Net Quantity", f, qty_base, qty_family)

    # ── 4. Month & Year of Manufacture — Rule 6(1)(d) ──
    # Rule 26 proviso: only MRP + net quantity are mandatory for 10-20 g/ml packages, so this
    # (like manufacturer/consumer-care/batch) is skipped for both full_exempt and partial_exempt.
    if exemption == "normal":
        f = fields.get("mfg_date")
        ref = "Rule 6(1)(d) LM(PC) Rules 2011 — Month and year of manufacture / pre-packing / import"
        if not f:
            add("mfg_date", "Month & Year of Manufacture", "bad", ref, "No manufacturing / packing date detected.",
                "<b>Correction:</b> Print 'Mfg. Date: MM/YYYY' (month and year at minimum).", severity="critical")
        elif f.get("on_neck"):
            add("mfg_date", "Month & Year of Manufacture", "ok", ref,
                f"{f['value']} — statutory cross-reference on label; inspect neck/cap for printed stamp (Rule 6(1) proviso).", f=f)
        else:
            add("mfg_date", "Month & Year of Manufacture", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 5. Retail Sale Price / MRP — Rule 6(1)(e) · Rule 2(m) (format & rounding) ──
    f = fields.get("mrp")
    ref = "Rule 6(1)(e) · Rule 2(m) LM(PC) Rules 2011 — 'Maximum Retail Price ₹… inclusive of all taxes'"
    if not f:
        add("mrp", "Retail Sale Price (MRP)", "bad", ref, "No MRP declaration detected.",
            "<b>Correction:</b> Print 'MRP ₹<amount> (inclusive of all taxes)' per Rule 2(m).", severity="critical")
    elif f.get("on_neck"):
        add("mrp", "Retail Sale Price (MRP)", "ok", ref,
            f"{f['value']} — statutory cross-reference on label; inspect neck/cap for printed stamp (Rule 6(1) proviso).", f=f)
    elif not f.get("incl_taxes"):
        add("mrp", "Retail Sale Price (MRP)", "warn", ref, f"Detected MRP {f['value']} but 'inclusive of all taxes' not found nearby.",
            "<b>Correction:</b> Add the words 'inclusive of all taxes' with the MRP, per Rule 2(m).", f=f)
    else:
        add("mrp", "Retail Sale Price (MRP)", "ok", ref, f"Detected MRP {f['value']} (inclusive of all taxes).", f=f)
    font_check("mrp", "MRP", f, qty_base, qty_family)

    # ── 6. Consumer Care — Rule 6(2) (NOT 6(1)(f), which is about commodity dimensions) ──
    if exemption == "normal":
        f = fields.get("consumer_care")
        ref = "Rule 6(2) LM(PC) Rules 2011 — Name, address, telephone / e-mail for consumer complaints"
        if not f:
            add("consumer_care", "Consumer Care Details", "bad", ref,
                "No consumer-care telephone / e-mail / address detected on visible panels.",
                "<b>Correction:</b> Add 'Consumer Care: <phone>, <e-mail>, <address>' on any panel.")
        else:
            add("consumer_care", "Consumer Care Details", "ok", ref, f"Detected: {f['value'][:110]}", f=f)

    # ── 7. Batch / Lot Number — Rule 6(2) / traceability ──
    if exemption == "normal":
        f = fields.get("batch_number")
        ref = "Rule 6(2) LM(PC) Rules 2011 / BIS Norms — Batch / Lot / Code Number for traceability"
        if not f:
            add("batch_number", "Batch / Lot Number", "warn", ref,
                "No batch / lot / code number detected.",
                "<b>Correction:</b> Print 'Batch No.: XXXX' or 'Lot No.: XXXX' on the package for traceability.",
                severity="minor")
        elif f.get("on_neck"):
            add("batch_number", "Batch / Lot Number", "ok", ref,
                f"{f['value']} — statutory cross-reference on label; inspect neck/cap for printed stamp.", f=f)
        else:
            add("batch_number", "Batch / Lot Number", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 8. FSSAI License Number — FSS Act 2006, Reg. 2.2.2 (independent of LM(PC) exemption) ──
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
        add("fssai", "FSSAI License / Reg. Number", "ok", ref, f"Detected: {f['value']}", f=f)

    # ── 9. Veg / Non-Veg Symbol — FSSAI Food Safety & Standards (Labelling & Display) Regs. 2020 ──
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

    # ── 10. Expiry / Best Before — Rule 6(1)(d) proviso (food) + FSSAI Reg. 2.1.5 ──
    f = fields.get("expiry")
    ref = "Rule 6(1)(d) proviso LM(PC) Rules 2011 + FSSAI Reg. 2.1.5 — Best before / Use by date"
    if f and f.get("on_neck"):
        add("expiry", "Expiry / Best Before", "ok", ref,
            f"{f['value']} — statutory cross-reference on label; inspect neck/cap for printed stamp.", f=f)
    elif f:
        add("expiry", "Expiry / Best Before", "ok", ref, f"Detected: {f['value']}", f=f)
    elif category in FOOD_LIKE | PERSONAL_CARE:
        add("expiry", "Expiry / Best Before", "warn", ref,
            "No 'Best before / Use by / Expiry' found — required for this category.",
            "<b>Correction:</b> Add 'Best before <n> months from manufacture' or an expiry date.", severity="minor")

    # ── 11. Country of Origin — Rule 6(1)(a) proviso (imported packages) ──
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

    # ── 12. Unit Sale Price (USP) — Rule 6(1)(e) (2022 Amendment, GSR 779(E)) LM(PC) Rules ──
    f = fields.get("unit_sale_price")
    ref = "Rule 6(1)(e) (2022 Amendment, GSR 779(E)) LM(PC) Rules 2011 — Unit Sale Price (₹/g, ₹/ml, ₹/kg, ₹/L) mandatory"
    if f and f.get("on_neck"):
        add("unit_sale_price", "Unit Sale Price (USP)", "ok", ref,
            f"{f['value']} — statutory cross-reference on label; inspect neck/cap for printed stamp (Rule 6(1) proviso).", f=f)
    elif f:
        add("unit_sale_price", "Unit Sale Price (USP)", "ok", ref, f"Detected: {f['value']}", f=f)
    elif fields.get("mrp") and fields.get("net_quantity"):
        add("unit_sale_price", "Unit Sale Price (USP)", "warn", ref,
            "Unit Sale Price (₹/g, ₹/ml, ₹/kg, ₹/L) not detected alongside MRP.",
            "<b>Correction:</b> Print Unit Sale Price (e.g. '₹ 0.50 / ml' or '₹ 1.20 / g') mandatory under LM(PC) 2022 Amendment.")
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
    elif f:
        add("cosmetic_lic", "Cosmetic Mfg. License (M.L. No.)", "ok", ref, f"Detected License: {f['value']}", f=f)

    # ── 16. Plastic Waste Management & EPR — PWM Rules 2016, Rule 11 ──
    f = fields.get("recycling_epr")
    ref = "Plastic Waste Management Rules 2016 (Amended 2022) Rule 11 — Recyclability mark & CPCB/SPCB EPR registration"
    if f:
        add("recycling_epr", "Plastic Waste & Recyclability / EPR", "ok", ref, f"Detected: {f['value']}", f=f)
    elif "plastic" in ft or "pet" in ft or "hdpe" in ft or "pwm" in ft or "bottle" in ft:
        add("recycling_epr", "Plastic Waste & Recyclability / EPR", "warn", ref,
            "Plastic packaging indicated but no recyclability symbol or CPCB EPR registration number detected.",
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