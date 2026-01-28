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
    "road_tax": 120.0,
    "registration": 150.0,
    "certifying_officer": 80.0,
}

# ---------------------------
# Helpers
# ---------------------------
def to_float(v):
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

def calculate_tom(weight):
    for a, b, fee in TOM_BY_WEIGHT:
        if a <= weight <= b:
            return float(fee)
    return 0.0


# ---------------------------
# ECB FX
# ---------------------------
@st.cache_data(ttl=3600)
def get_gbp_rate():
    try:
        r = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=10
        )
        r.raise_for_status()
        tree = ET.fromstring(r.content)
        ns = {"def": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        date = tree.find(".//def:Cube[@time]", ns).attrib["time"]
        gbp = float(tree.find(".//def:Cube[@currency='GBP']", ns).attrib["rate"])
        return round(1 / gbp, 4), date
    except:
        return 1.1534, "fallback"


# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

cfg = load_cfg()
rate, rate_date = get_gbp_rate()

tabs = st.tabs(["🇬🇧 UK", "🇯🇵 Japan", "⚙️ Admin"])


# ---------------------------
# Extra fees
# ---------------------------
def extra_fees(prefix):
    with st.expander("Extra fees (optional)"):
        reg_fee = st.number_input("Registration fee (€)", 0.0, step=10.0, key=f"{prefix}_reg")
        agent = st.number_input("Customs agent (€)", 0.0, step=10.0, key=f"{prefix}_agent")
        insurance = st.number_input("Insurance CY (€)", 0.0, step=10.0, key=f"{prefix}_ins")
        port = st.number_input("Port charges (€)", 0.0, step=10.0, key=f"{prefix}_port")
        co2 = st.number_input("CO₂ / inspection (€)", 0.0, step=10.0, key=f"{prefix}_co2")
    return reg_fee + agent + insurance + port + co2


# ---------------------------
# UK TAB
# ---------------------------
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase (GBP)", 0.0, step=100.0)
    transport = st.number_input("Transport (GBP)", 0.0, step=50.0)
    insurance_eur = st.number_input("Insurance (EUR)", 0.0, step=10.0)
    weight = st.number_input("Vehicle weight (kg)", 0, step=50)

    extras = extra_fees("uk")

    if st.button("Calculate UK", use_container_width=True):
        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate

        cif = purchase_eur + transport_eur + insurance_eur
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom(weight)
        cy_base = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + tom
        )

        total = cif + duty + vat + cy_base + extras

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"UK VAT (GBP): £{vat_uk:,.2f}")
        st.write(f"Purchase EUR (with UK VAT): €{purchase_eur:,.2f}")
        st.write(f"Transport EUR: €{transport_eur:,.2f}")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"Road Tax: €{cfg['road_tax']:,.2f}")
        st.write(f"Registration: €{cfg['registration']:,.2f}")
        st.write(f"Certifying Officer: €{cfg['certifying_officer']:,.2f}")
        st.write(f"TOM: €{tom:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# JAPAN TAB
# ---------------------------
with tabs[1]:
    purchase = st.number_input("Purchase (EUR)", 0.0, step=500.0)
    shipping = st.number_input("Shipping (EUR)", 0.0, step=100.0)
    weight = st.number_input("Vehicle weight (kg)", 0, step=50, key="jp_w")

    extras = extra_fees("jp")

    if st.button("Calculate Japan", use_container_width=True):
        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom(weight)
        cy_base = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + tom
        )

        total = cif + duty + vat + cy_base + extras

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"Road Tax: €{cfg['road_tax']:,.2f}")
        st.write(f"Registration: €{cfg['registration']:,.2f}")
        st.write(f"Certifying Officer: €{cfg['certifying_officer']:,.2f}")
        st.write(f"TOM: €{tom:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# ADMIN TAB
# ---------------------------
with tabs[2]:
    pwd = st.text_input("Admin password", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Access granted")

        for k in DEFAULT_CONFIG:
            cfg[k] = st.number_input(
                k.replace("_", " ").title(),
                value=float(cfg[k]),
                step=1.0
            )

        if st.button("Save settings"):
            save_cfg(cfg)
            st.success("Saved — refresh page")
    elif pwd:
        st.error("Wrong password")
