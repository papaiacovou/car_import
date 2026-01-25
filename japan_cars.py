import streamlit as st
import requests
import xml.etree.ElementTree as ET

# -----------------------------
# CONFIG
# -----------------------------
VAT_UK = 20
DUTY_PERCENT = 10
VAT_CY = 19
MOT = 60
PLATES = 40

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

# -----------------------------
# HELPERS
# -----------------------------
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
            timeout=5,
        ).content
        root = ET.fromstring(xml)
        ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        rate = float(root.find(".//e:Cube[@currency='GBP']", ns).attrib["rate"])
        date = root.find(".//e:Cube[@time]", ns).attrib["time"]
        return round(1 / rate, 4), date
    except Exception:
        return 1.15, "fallback"

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

tab_uk, tab_jp = st.tabs(["🇬🇧 UK Import", "🇯🇵 Japan Import"])

# -----------------------------
# UK CALCULATOR
# -----------------------------
with tab_uk:
    rate, date = get_gbp_rate()
    st.caption(f"GBP → EUR: **{rate}** (ECB {date})")

    purchase_gbp = st.number_input("Purchase price (£)", 0.0)
    transport_gbp = st.number_input("Transport (£)", 0.0)
    insurance_eur = st.number_input("Insurance (€)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0)

    if st.button("Calculate UK Import"):
        vat_uk = purchase_gbp * VAT_UK / 100
        purchase_eur = (purchase_gbp + vat_uk) * rate
        transport_eur = transport_gbp * rate

        cif = purchase_eur + transport_eur + insurance_eur
        duty = cif * DUTY_PERCENT / 100
        vat_cy = (cif + duty) * VAT_CY / 100
        tom = calculate_tom(weight)

        total_import = cif + duty + vat_cy
        total_cy = MOT + PLATES + tom

        st.subheader("Results")
        st.write(f"UK VAT (£): **{vat_uk:.2f}**")
        st.write(f"CIF (€): **{cif:.2f}**")
        st.write(f"Customs Duty (€): **{duty:.2f}**")
        st.write(f"Cyprus VAT (€): **{vat_cy:.2f}**")
        st.write(f"TOM (€): **{tom:.2f}**")
        st.success(f"Final Total (€): **{total_import + total_cy:.2f}**")

# -----------------------------
# JAPAN CALCULATOR
# -----------------------------
with tab_jp:
    purchase_eur = st.number_input("Purchase price (€)", 0.0)
    shipping_eur = st.number_input("Shipping (€)", 0.0)
    weight = st.number_input("Vehicle weight (kg)", 0, key="jp_weight")

    if st.button("Calculate Japan Import"):
        cif = purchase_eur + shipping_eur
        duty = cif * DUTY_PERCENT / 100
        vat = (cif + duty) * VAT_CY / 100
        tom = calculate_tom(weight)

        total_import = cif + duty + vat
        total_cy = MOT + PLATES + tom

        st.subheader("Results")
        st.write(f"CIF (€): **{cif:.2f}**")
        st.write(f"Customs Duty (€): **{duty:.2f}**")
        st.write(f"Cyprus VAT (€): **{vat:.2f}**")
        st.write(f"TOM (€): **{tom:.2f}**")
        st.success(f"Final Total (€): **{total_import + total_cy:.2f}**")
