import streamlit as st
import requests
import xml.etree.ElementTree as ET
import json
import os

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="Car Import Calculator",
    layout="centered"
)

# =============================
# CONSTANTS
# =============================
ADMIN_PASSWORD = "i4ipapa"
CONFIG_FILE = "tax_config.json"

DEFAULT_CONFIG = {
    "vat_uk_percent": 20.0,
    "duty_percent": 10.0,
    "vat_cy_percent": 19.0,
    "mot": 60.0,
    "plates": 40.0,
}

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

# =============================
# HELPERS
# =============================
def to_float(v):
    try:
        return float(str(v).replace(",", "."))
    except:
        return 0.0

def calculate_tom(weight):
    if weight <= 0:
        return 0
    for a, b, fee in TOM_BY_WEIGHT:
        if a <= weight <= b:
            return fee
    return 0  # > 3500kg → manual

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

@st.cache_data(ttl=3600)
def get_gbp_to_eur_rate():
    try:
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        r = requests.get(url, timeout=5)
        r.raise_for_status()

        tree = ET.fromstring(r.content)
        ns = {"def": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

        date = tree.find(".//def:Cube[@time]", ns).attrib["time"]
        gbp = float(tree.find(".//def:Cube[@currency='GBP']", ns).attrib["rate"])

        return round(1 / gbp, 4), date
    except:
        return 1.15, "fallback"

# =============================
# LOAD CONFIG
# =============================
cfg = load_config()
rate, rate_date = get_gbp_to_eur_rate()

# =============================
# UI TABS
# =============================
tab_uk, tab_jp, tab_admin = st.tabs(
    ["🇬🇧 UK Import", "🇯🇵 Japan Import", "⚙️ Admin"]
)

# =============================
# 🇬🇧 UK IMPORT
# =============================
with tab_uk:
    st.header("UK Car Import Calculator")
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase_gbp = st.number_input("Purchase price (GBP)", min_value=0.0, step=500.0)
    transport_gbp = st.number_input("Transport (GBP)", min_value=0.0, step=100.0)
    insurance_eur = st.number_input("Insurance (EUR)", min_value=0.0, step=50.0)
    weight = st.number_input("Vehicle weight (kg)", min_value=0, step=50)

    if st.button("Calculate UK total", use_container_width=True):
        vat_uk = purchase_gbp * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase_gbp + vat_uk) * rate
        transport_eur = transport_gbp * rate

        cif = purchase_eur + transport_eur + insurance_eur
        duty = cif * cfg["duty_percent"] / 100
        vat_cy = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom(weight)

        total_import = cif + duty + vat_cy
        total_cyprus = cfg["mot"] + cfg["plates"] + tom
        final_total = total_import + total_cyprus

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"UK VAT: €{vat_uk:,.2f}")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({cfg['duty_percent']}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT ({cfg['vat_cy_percent']}%): €{vat_cy:,.2f}")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"TOM: €{tom:,.2f}")

# =============================
# 🇯🇵 JAPAN IMPORT (FIXED)
# =============================
with tab_jp:
    st.header("Japan Car Import Calculator")

    purchase_eur = st.number_input("Purchase price (EUR)", min_value=0.0, step=500.0)
    shipping_eur = st.number_input("Shipping (EUR)", min_value=0.0, step=100.0)
    weight = st.number_input("Vehicle weight (kg)", min_value=0, step=50, key="jp_weight")

    if st.button("Calculate Japan total", use_container_width=True):
        tom = calculate_tom(weight)

        cif = purchase_eur + shipping_eur
        duty = cif * cfg["duty_percent"] / 100
        vat_cy = (cif + duty) * cfg["vat_cy_percent"] / 100

        total_import = cif + duty + vat_cy
        total_cyprus = cfg["mot"] + cfg["plates"] + tom
        final_total = total_import + total_cyprus

        st.success(f"Final total: €{final_total:,.2f}")

        st.write("### Breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({cfg['duty_percent']}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT ({cfg['vat_cy_percent']}%): €{vat_cy:,.2f}")
        st.write(f"Import total: €{total_import:,.2f}")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"TOM: €{tom:,.2f}")

# =============================
# ⚙️ ADMIN
# =============================
with tab_admin:
    st.header("Admin Settings")

    pwd = st.text_input("Password", type="password")

    if pwd == ADMIN_PASSWORD:
        cfg["vat_uk_percent"] = st.number_input("UK VAT (%)", value=cfg["vat_uk_percent"])
        cfg["duty_percent"] = st.number_input("Duty (%)", value=cfg["duty_percent"])
        cfg["vat_cy_percent"] = st.number_input("Cyprus VAT (%)", value=cfg["vat_cy_percent"])
        cfg["mot"] = st.number_input("MOT fee (€)", value=cfg["mot"])
        cfg["plates"] = st.number_input("Plates fee (€)", value=cfg["plates"])

        if st.button("Save settings"):
            save_config(cfg)
            st.success("Settings saved")
    elif pwd:
        st.error("Wrong password")
