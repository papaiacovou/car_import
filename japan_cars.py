import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ============================================================
# Google Sheets / Auth
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

def _bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y")

# ============================================================
# Config from Google Sheets
# ============================================================
def load_cfg():
    rows = cfg_sheet.get_all_records()
    return {r["key"]: float(r["value"]) for r in rows}

def save_cfg(cfg):
    values = cfg_sheet.get_all_values()
    header = values[0]
    key_col = header.index("key")
    val_col = header.index("value")

    updates = []
    for i, row in enumerate(values[1:], start=2):
        key = row[key_col]
        if key in cfg:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(i, val_col + 1),
                "values": [[str(cfg[key])]],
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
            "active": _bool(r.get("active", True)),
        }
    return users

def login(u, p):
    users = load_users()
    if u not in users or not users[u]["active"]:
        return False, None
    ok = bcrypt.checkpw(p.encode(), users[u]["hash"].encode())
    return ok, users[u]["role"] if ok else (False, None)

def logout():
    st.session_state.clear()
    st.cache_data.clear()
    st.rerun()

# ============================================================
# LIVE FX (Google / Market) + ECB fallback
# ============================================================
@st.cache_data(ttl=300)
def get_gbp_rate():
    # LIVE MARKET
    try:
        r = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "GBP", "symbols": "EUR"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        return round(data["rates"]["EUR"], 4), data["date"], "Market"
    except:
        pass

    # ECB FALLBACK
    r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=8)
    tree = ET.fromstring(r.content)
    gbp = float(tree.find(".//{*}Cube[@currency='GBP']").attrib["rate"])
    date = tree.find(".//{*}Cube[@time]").attrib["time"]
    return round(1 / gbp, 4), date, "ECB"

# ============================================================
# UI
# ============================================================
st.set_page_config("Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

# ---------- LOGIN ----------
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            ok, role = login(u, p)
            if ok:
                st.session_state.auth = True
                st.session_state.role = role
                st.session_state.user = u
                st.rerun()
            else:
                st.error("Invalid login")
    st.stop()

with st.sidebar:
    st.write(f"👤 {st.session_state.user}")
    st.write(f"🔐 {st.session_state.role}")
    st.button("Logout", on_click=logout)

cfg = load_cfg()
rate, rate_date, rate_src = get_gbp_rate()

tabs = ["🇬🇧 UK", "🇯🇵 Japan"]
if st.session_state.role == "admin":
    tabs.append("⚙️ Admin")

t = st.tabs(tabs)

# ============================================================
# UK
# ============================================================
with t[0]:
    st.caption(f"GBP → EUR: {rate} ({rate_src} {rate_date})")

    p = nz(st.number_input("Purchase (GBP)", value=None))
    tr = nz(st.number_input("Transport (GBP)", value=None))
    ins = nz(st.number_input("Insurance (EUR)", value=None))

    if st.button("Calculate UK"):
        vat_uk = p * cfg["vat_uk_percent"] / 100
        purchase_eur = (p + vat_uk) * rate
        cif = purchase_eur + tr * rate + ins

        duty = cif * cfg["duty_percent_10"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"] +
            cfg["registration"] + cfg["certifying_officer"] +
            cfg["service"] + cfg["customs_agent"] + cfg["port_charges"]
        )

        total = cif + duty + vat + cy

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty (10%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        for k in ["mot","plates","road_tax","registration","certifying_officer","service","customs_agent","port_charges"]:
            st.write(f"{k.replace('_',' ').title()}: €{cfg[k]:,.2f}")

        st.info("💡 Recommendation: UK imports benefit from predictable duties but FX timing can impact total cost.")

# ============================================================
# JAPAN
# ============================================================
with t[1]:
    p = nz(st.number_input("Purchase (EUR)", value=None))
    s = nz(st.number_input("Shipping (EUR)", value=None))
    duty_choice = st.radio("Duty rate (%)", [5, 10], horizontal=True)

    if st.button("Calculate Japan"):
        cif = p + s
        duty_rate = cfg["duty_percent_5"] if duty_choice == 5 else cfg["duty_percent_10"]
        duty = cif * duty_rate / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"] +
            cfg["registration"] + cfg["certifying_officer"] +
            cfg["service"] + cfg["customs_agent"] +
            cfg["port_charges"] + cfg["sva_japan"]
        )

        total = cif + duty + vat + cy

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({duty_choice}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown("### 🇨🇾 Cyprus fees")
        for k in ["mot","plates","road_tax","registration","certifying_officer","service","customs_agent","port_charges","sva_japan"]:
            st.write(f"{k.replace('_',' ').title()}: €{cfg[k]:,.2f}")

        st.info("💡 Recommendation: Japan imports can reduce duty to 5% depending on vehicle category.")

# ============================================================
# ADMIN
# ============================================================
if st.session_state.role == "admin":
    with t[2]:
        st.subheader("Admin settings (stored in Google Sheets)")
        cfg_edit = dict(cfg)

        for k in cfg_edit:
            cfg_edit[k] = st.number_input(k.replace("_"," ").title(), value=cfg[k])

        if st.button("Save"):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved permanently.")
            st.rerun()

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<hr>
<div style="text-align:center;color:gray">
© 2025 Ioannis Papaiacovou. All rights reserved.
</div>
""", unsafe_allow_html=True)
