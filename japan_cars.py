# ============================================================
# 🚗 CAR IMPORT CALCULATOR (FINAL – STABLE)
# ============================================================

import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ============================================================
# GOOGLE SHEETS
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES,
)
gc = gspread.authorize(CREDS)

book = gc.open_by_key(st.secrets["SPREADSHEET_ID"])
cfg_sheet = book.sheet1
users_sheet = book.worksheet("users")

# ============================================================
# HELPERS
# ============================================================
def nz(v):
    return float(v) if v not in (None, "") else 0.0

def to_bool(v):
    return str(v).lower() in ("1", "true", "yes", "y", "on")

# ============================================================
# CONFIG
# ============================================================
def load_cfg():
    cfg = {}
    for r in cfg_sheet.get_all_records():
        cfg[r["key"]] = float(r["value"])
    return cfg

def save_cfg(cfg):
    data = cfg_sheet.get_all_values()
    keys = [r[0] for r in data[1:]]
    for i, k in enumerate(keys, start=2):
        cfg_sheet.update_cell(i, 2, cfg[k])

# ============================================================
# USERS / AUTH
# ============================================================
@st.cache_data(ttl=60)
def load_users():
    users = {}
    for r in users_sheet.get_all_records():
        users[r["username"]] = {
            "hash": r["password_hash"],
            "role": r.get("role", "user"),
            "active": to_bool(r.get("active", True)),
        }
    return users

def verify_login(u, p):
    users = load_users()
    if u in users and users[u]["active"]:
        if bcrypt.checkpw(p.encode(), users[u]["hash"].encode()):
            return True, users[u]["role"]
    return False, None

# ============================================================
# FX RATE (LIVE ECB)
# ============================================================
@st.cache_data(ttl=1800)
def get_gbp_rate():
    r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    tree = ET.fromstring(r.content)
    ns = {"d": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    date = tree.find(".//d:Cube[@time]", ns).attrib["time"]
    gbp = float(tree.find(".//d:Cube[@currency='GBP']", ns).attrib["rate"])
    return round(1 / gbp, 4), date

# ============================================================
# UI
# ============================================================
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

# ---------------- LOGIN ----------------
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            ok, role = verify_login(u, p)
            if ok:
                st.session_state.auth = True
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid login")
    st.stop()

# ---------------- STATE ----------------
cfg = load_cfg()
rate, rate_date = get_gbp_rate()
is_admin = st.session_state.role == "admin"

tabs = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tabs.append("⚙️ Admin")
tabs = st.tabs(tabs)

# ============================================================
# 🇯🇵 JAPAN TAB
# ============================================================
with tabs[1]:
    c1, c2 = st.columns([2, 1])
    with c1:
        purchase = st.number_input("Purchase (EUR)", value=10000.0)
    with c2:
        duty_choice = st.radio("Duty rate", ["10%", "5%"], horizontal=True)

    shipping = st.number_input("Shipping (EUR)", value=0.0)

    if st.button("Calculate Japan", use_container_width=True):
        cif = purchase + shipping
        duty_rate = cfg["duty_percent_5"] if duty_choice == "5%" else cfg["duty_percent_10"]
        duty = cif * duty_rate / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"]
            + cfg["registration"] + cfg["certifying_officer"]
            + cfg["service"] + cfg["customs_agent"]
            + cfg["port_charges"] + cfg["sva_japan"]
        )

        total = cif + duty + vat + cy_fees

        # 🔑 STORE FOR PROFIT TOOL
        st.session_state.last_final_total = total
        st.session_state.last_cy_vat = vat

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("## 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({duty_rate}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

# ============================================================
# ⚙️ ADMIN + 💰 PROFIT TOOL
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader("💰 Profit Calculator")

        if "last_final_total" not in st.session_state:
            st.warning("Run a UK or Japan calculation first.")
        else:
            cost_net = st.session_state.last_final_total - st.session_state.last_cy_vat
            st.write(f"**Car cost (net): €{cost_net:,.2f}**")

            target_profit = st.number_input("Target profit (€)", value=None, step=500.0)
            if target_profit:
                sell_price = (cost_net + target_profit) * 1.19
                vat_sale = sell_price * 19 / 119
                st.success(f"Sell at €{sell_price:,.2f} (VAT €{vat_sale:,.2f})")

            manual_price = st.number_input("Selling price (VAT incl €)", value=None, step=500.0)
            if manual_price:
                vat_sale = manual_price * 19 / 119
                net_sale = manual_price - vat_sale
                profit = net_sale - cost_net
                st.success(f"Profit: €{profit:,.2f}")

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True
)
