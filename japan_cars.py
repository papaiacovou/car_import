import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ---------------------------
# Google Sheets + Auth Config
# ---------------------------
ADMIN_PASSWORD = "i4ipapa"  # Role-based admin controls access; kept for reference
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES,
)
gc = gspread.authorize(CREDS)

SHEET_ID = st.secrets["SPREADSHEET_ID"]
book = gc.open_by_key(SHEET_ID)

# Config is stored in Sheet1: columns key/value
cfg_sheet = book.sheet1

# Users are stored in a worksheet named exactly "users"
users_sheet = book.worksheet("users")

# ---------------------------
# Helpers
# ---------------------------
def nz(v):
    return float(v) if v not in (None, "") else 0.0


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("true", "1", "yes", "y", "on")


# ---------------------------
# Config load/save (Sheet1)
# ---------------------------
def load_cfg():
    """
    Reads Sheet1 as key/value rows. Requires headers: key, value (row 1).
    Returns dict[str, float].
    """
    rows = cfg_sheet.get_all_records()  # uses row 1 as headers
    cfg = {}
    for row in rows:
        k = str(row.get("key", "")).strip()
        if not k:
            continue
        v = row.get("value", 0)
        try:
            cfg[k] = float(v)
        except Exception:
            cfg[k] = 0.0
    return cfg


def save_cfg(cfg: dict):
    """
    Writes values back to Sheet1 by matching the 'key' column.
    Only updates existing keys (does not reorder rows).
    """
    all_values = cfg_sheet.get_all_values()
    if not all_values or len(all_values) < 2:
        raise RuntimeError("Config sheet (Sheet1) is empty or missing headers.")

    # Find header indexes
    headers = [h.strip().lower() for h in all_values[0]]
    if "key" not in headers or "value" not in headers:
        raise RuntimeError("Config sheet must have headers: key, value")

    key_col = headers.index("key") + 1
    val_col = headers.index("value") + 1

    # Map key -> row number
    key_to_row = {}
    for r in range(2, len(all_values) + 1):
        k = (all_values[r - 1][key_col - 1] if len(all_values[r - 1]) >= key_col else "").strip()
        if k:
            key_to_row[k] = r

    # Batch updates (values column)
    updates = []
    for k, v in cfg.items():
        if k in key_to_row:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(key_to_row[k], val_col),
                "values": [[str(v)]],
            })

    if updates:
        cfg_sheet.batch_update(updates)


# ---------------------------
# Users load + auth (users worksheet)
# ---------------------------
@st.cache_data(ttl=60)
def load_users():
    """
    Reads users worksheet rows as dicts.
    Expected columns: username, password_hash, role, active
    """
    rows = users_sheet.get_all_records()
    users = {}
    for row in rows:
        username = str(row.get("username", "")).strip()
        if not username:
            continue
        users[username] = {
            "password_hash": str(row.get("password_hash", "")).strip(),
            "role": str(row.get("role", "user")).strip().lower() or "user",
            "active": _to_bool(row.get("active", True)),
        }
    return users


def verify_login(username: str, password: str):
    users = load_users()
    u = users.get(username)
    if not u or not u["active"]:
        return False, None

    stored_hash = u["password_hash"]
    if not stored_hash:
        return False, None

    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        ok = False

    if not ok:
        return False, None

    return True, u["role"]


def logout():
    st.session_state["auth"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.cache_data.clear()
    st.rerun()


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
    except Exception:
        return 1.1534, "fallback"


# ---------------------------
# App UI
# ---------------------------
st.set_page_config(page_title="Car Import Calculator", layout="centered")
st.title("🚗 Car Import Calculator")

# --- Authentication Gate ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""

if not st.session_state["auth"]:
    st.subheader("Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        ok, role = verify_login(username.strip(), password)
        if ok:
            st.session_state["auth"] = True
            st.session_state["username"] = username.strip()
            st.session_state["role"] = role or "user"
            st.success("Logged in.")
            st.rerun()
        else:
            st.error("Invalid username/password or user inactive.")

    st.stop()

# Sidebar status + logout
with st.sidebar:
    st.write(f"👤 **User:** {st.session_state['username']}")
    st.write(f"🔐 **Role:** {st.session_state['role']}")
    st.button("Logout", on_click=logout, use_container_width=True)

# Load config after login
cfg = load_cfg()
rate, rate_date = get_gbp_rate()

# Ensure required keys exist (so missing sheet rows don't crash)
REQUIRED_KEYS = [
    "vat_uk_percent",
    "duty_percent",
    "vat_cy_percent",
    "mot",
    "plates",
    "road_tax",
    "registration",
    "certifying_officer",
    "service",
    "sva_japan",
    "customs_agent",
    "port_charges",
]
for k in REQUIRED_KEYS:
    cfg.setdefault(k, 0.0)

is_admin = (st.session_state.get("role") == "admin")

# Tabs: Admin only visible for admins
tab_labels = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tab_labels.append("⚙️ Admin")
tabs = st.tabs(tab_labels)

# ---------------------------
# Extra fees (optional)
# NOTE: Customs agent + Port charges moved to Admin (Google Sheet config)
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

    purchase = st.number_input("Purchase (GBP)", value=None, step=100.0, key="uk_purchase")
    transport = st.number_input("Transport (GBP)", value=None, step=50.0, key="uk_transport")
    insurance = st.number_input("Insurance (EUR)", value=None, step=10.0, key="uk_insurance")

    extras = extra_fees("uk")

    if st.button("Calculate UK", use_container_width=True, key="btn_uk"):
        purchase = nz(purchase)
        transport = nz(transport)
        insurance = nz(insurance)

        # UK VAT on purchase (GBP)
        vat_uk = purchase * cfg["vat_uk_percent"] / 100.0

        # Convert purchase+UK VAT to EUR, convert transport to EUR, then CIF
        purchase_eur = (purchase + vat_uk) * rate
        transport_eur = transport * rate
        cif = purchase_eur + transport_eur + insurance

        duty = cif * cfg["duty_percent"] / 100.0
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100.0

        # Cyprus fees (shared, configurable)
        cy_fees = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + cfg["service"]
            + cfg["customs_agent"]   # moved from extra fees -> admin
            + cfg["port_charges"]    # moved from extra fees -> admin
        )

        total = cif + duty + vat + cy_fees + extras

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
        st.write(f"Service: €{cfg['service']:,.2f}")
        st.write(f"Customs agent: €{cfg['customs_agent']:,.2f}")
        st.write(f"Port charges: €{cfg['port_charges']:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# JAPAN TAB
# ---------------------------
with tabs[1]:
    purchase = st.number_input("Purchase (EUR)", value=None, step=500.0, key="jp_purchase")
    shipping = st.number_input("Shipping (EUR)", value=None, step=100.0, key="jp_shipping")

    extras = extra_fees("jp")

    if st.button("Calculate Japan", use_container_width=True, key="btn_jp"):
        purchase = nz(purchase)
        shipping = nz(shipping)

        cif = purchase + shipping
        duty = cif * cfg["duty_percent"] / 100.0
        vat = (cif + duty) * cfg["vat_cy_percent"] / 100.0

        # Cyprus fees + Japan-only SVA
        cy_fees = (
            cfg["mot"]
            + cfg["plates"]
            + cfg["road_tax"]
            + cfg["registration"]
            + cfg["certifying_officer"]
            + cfg["service"]
            + cfg["customs_agent"]   # moved from extra fees -> admin
            + cfg["port_charges"]    # moved from extra fees -> admin
            + cfg["sva_japan"]       # JAPAN ONLY
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
        st.write(f"Customs agent: €{cfg['customs_agent']:,.2f}")
        st.write(f"Port charges: €{cfg['port_charges']:,.2f}")
        st.write(f"SVA (Japan): €{cfg['sva_japan']:,.2f}")
        st.write(f"Extra fees: €{extras:,.2f}")


# ---------------------------
# ADMIN TAB (admins only)
# ---------------------------
if is_admin:
    with tabs[2]:
        st.subheader("Admin Settings (stored in Google Sheets)")

        cfg_edit = dict(cfg)

        # Show ONLY the known keys, in a clean order
        st.caption("Edit values below and click Save. Values persist in Google Sheets.")
        for k in REQUIRED_KEYS:
            cfg_edit[k] = st.number_input(
                k.replace("_", " ").title(),
                value=float(cfg_edit.get(k, 0.0)),
                step=1.0,
                key=f"adm_{k}"
            )

        if st.button("Save settings", use_container_width=True):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved to Google Sheets. Values persist permanently.")
            st.rerun()


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
