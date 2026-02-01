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
    "service": 150.0,     # BOTH
    "sva_japan": 0.0,     # JAPAN ONLY
}

# ---------------------------
# Helpers
# ---------------------------
def nz(v):
    return float(v) if v not in (None, "") else 0.0


def load_cfg():
    """
    Load config ONCE from disk.
    Defaults are written ONLY if file does not exist.
    Never overwritten automatically.
    """
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


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
        reg = st.number_input("Extra registration (€)", value=None, step=10.0, key=f"{prefix}_reg")
        agent = st.number_input("Customs agent (€)", value=None, step=10.0, key=f"{prefix}_agent")
        ins = st.number_input("Insurance CY (€)", value=None, step=10.0, key=f"{prefix}_ins")
        port = st.number_input("Port charges (€)", value=None, step=10.0, key=f"{prefix}_port")
        co2 = st.number_input("CO₂ / inspection (€)", value=None, step=10.0, key=f"{prefix}_co2")

    return nz(reg) + nz(agent) + nz(ins) + nz(port) + nz(co2)


# ---------------------------
# UK TAB
# ---------------------------
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase (GBP)", value=None, step=100.0)
    transport = st.number_input("Transport (GBP)", value=None, step=50.0)
    insurance = st.number_input("Insurance (EUR)", value=None, step=10.0)

    extras = extra_fees("uk")

    if st.button("Calculate UK", use_container_width=True):
        purchase = nz(purchase)
        transport = nz(transport)
        insurance = nz(insurance)

        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate

        cif = purchase_eur + transport_eur + insurance
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + cfg["service"]
        )

        total = cif + duty + vat + cy_fees + extras

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
        st.write(f"Service: €{cfg['service']:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# JAPAN TAB
# ---------------------------
with tabs[1]:
    purchase = st.number_input("Purchase (EUR)", value=None, step=500.0)
    shipping = st.number_input("Shipping (EUR)", value=None, step=100.0)

    extras = extra_fees("jp")

    if st.button("Calculate Japan", use_container_width=True):
        purchase = nz(purchase)
        shipping = nz(shipping)

        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + cfg["service"]
            + cfg["sva_japan"]
        )

        total = cif + duty + vat + cy_fees + extras

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
        st.write(f"Service: €{cfg['service']:,.2f}")
        st.write(f"SVA (Japan): €{cfg['sva_japan']:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# ADMIN TAB
# ---------------------------
with tabs[2]:
    pwd = st.text_input("Admin password", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Access granted")

        for k in cfg:
            cfg[k] = st.number_input(
                k.replace("_", " ").title(),
                value=float(cfg[k]),
                step=1.0,
                key=f"adm_{k}"
            )

        if st.button("Save settings"):
            save_cfg(cfg)
            st.success("Saved. Values will persist until changed again.")
    elif pwd:
        st.error("Wrong password")


# ---------------------------
# FOOTER
# ---------------------------
st.markdown(
    """
    <hr style="margin-top:50px;">
    <div style="text-align:center; color:gray; font-size:14px;">
        © 2025 Ioannis Papaiacovou. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)
