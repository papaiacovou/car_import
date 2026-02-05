import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ============================================================
# 🌍 Language setup
# ============================================================
LANGS = {
    "EN": {
        "profit_title": "💰 Profit Calculator (Admin only)",
        "run_calc": "Run a UK or Japan calculation first.",
        "cost_net": "Car cost (net of CY VAT)",
        "target_profit": "Target profit (€)",
        "to_make": "To make €{profit:,.2f} profit:",
        "sell_price": "Sell price (VAT incl)",
        "vat_on_sale": "VAT on sale",
        "manual_sell": "Manual selling price (VAT incl €)",
        "at_price": "At selling price €{price:,.2f}:",
        "vat_payable": "VAT payable",
        "net_sale": "Net sale",
        "profit": "Profit",
    },
    "GR": {
        "profit_title": "💰 Υπολογισμός Κέρδους (Μόνο Διαχειριστής)",
        "run_calc": "Υπολογίστε πρώτα εισαγωγή από ΗΒ ή Ιαπωνία.",
        "cost_net": "Κόστος αυτοκινήτου (χωρίς ΦΠΑ Κύπρου)",
        "target_profit": "Στόχος κέρδους (€)",
        "to_make": "Για κέρδος €{profit:,.2f}:",
        "sell_price": "Τιμή πώλησης (με ΦΠΑ)",
        "vat_on_sale": "ΦΠΑ πώλησης",
        "manual_sell": "Χειροκίνητη τιμή πώλησης (με ΦΠΑ €)",
        "at_price": "Σε τιμή πώλησης €{price:,.2f}:",
        "vat_payable": "ΦΠΑ πληρωτέος",
        "net_sale": "Καθαρή πώληση",
        "profit": "Κέρδος",
    },
}

if "lang" not in st.session_state:
    st.session_state.lang = "EN"

with st.sidebar:
    st.radio(
        "🌐 Language",
        ["EN", "GR"],
        index=0 if st.session_state.lang == "EN" else 1,
        key="lang",
        horizontal=True,
    )

_ = LANGS[st.session_state.lang]

# ============================================================
# Google Sheets setup
# ============================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
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
    assert "duty_percent_10" in cfg, "Admin error: duty_percent_10 missing"
    return cfg

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
# FX
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
        r = requests.get(
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
            timeout=8,
        )
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
    tabs += ["💰 Profit Tool", "⚙️ Admin"]
tabs = st.tabs(tabs)

# ============================================================
# 💰 PROFIT TOOL (ADMIN ONLY)
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader(_["profit_title"])

        if "last_final_total" not in st.session_state:
            st.info(_["run_calc"])
        else:
            final_total = st.session_state.last_final_total
            cy_vat = st.session_state.last_cy_vat
            cost_net = final_total - cy_vat

            st.write(f"**{_['cost_net']}: €{cost_net:,.2f}**")
            st.divider()

            target_profit = st.number_input(
                _["target_profit"], value=None, step=500.0
            )

            if target_profit is not None:
                net_sale = cost_net + target_profit
                sell_price = net_sale * 1.19
                vat_sale = sell_price * 19 / 119

                st.success(
                    f"{_['to_make'].format(profit=target_profit)}\n\n"
                    f"• {_['sell_price']}: €{sell_price:,.2f}\n\n"
                    f"• {_['vat_on_sale']}: €{vat_sale:,.2f}"
                )

            st.divider()

            manual_sell = st.number_input(
                _["manual_sell"], value=None, step=500.0
            )

            if manual_sell is not None:
                vat_sale = manual_sell * 19 / 119
                net_sale = manual_sell - vat_sale
                profit = net_sale - cost_net

                st.info(
                    f"{_['at_price'].format(price=manual_sell)}\n\n"
                    f"• {_['vat_payable']}: €{vat_sale:,.2f}\n\n"
                    f"• {_['net_sale']}: €{net_sale:,.2f}\n\n"
                    f"• **{_['profit']}: €{profit:,.2f}**"
                )

# ============================================================
# Footer
# ============================================================
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True,
)
