import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ---------------------------
# Google Sheets + Auth
# ---------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES,
)
gc = gspread.authorize(CREDS)

SHEET_ID = st.secrets["SPREADSHEET_ID"]
book = gc.open_by_key(SHEET_ID)

cfg_sheet = book.sheet1
users_sheet = book.worksheet("users")

# ---------------------------
# Helpers
# ---------------------------
def nz(v):
    return float(v) if v not in (None, "") else 0.0


def _to_bool(v):
    return str(v).lower() in ("1", "true", "yes", "y")


# ---------------------------
# Config from Google Sheets
# ---------------------------
def load_cfg():
    rows = cfg_sheet.get_all_records()
    cfg = {}
    for r in rows:
        k = str(r.get("key", "")).strip()
        if k:
            cfg[k] = float(r.get("value", 0))
    return cfg


def save_cfg(cfg):
    data = cfg_sheet.get_all_values()
    headers = [h.lower() for h in data[0]]
    key_col = headers.index("key") + 1
    val_col = headers.index("value") + 1

    key_to_row = {}
    for i in range(1, len(data)):
        key_to_row[data[i][key_col - 1]] = i + 1

    updates = []
    for k, v in cfg.items():
        if k in key_to_row:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(key_to_row[k], val_col),
                "values": [[str(v)]]
            })

    if updates:
        cfg_sheet.batch_update(updates)


# ---------------------------
# Users / Auth
# ---------------------------
@st.cache_data(ttl=60)
def load_users():
    rows = users_sheet.get_all_records()
    users = {}
    for r in rows:
        users[r["username"]] = {
            "hash": r["password_hash"],
            "role": r.get("role", "user"),
            "active": _to_bool(r.get("active", True)),
        }
    return users


def verify_login(username, password):
    users = load_users()
    u = users.get(username)
    if not u or not u["active"]:
        return False, None
    if bcrypt.checkpw(password.encode(), u["hash"].encode()):
        return True, u["role"]
    return False, None


# ---------------------------
# ECB FX
# ---------------------------
@st.cache_data(ttl=3600)
def get_gbp_rate():
    try:
        r = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=10,
        )
        tree = ET.fromstring(r.content)
        ns = {"d": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        date = tree.find(".//d:Cube[@time]", ns).attrib["time"]
        gbp = float(tree.find(".//d:Cube[@currency='GBP']", ns).attrib["rate"])
        return round(1 / gbp, 4), date
    except:
        return 1.1534, "fallback"


# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

# ---------------------------
# Login
# ---------------------------
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
                st.error("Invalid login")
    st.stop()

# ---------------------------
# Load config
# ---------------------------
cfg = load_cfg()
rate, rate_date = get_gbp_rate()
is_admin = st.session_state.role == "admin"

tabs = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tabs.append("💰 Profit Tool")   # <<< ADDED
    tabs.append("⚙️ Admin")
tabs = st.tabs(tabs)

# ---------------------------
# Extra fees
# ---------------------------
def extra_fees(prefix):
    with st.expander("Extra fees (optional)"):
        reg = st.number_input("Extra registration (€)", value=None, step=10.0, key=f"{prefix}_reg")
        ins = st.number_input("Insurance CY (€)", value=None, step=10.0, key=f"{prefix}_ins")
        co2 = st.number_input("CO₂ / inspection (€)", value=None, step=10.0, key=f"{prefix}_co2")
    return nz(reg) + nz(ins) + nz(co2)


# ---------------------------
# UK TAB
# ---------------------------
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase (GBP)", value=None, step=100.0)
    transport = st.number_input("Transport (GBP)", value=None, step=50.0)
    insurance = st.number_input("Insurance (EUR)", value=None, step=10.0)

    extras = extra_fees("uk")

    if st.button("Calculate UK"):
        purchase, transport, insurance = nz(purchase), nz(transport), nz(insurance)

        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate

        cif = purchase_eur + transport_eur + insurance
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_items = {
            "MOT": cfg["mot"],
            "Plates": cfg["plates"],
            "Road Tax": cfg["road_tax"],
            "Registration": cfg["registration"],
            "Certifying Officer": cfg["certifying_officer"],
            "Service": cfg["service"],
            "Customs agent": cfg["customs_agent"],
            "Port charges": cfg["port_charges"],
        }

        cy_total = sum(cy_items.values())
        total = cif + duty + vat + cy_total + extras

        # <<< ADDED (state only)
        st.session_state.last_total = total
        st.session_state.last_vat = vat

        st.success(f"Final total: €{total:,.2f}")

# ---------------------------
# JAPAN TAB
# ---------------------------
with tabs[1]:
    purchase = st.number_input("Purchase (EUR)", value=None, step=500.0)
    shipping = st.number_input("Shipping (EUR)", value=None, step=100.0)

    extras = extra_fees("jp")

    if st.button("Calculate Japan"):
        purchase, shipping = nz(purchase), nz(shipping)

        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_items = {
            "MOT": cfg["mot"],
            "Plates": cfg["plates"],
            "Road Tax": cfg["road_tax"],
            "Registration": cfg["registration"],
            "Certifying Officer": cfg["certifying_officer"],
            "Service": cfg["service"],
            "Customs agent": cfg["customs_agent"],
            "Port charges": cfg["port_charges"],
            "SVA (Japan)": cfg["sva_japan"],
        }

        cy_total = sum(cy_items.values())
        total = cif + duty + vat + cy_total + extras

        # <<< ADDED (state only)
        st.session_state.last_total = total
        st.session_state.last_vat = vat

        st.success(f"Final total: €{total:,.2f}")

# ---------------------------
# PROFIT TOOL (ADMIN ONLY)
# ---------------------------
if is_admin:
    with tabs[2]:
        st.subheader("💰 Profit Tool")

        if "last_total" not in st.session_state:
            st.info("Run a UK or Japan calculation first.")
        else:
            cost_net = st.session_state.last_total - st.session_state.last_vat
            st.write(f"**Car cost (net of CY VAT): €{cost_net:,.2f}**")

# ---------------------------
# ADMIN TAB
# ---------------------------
if is_admin:
    with tabs[3]:
        st.subheader("Admin settings (Google Sheets)")
        cfg_edit = dict(cfg)

        for k in cfg_edit:
            cfg_edit[k] = st.number_input(
                k.replace("_", " ").title(),
                value=float(cfg_edit[k]),
                step=1.0,
            )

        if st.button("Save"):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved permanently to Google Sheets")
            st.rerun()

# ---------------------------
# Footer
# ---------------------------
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True,
)
