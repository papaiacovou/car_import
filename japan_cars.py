import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ============================================================
# Google Sheets setup
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
# Helpers
# ============================================================
def nz(v):
    return float(v) if v not in (None, "") else 0.0

def to_bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

# ============================================================
# Config from Google Sheets
# ============================================================
def load_cfg():
    rows = cfg_sheet.get_all_records()
    cfg = {r["key"]: float(r["value"]) for r in rows}
    assert "duty_percent_10" in cfg
    return cfg

def save_cfg(cfg):
    data = cfg_sheet.get_all_values()
    headers = [h.lower() for h in data[0]]
    key_col = headers.index("key")
    val_col = headers.index("value")

    updates = []
    for i, row in enumerate(data[1:], start=2):
        k = row[key_col]
        if k in cfg:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(i, val_col + 1),
                "values": [[str(cfg[k])]],
            })
    if updates:
        cfg_sheet.batch_update(updates)

# ============================================================
# Users / Login
# ============================================================
@st.cache_data(ttl=60)
def load_users():
    rows = users_sheet.get_all_records()
    users = {}
    for r in rows:
        users[r["username"]] = {
            "hash": r["password_hash"],
            "role": r.get("role", "user"),
            "active": to_bool(r.get("active", True)),
        }
    return users

def verify_login(u, p):
    users = load_users()
    if u not in users or not users[u]["active"]:
        return False, None
    if bcrypt.checkpw(p.encode(), users[u]["hash"].encode()):
        return True, users[u]["role"]
    return False, None

# ============================================================
# LIVE FX
# ============================================================
@st.cache_data(ttl=300)
def get_gbp_rate():
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "GBP", "symbols": "EUR"},
            timeout=8,
        )
        data = r.json()
        return round(data["rates"]["EUR"], 4), data["date"], "Market"
    except:
        r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=8)
        tree = ET.fromstring(r.content)
        gbp = float(tree.find(".//{*}Cube[@currency='GBP']").attrib["rate"])
        date = tree.find(".//{*}Cube[@time]").attrib["time"]
        return round(1 / gbp, 4), date, "ECB"

# ============================================================
# UI
# ============================================================
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = ""

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
                st.error("Invalid credentials")
    st.stop()

cfg = load_cfg()
rate, rate_date, rate_src = get_gbp_rate()
is_admin = st.session_state.role == "admin"

tabs = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tabs.extend(["💰 Profit Tool", "⚙️ Admin"])
tabs = st.tabs(tabs)

# ============================================================
# 🇬🇧 UK TAB
# ============================================================
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} — updated {rate_date} ({rate_src})")

    purchase = nz(st.number_input("Purchase (GBP)", value=None))
    transport = nz(st.number_input("Transport (GBP)", value=None))
    insurance = nz(st.number_input("Insurance (EUR)", value=None))

    if st.button("Calculate UK", use_container_width=True):
        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate

        cif = purchase_eur + transport_eur + insurance
        duty = cif * cfg["duty_percent_10"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"]
            + cfg["registration"] + cfg["certifying_officer"]
            + cfg["service"] + cfg["customs_agent"]
            + cfg["port_charges"]
        )

        cost_net = cif + duty + cy_fees
        total = cost_net + vat

        st.session_state.last_cost_net = cost_net

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        st.write(f"Total Cyprus fees: €{cy_fees:,.2f}")

# ============================================================
# 🇯🇵 JAPAN TAB
# ============================================================
with tabs[1]:
    purchase = nz(st.number_input("Purchase (EUR)", value=None))
    shipping = nz(st.number_input("Shipping (EUR)", value=None))
    duty_choice = st.radio("Duty rate", ["10%", "5%"], horizontal=True)

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

        cost_net = cif + duty + cy_fees
        total = cost_net + vat

        st.session_state.last_cost_net = cost_net

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty: €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        st.write(f"Total Cyprus fees: €{cy_fees:,.2f}")

# ============================================================
# 💰 PROFIT TOOL
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader("💰 Profit Calculator (Admin only)")

        if "last_cost_net" not in st.session_state:
            st.info("Run a UK or Japan calculation first.")
        else:
            cost_net = st.session_state.last_cost_net
            st.write(f"**Car cost (net of CY VAT): €{cost_net:,.2f}**")

# ============================================================
# ⚙️ ADMIN SETTINGS
# ============================================================
if is_admin:
    with tabs[3]:
        cfg_edit = dict(cfg)
        for k in cfg_edit:
            cfg_edit[k] = st.number_input(k.replace("_", " ").title(), value=float(cfg_edit[k]))
        if st.button("Save settings", use_container_width=True):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved permanently")
            st.rerun()

# ============================================================
# Footer
# ============================================================
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True
)
