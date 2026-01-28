import streamlit as st
import requests
import xml.etree.ElementTree as ET
import json
import os

# ---------------------------
# Config
# ---------------------------
CONFIG_FILE = "tax_config.json"
ADMIN_PASSWORD = "i4ipapa"

DEFAULT_CONFIG = {
    "vat_uk_percent": 20.0,
    "duty_percent": 10.0,
    "vat_cy_percent": 19.0,
    "mot": 60.0,
    "plates": 40.0,
}

# ---------------------------
# Helpers
# ---------------------------
def to_float(v):
    if v is None or v == "":
        return 0.0
    try:
        return float(str(v).replace(",", "."))
    except:
        return 0.0


def load_cfg():
    if not os.path.exists(CONFIG_FILE):
        save_cfg(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        save_cfg(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)


def save_cfg(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ---------------------------
# TOM by weight
# ---------------------------
TOM_BY_WEIGHT = [
    (0, 2000, 180),
    (2001, 2300, 220),
    (2301, 2500, 260),
    (2501, 2700, 300),
    (2701, 2900, 340),
    (2901, 3100, 380),
    (3101, 3300, 450),
    (3301, 3500, 550),
]

def calculate_tom_from_weight(weight):
    if weight <= 0:
        return 0.0
    for min_w, max_w, fee in TOM_BY_WEIGHT:
        if min_w <= weight <= max_w:
            return float(fee)
    # >3500kg: manual -> return 0 but show warning
    return 0.0


# ---------------------------
# FX (ECB GBP->EUR)
# ---------------------------
@st.cache_data(ttl=3600)
def get_gbp_to_eur_rate():
    try:
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        r = requests.get(url, timeout=8)
        r.raise_for_status()

        tree = ET.fromstring(r.content)
        ns = {"def": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

        date = tree.find(".//def:Cube[@time]", ns).attrib["time"]
        gbp = float(tree.find(".//def:Cube[@currency='GBP']", ns).attrib["rate"])
        return round(1 / gbp, 4), date, "ecb"
    except Exception:
        return 1.1534, "fallback", "fallback"


# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

cfg = load_cfg()
rate, rate_date, rate_src = get_gbp_to_eur_rate()

tabs = st.tabs(["🇬🇧 UK", "🇯🇵 Japan", "⚙️ Admin"])

# ---------------------------
# Shared extra fees block
# ---------------------------
def extra_fees_ui(prefix: str):
    """
    These fields existed in your Flask form.
    In the Flask code they were preserved but NOT included in totals.
    Here we include them in the final total (so they matter).
    """
    with st.expander("Extra fees (optional)"):
        registration_fee = st.number_input("Registration fee (€)", min_value=0.0, step=10.0, key=f"{prefix}_registration_fee")
        customs_agent_fee = st.number_input("Customs agent fee (€)", min_value=0.0, step=10.0, key=f"{prefix}_customs_agent_fee")
        road_tax = st.number_input("Road tax (€)", min_value=0.0, step=10.0, key=f"{prefix}_road_tax")
        insurance_cy = st.number_input("Insurance (Cyprus) (€)", min_value=0.0, step=10.0, key=f"{prefix}_insurance_cy")
        port_charges = st.number_input("Port charges (€)", min_value=0.0, step=10.0, key=f"{prefix}_port_charges")
        co2_check = st.number_input("CO2 check / inspection (€)", min_value=0.0, step=10.0, key=f"{prefix}_co2_check")

    extras_total = (
        registration_fee
        + customs_agent_fee
        + road_tax
        + insurance_cy
        + port_charges
        + co2_check
    )
    return extras_total


# ---------------------------
# UK TAB
# ---------------------------
with tabs[0]:
    st.subheader("UK Import")
    st.caption(f"GBP → EUR: {rate} ({rate_src} {rate_date})")

    c1, c2 = st.columns(2)
    with c1:
        purchase_gbp = st.number_input("Purchase (GBP)", min_value=0.0, step=100.0)
        transport_gbp = st.number_input("Transport (GBP)", min_value=0.0, step=50.0)
    with c2:
        insurance_eur = st.number_input("Insurance / transport insurance (EUR)", min_value=0.0, step=10.0)
        vehicle_weight = st.number_input("Vehicle weight (kg)", min_value=0, step=50)

    extras_total = extra_fees_ui("uk")

    # TOM
    tom_registration = 0.0
    manual_tom = False
    if vehicle_weight > 0:
        tom_registration = calculate_tom_from_weight(vehicle_weight)
        if vehicle_weight > 3500:
            manual_tom = True

    if st.button("Calculate (UK)", use_container_width=True):
        # UK VAT on purchase (GBP)
        vat_uk_gbp = purchase_gbp * cfg["vat_uk_percent"] / 100.0

        # Convert to EUR using ECB rate
        purchase_eur_with_vat = (purchase_gbp + vat_uk_gbp) * rate
        transport_eur = transport_gbp * rate

        cif = purchase_eur_with_vat + transport_eur + insurance_eur
        duty_eur = cif * cfg["duty_percent"] / 100.0
        vat_eur = (cif + duty_eur) * cfg["vat_cy_percent"] / 100.0

        total_import = cif + duty_eur + vat_eur

        base_cyprus_fees = cfg["mot"] + cfg["plates"] + tom_registration
        total_cyprus = base_cyprus_fees + extras_total

        final_total = total_import + total_cyprus

        if manual_tom:
            st.warning("Weight > 3500kg: TOM is manual. Current TOM value is 0. Please enter it via an extra fee if needed.")

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"UK VAT (GBP): **£{vat_uk_gbp:,.2f}**")
        st.write(f"Purchase EUR (with UK VAT): **€{purchase_eur_with_vat:,.2f}**")
        st.write(f"Transport EUR: **€{transport_eur:,.2f}**")
        st.write(f"CIF: **€{cif:,.2f}**")
        st.write(f"Duty: **€{duty_eur:,.2f}**")
        st.write(f"Cyprus VAT: **€{vat_eur:,.2f}**")
        st.write(f"Import total (CIF+Duty+VAT): **€{total_import:,.2f}**")
        st.write(f"Cyprus base fees (MOT+Plates+TOM): **€{base_cyprus_fees:,.2f}**")
        st.write(f"Extra fees total: **€{extras_total:,.2f}**")
        st.write(f"Cyprus total: **€{total_cyprus:,.2f}**")


# ---------------------------
# JAPAN TAB
# ---------------------------
with tabs[1]:
    st.subheader("Japan Import")

    c1, c2 = st.columns(2)
    with c1:
        purchase_eur = st.number_input("Purchase (EUR)", min_value=0.0, step=500.0)
        shipping_eur = st.number_input("Shipping (EUR)", min_value=0.0, step=100.0)
    with c2:
        vehicle_weight_jp = st.number_input("Vehicle weight (kg)", min_value=0, step=50, key="jp_weight")

    extras_total = extra_fees_ui("jp")

    tom_registration = 0.0
    manual_tom = False
    if vehicle_weight_jp > 0:
        tom_registration = calculate_tom_from_weight(vehicle_weight_jp)
        if vehicle_weight_jp > 3500:
            manual_tom = True

    if st.button("Calculate (Japan)", use_container_width=True):
        cif = purchase_eur + shipping_eur
        duty_eur = cif * cfg["duty_percent"] / 100.0
        vat_eur = (cif + duty_eur) * cfg["vat_cy_percent"] / 100.0

        total_import = cif + duty_eur + vat_eur

        base_cyprus_fees = cfg["mot"] + cfg["plates"] + tom_registration
        total_cyprus = base_cyprus_fees + extras_total

        final_total = total_import + total_cyprus

        if manual_tom:
            st.warning("Weight > 3500kg: TOM is manual. Current TOM value is 0. Please enter it via an extra fee if needed.")

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"CIF: **€{cif:,.2f}**")
        st.write(f"Duty: **€{duty_eur:,.2f}**")
        st.write(f"Cyprus VAT: **€{vat_eur:,.2f}**")
        st.write(f"Import total (CIF+Duty+VAT): **€{total_import:,.2f}**")
        st.write(f"Cyprus base fees (MOT+Plates+TOM): **€{base_cyprus_fees:,.2f}**")
        st.write(f"Extra fees total: **€{extras_total:,.2f}**")
        st.write(f"Cyprus total: **€{total_cyprus:,.2f}**")


# ---------------------------
# ADMIN TAB
# ---------------------------
with tabs[2]:
    st.subheader("Admin")

    pwd = st.text_input("Password", type="password")
    if not pwd:
        st.info("Enter admin password to edit tax settings.")
    elif pwd != ADMIN_PASSWORD:
        st.error("Wrong password.")
    else:
        st.success("Access granted.")

        cfg_edit = dict(cfg)

        cfg_edit["vat_uk_percent"] = st.number_input("UK VAT %", value=float(cfg_edit["vat_uk_percent"]), step=0.5)
        cfg_edit["duty_percent"] = st.number_input("Duty %", value=float(cfg_edit["duty_percent"]), step=0.5)
        cfg_edit["vat_cy_percent"] = st.number_input("Cyprus VAT %", value=float(cfg_edit["vat_cy_percent"]), step=0.5)
        cfg_edit["mot"] = st.number_input("MOT (€)", value=float(cfg_edit["mot"]), step=1.0)
        cfg_edit["plates"] = st.number_input("Plates (€)", value=float(cfg_edit["plates"]), step=1.0)

        if st.button("Save settings", use_container_width=True):
            save_cfg(cfg_edit)
            st.success("Saved. Refresh the page to see updated values.")
