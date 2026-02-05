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

SHEET_ID = st.secrets["SPREADSHEET_ID"]
book = gc.open_by_key(SHEET_ID)

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
# Config (Google Sheets)
# ============================================================
def load_cfg():
    rows = cfg_sheet.get_all_records()
    cfg = {}
    for r in rows:
        key = str(r.get("key", "")).strip()
        if key:
            cfg[key] = float(r.get("value", 0.0))
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
                "values": [[str(v)]],
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


def verify_login(username, password):
    users = load_users()
    u = users.get(username)
    if not u or not u["active"]:
        return False, None
    if bcrypt.checkpw(password.encode(), u["hash"].encode()):
        return True, u["role"]
    return False, None


# ============================================================
# ECB FX (LIVE)
# ============================================================
@st.cache_data(ttl=1800)
def get_gbp_rate():
    r = requests.get(
        "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        timeout=10,
    )
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

# ---------------- Login ----------------
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

# ---------------- State ----------------
cfg = load_cfg()
rate, rate_date = get_gbp_rate()
is_admin = st.session_state.role == "admin"

tabs = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tabs.append("⚙️ Admin")
tabs = st.tabs(tabs)

# ============================================================
# Extra fees
# ============================================================
def extra_fees(prefix):
    with st.expander("Extra fees (optional)"):
        reg = st.number_input("Extra registration (€)", value=None, step=10.0, key=f"{prefix}_reg")
        ins = st.number_input("Insurance CY (€)", value=None, step=10.0, key=f"{prefix}_ins")
        co2 = st.number_input("CO₂ / inspection (€)", value=None, step=10.0, key=f"{prefix}_co2")
    return nz(reg) + nz(ins) + nz(co2)


# ============================================================
# 🇬🇧 UK TAB
# ============================================================
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} (ECB {rate_date})")

    purchase = st.number_input("Purchase (GBP)", value=None, step=100.0)
    transport = st.number_input("Transport (GBP)", value=None, step=50.0)
    insurance = st.number_input("Insurance (EUR)", value=None, step=10.0)

    extras = extra_fees("uk")

    if st.button("Calculate UK", use_container_width=True):
        purchase, transport, insurance = nz(purchase), nz(transport), nz(insurance)

        vat_uk = purchase * cfg["vat_uk_percent"] / 100
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate
        cif = purchase_eur + transport_eur + insurance

        duty = cif * cfg["duty_percent_10"] / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"] +
            cfg["registration"] + cfg["certifying_officer"] +
            cfg["service"] + cfg["customs_agent"] + cfg["port_charges"]
        )

        total = cif + duty + vat + cy_fees + extras

        # store for profit tool
        st.session_state.last_final_total = total
        st.session_state.last_cy_vat = vat

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty (10%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")


# ============================================================
# 🇯🇵 JAPAN TAB
# ============================================================
with tabs[1]:
    c1, c2 = st.columns([2, 1])
    with c1:
        purchase = st.number_input("Purchase (EUR)", value=None, step=500.0)
    with c2:
        duty_choice = st.radio("Duty rate", ["10%", "5%"], horizontal=True)

    shipping = st.number_input("Shipping (EUR)", value=None, step=100.0)
    extras = extra_fees("jp")

    if st.button("Calculate Japan", use_container_width=True):
        purchase, shipping = nz(purchase), nz(shipping)
        cif = purchase + shipping

        duty_rate = cfg["duty_percent_5"] if duty_choice == "5%" else cfg["duty_percent_10"]
        duty = cif * duty_rate / 100
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100

        cy_fees = (
            cfg["mot"] + cfg["plates"] + cfg["road_tax"] +
            cfg["registration"] + cfg["certifying_officer"] +
            cfg["service"] + cfg["customs_agent"] +
            cfg["port_charges"] + cfg["sva_japan"]
        )

        total = cif + duty + vat + cy_fees + extras

        st.session_state.last_final_total = total
        st.session_state.last_cy_vat = vat

        st.success(f"Final total: €{total:,.2f}")

        st.markdown("### 📊 Import breakdown")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({duty_rate}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")


# ============================================================
# ⚙️ ADMIN TAB + 💰 PROFIT TOOL
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader("Admin Settings")

        cfg_edit = dict(cfg)
        for k in cfg_edit:
            label = k.replace("_", " ").title()
            if k == "duty_percent_10":
                label = "Duty Percent (10)"
            if k == "duty_percent_5":
                label = "Duty Percent (5)"
            cfg_edit[k] = st.number_input(label, value=float(cfg_edit[k]), step=1.0)

        if st.button("Save settings", use_container_width=True):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved permanently")
            st.rerun()

        # ---------------- PROFIT TOOL ----------------
        st.divider()
        st.subheader("💰 Profit Calculator")

        if "last_final_total" not in st.session_state:
            st.info("Run a UK or Japan calculation first.")
        else:
            cost_net = st.session_state.last_final_total - st.session_state.last_cy_vat
            st.write(f"**Car cost (net): €{cost_net:,.2f}**")

            target_profit = st.number_input("Target profit (€)", value=None, step=500.0)
            if target_profit:
                sell_price = (cost_net + target_profit) * 1.19
                vat_sale = sell_price * 19 / 119
                st.success(
                    f"Sell at €{sell_price:,.2f} "
                    f"(VAT €{vat_sale:,.2f})"
                )

            selling_price = st.number_input("Selling price (VAT incl €)", value=None, step=500.0)
            if selling_price:
                vat_sale = selling_price * 19 / 119
                net_sale = selling_price - vat_sale
                profit = net_sale - cost_net
                st.success(f"Profit: €{profit:,.2f}")


# ============================================================
# Footer
# ============================================================
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True
)
