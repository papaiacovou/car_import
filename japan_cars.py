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
    "road_tax": 0.0
}

# ---------------------------
# Helpers
# ---------------------------
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
    for a, b, fee in TOM_BY_WEIGHT:
        if a <= weight <= b:
            return float(fee)
    return 0.0

# ---------------------------
# FX
# ---------------------------
@st.cache_data(ttl=3600)
def get_gbp_to_eur_rate():
    try:
        r = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=8
        )
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
def extra_fees_ui(prefix):
    with st.expander("Extra fees (optional)"):
        registration = st.number_input("Registration (€)", 0.0, key=f"{prefix}_reg")
        customs = st.number_input("Customs agent (€)", 0.0, key=f"{prefix}_cust")
        road_extra = st.number_input("Extra road tax (€)", 0.0, key=f"{prefix}_road")
        insurance = st.number_input("Insurance CY (€)", 0.0, key=f"{prefix}_ins")
        port = st.number_input("Port charges (€)", 0.0, key=f"{prefix}_port")
        co2 = st.number_input("CO2 / inspection (€)", 0.0, key=f"{prefix}_co2")

    return registration + customs + road_extra + insurance + port + co2

# ---------------------------
# UK
# ---------------------------
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase (GBP)", 0.0)
    transport = st.number_input("Transport (GBP)", 0.0)
    insurance = st.number_input("Insurance (€)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0)

    extras = extra_fees_ui("uk")

    if st.button("Calculate UK"):
        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        cif = (purchase + vat_uk) * rate + transport * rate + insurance
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom_from_weight(weight)
        cy_fees = cfg["mot"] + cfg["plates"] + cfg["road_tax"] + tom

        total = cif + duty + vat + cy_fees + extras
        st.success(f"Final total: €{total:,.2f}")

# ---------------------------
# JAPAN
# ---------------------------
with tabs[1]:
    purchase = st.number_input("Purchase (€)", 0.0)
    shipping = st.number_input("Shipping (€)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0, key="jp_w")

    extras = extra_fees_ui("jp")

    if st.button("Calculate Japan"):
        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom_from_weight(weight)
        cy_fees = cfg["mot"] + cfg["plates"] + cfg["road_tax"] + tom

        total = cif + duty + vat + cy_fees + extras
        st.success(f"Final total: €{total:,.2f}")

# ---------------------------
# ADMIN
# ---------------------------
with tabs[2]:
    pwd = st.text_input("Password", type="password")

    if pwd == ADMIN_PASSWORD:
        st.success("Admin access")

        cfg_edit = dict(cfg)

        cfg_edit["vat_uk_percent"] = st.number_input("UK VAT %", value=cfg_edit["vat_uk_percent"])
        cfg_edit["duty_percent"] = st.number_input("Duty %", value=cfg_edit["duty_percent"])
        cfg_edit["vat_cy_percent"] = st.number_input("Cyprus VAT %", value=cfg_edit["vat_cy_percent"])
        cfg_edit["mot"] = st.number_input("MOT (€)", value=cfg_edit["mot"])
        cfg_edit["plates"] = st.number_input("Plates (€)", value=cfg_edit["plates"])
        cfg_edit["road_tax"] = st.number_input("Road Tax (€)", value=cfg_edit["road_tax"])

        if st.button("Save settings"):
            save_cfg(cfg_edit)
            st.success("Saved – refresh page")
    else:
        st.info("Enter admin password")
