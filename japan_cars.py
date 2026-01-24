import streamlit as st
import requests
import xml.etree.ElementTree as ET
import json
import os

st.set_page_config(page_title="Car Import Calculator", layout="centered")

# ---------------- CONFIG ----------------
ADMIN_PASSWORD = "i4ipapa"
CONFIG_FILE = "tax_config.json"

DEFAULT_CONFIG = {
    "vat_uk_percent": 20,
    "duty_percent": 10,
    "vat_cy_percent": 19,
    "mot": 60,
    "plates": 40,
}

# ---------------- HELPERS ----------------
def to_float(v):
    try:
        return float(str(v).replace(",", "."))
    except:
        return 0.0

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f)
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

TOM_BY_WEIGHT = [
    (0, 2000, 180), (2001, 2300, 220), (2301, 2500, 260),
    (2501, 2700, 300), (2701, 2900, 340), (2901, 3100, 380),
    (3101, 3300, 450), (3301, 3500, 550),
]

def calculate_tom(weight):
    for a, b, fee in TOM_BY_WEIGHT:
        if a <= weight <= b:
            return fee
    return 0

@st.cache_data(ttl=3600)
def get_gbp_rate():
    try:
        xml = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=5
        ).content
        root = ET.fromstring(xml)
        ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        gbp = float(root.find(".//e:Cube[@currency='GBP']", ns).attrib["rate"])
        date = root.find(".//e:Cube[@time]", ns).attrib["time"]
        return round(1 / gbp, 4), date
    except:
        return 1.15, "fallback"

# ---------------- UI ----------------
cfg = load_config()
rate, rate_date = get_gbp_rate()

tab_uk, tab_jp, tab_admin = st.tabs(["🇬🇧 UK Import", "🇯🇵 Japan Import", "⚙️ Admin"])

# ---------------- UK ----------------
with tab_uk:
    st.header("UK Car Import Calculator")
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase price (GBP)", 0.0)
    transport = st.number_input("Transport (GBP)", 0.0)
    insurance = st.number_input("Insurance (EUR)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0)

    if st.button("Calculate UK total"):
        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate

        cif = purchase_eur + transport_eur + insurance
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        tom = calculate_tom(weight)
        total = cif + duty + vat + cfg["mot"] + cfg["plates"] + tom

        st.success(f"Final total: €{total:,.2f}")

# ---------------- JAPAN ----------------
with tab_jp:
    st.header("Japan Car Import Calculator")

    purchase = st.number_input("Purchase price (EUR)", 0.0)
    shipping = st.number_input("Shipping (EUR)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0, key="jp_w")

    if st.button("Calculate Japan total"):
        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100
        tom = calculate_tom(weight)

        total = cif + duty + vat + cfg["mot"] + cfg["plates"] + tom
        st.success(f"Final total: €{total:,.2f}")

# ---------------- ADMIN ----------------
with tab_admin:
    st.header("Admin Settings")
    pwd = st.text_input("Password", type="password")

    if pwd == ADMIN_PASSWORD:
        cfg["vat_uk_percent"] = st.number_input("UK VAT %", value=cfg["vat_uk_percent"])
        cfg["duty_percent"] = st.number_input("Duty %", value=cfg["duty_percent"])
        cfg["vat_cy_percent"] = st.number_input("CY VAT %", value=cfg["vat_cy_percent"])
        cfg["mot"] = st.number_input("MOT fee", value=cfg["mot"])
        cfg["plates"] = st.number_input("Plates fee", value=cfg["plates"])

        if st.button("Save settings"):
            save_config(cfg)
            st.success("Settings saved")
    elif pwd:
        st.error("Wrong password")
