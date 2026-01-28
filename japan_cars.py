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
    "road_tax": 0.0,
    "registration": 0.0,
    "certifying_officer": 0.0,
}

# ---------------------------
# Helpers
# ---------------------------
def load_cfg():
    if not os.path.exists(CONFIG_FILE):
        save_cfg(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cfg(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ---------------------------
# TOM (DISABLED BUT KEPT)
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
    for a, b, fee in TOM_BY_WEIGHT:
        if a <= weight <= b:
            return float(fee)
    return 0.0

# ---------------------------
# FX (ECB GBP → EUR)
# ---------------------------
@st.cache_data(ttl=3600)
def get_gbp_to_eur_rate():
    try:
        r = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=8
        )
        r.raise_for_status()
        tree = ET.fromstring(r.content)
        ns = {"d": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        date = tree.find(".//d:Cube[@time]", ns).attrib["time"]
        gbp = float(tree.find(".//d:Cube[@currency='GBP']", ns).attrib["rate"])
        return round(1 / gbp, 4), date
    except:
        return 1.15, "fallback"

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

cfg = load_cfg()
rate, rate_date = get_gbp_to_eur_rate()

tabs = st.tabs(["🇬🇧 UK", "🇯🇵 Japan", "⚙️ Admin"])

# ---------------------------
# Extra fees
# ---------------------------
def extra_fees(prefix):
    with st.expander("Extra fees (optional)"):
        reg_fee = st.number_input("Registration fee (€)", 0.0, key=f"{prefix}_reg")
        agent_fee = st.number_input("Customs agent (€)", 0.0, key=f"{prefix}_agent")
        road_tax = st.number_input("Road tax (€)", 0.0, key=f"{prefix}_road")
        insurance = st.number_input("Insurance CY (€)", 0.0, key=f"{prefix}_ins")
        port = st.number_input("Port charges (€)", 0.0, key=f"{prefix}_port")
        co2 = st.number_input("CO₂ / inspection (€)", 0.0, key=f"{prefix}_co2")

    return reg_fee + agent_fee + road_tax + insurance + port + co2

# ===========================
# UK TAB
# ===========================
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase_gbp = st.number_input("Purchase (GBP)", 0.0, step=500.0, key="uk_purchase")
    transport_gbp = st.number_input("Transport (GBP)", 0.0, step=100.0, key="uk_transport")
    insurance_eur = st.number_input("Insurance (EUR)", 0.0, step=50.0, key="uk_insurance")
    weight_uk = st.number_input("Vehicle weight (kg)", 0, step=50, key="uk_weight")

    extras = extra_fees("uk")

    # TOM disabled
    tom = 0.0

    if st.button("Calculate UK", key="calc_uk"):
        vat_uk = purchase_gbp * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase_gbp + vat_uk) * rate
        transport_eur = transport_gbp * rate

        cif = purchase_eur + transport_eur + insurance_eur
        duty = cif * cfg["duty_percent"] / 100
        vat_cy = (cif + duty) * cfg["vat_cy_percent"] / 100

        import_total = cif + duty + vat_cy

        cyprus_base = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
        )

        final_total = import_total + cyprus_base + extras

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"UK VAT: £{vat_uk:,.2f}")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat_cy:,.2f}")
        st.write(f"Cyprus base fees: €{cyprus_base:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")

# ===========================
# JAPAN TAB
# ===========================
with tabs[1]:
    purchase_eur = st.number_input("Purchase (EUR)", 0.0, step=1000.0, key="jp_purchase")
    shipping = st.number_input("Shipping (EUR)", 0.0, step=200.0, key="jp_shipping")
    weight_jp = st.number_input("Vehicle weight (kg)", 0, step=50, key="jp_weight")

    extras = extra_fees("jp")

    tom = 0.0  # disabled

    if st.button("Calculate Japan", key="calc_jp"):
        cif = purchase_eur + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat_cy = (cif + duty) * cfg["vat_cy_percent"] / 100

        import_total = cif + duty + vat_cy

        cyprus_base = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
        )

        final_total = import_total + cyprus_base + extras

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat_cy:,.2f}")
        st.write(f"Cyprus base fees: €{cyprus_base:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")

# ===========================
# ADMIN TAB
# ===========================
with tabs[2]:
    pwd = st.text_input("Admin password", type="password", key="admin_pwd")
    if pwd == ADMIN_PASSWORD:
        cfg["vat_uk_percent"] = st.number_input("UK VAT %", value=cfg["vat_uk_percent"], key="adm_vatuk")
        cfg["duty_percent"] = st.number_input("Duty %", value=cfg["duty_percent"], key="adm_duty")
        cfg["vat_cy_percent"] = st.number_input("Cyprus VAT %", value=cfg["vat_cy_percent"], key="adm_vatcy")
        cfg["mot"] = st.number_input("MOT (€)", value=cfg["mot"], key="adm_mot")
        cfg["plates"] = st.number_input("Plates (€)", value=cfg["plates"], key="adm_plates")
        cfg["road_tax"] = st.number_input("Road tax (€)", value=cfg["road_tax"], key="adm_road")
        cfg["registration"] = st.number_input("Registration (€)", value=cfg["registration"], key="adm_reg")
        cfg["certifying_officer"] = st.number_input(
            "Certifying officer (€)",
            value=cfg["certifying_officer"],
            key="adm_cert"
        )

        if st.button("Save settings", key="adm_save"):
            save_cfg(cfg)
            st.success("Settings saved")
    elif pwd:
        st.error("Wrong password")
