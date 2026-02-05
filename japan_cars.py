import streamlit as st
import requests
import xml.etree.ElementTree as ET
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

# ============================================================
# 🌍 Language setup (flags)
# ============================================================
if "lang" not in st.session_state:
    st.session_state.lang = "en"

T = {
    "en": {
        "title": "🚗 Car Import Calculator",
        "login": "Login",
        "username": "Username",
        "password": "Password",
        "invalid": "Invalid credentials",

        "purchase_gbp": "Purchase (GBP)",
        "transport_gbp": "Transport (GBP)",
        "insurance_eur": "Insurance (EUR)",

        "purchase_eur": "Purchase (EUR)",
        "shipping_eur": "Shipping (EUR)",
        "duty_rate": "Duty rate",

        "calculate_uk": "Calculate UK",
        "calculate_jp": "Calculate Japan",

        "final_total": "Final total",
        "import_breakdown": "📊 Import breakdown",
        "cyprus_fees": "🇨🇾 Cyprus fees",

        "profit_tool": "💰 Profit Calculator (Admin only)",
        "target_profit": "Target profit (€)",
        "manual_sell": "Manual selling price (VAT incl €)",

        "admin": "⚙️ Admin",
        "admin_settings": "Admin Settings",
        "save_settings": "Save settings",
        "saved": "Saved permanently",

        "run_calc_first": "Run a UK or Japan calculation first.",
        "car_cost_net": "Car cost (net of CY VAT):",

        "footer": "© 2025 Ioannis Papaiacovou. All rights reserved.",
    },
    "el": {
        "title": "🚗 Υπολογιστής Εισαγωγής Αυτοκινήτου",
        "login": "Σύνδεση",
        "username": "Όνομα χρήστη",
        "password": "Κωδικός",
        "invalid": "Λάθος στοιχεία σύνδεσης",

        "purchase_gbp": "Τιμή αγοράς (GBP)",
        "transport_gbp": "Μεταφορά (GBP)",
        "insurance_eur": "Ασφάλεια (EUR)",

        "purchase_eur": "Τιμή αγοράς (EUR)",
        "shipping_eur": "Μεταφορά (EUR)",
        "duty_rate": "Δασμός",

        "calculate_uk": "Υπολογισμός ΗΒ",
        "calculate_jp": "Υπολογισμός Ιαπωνία",

        "final_total": "Τελικό σύνολο",
        "import_breakdown": "📊 Ανάλυση εισαγωγής",
        "cyprus_fees": "🇨🇾 Τέλη Κύπρου",

        "profit_tool": "💰 Υπολογιστής Κέρδους (Μόνο Διαχειριστής)",
        "target_profit": "Στόχος κέρδους (€)",
        "manual_sell": "Χειροκίνητη τιμή πώλησης (με ΦΠΑ €)",

        "admin": "⚙️ Διαχείριση",
        "admin_settings": "Ρυθμίσεις Διαχειριστή",
        "save_settings": "Αποθήκευση",
        "saved": "Αποθηκεύτηκε μόνιμα",

        "run_calc_first": "Κάνε πρώτα υπολογισμό από UK ή Japan.",
        "car_cost_net": "Κόστος αυτοκινήτου (χωρίς ΦΠΑ Κύπρου):",

        "footer": "© 2025 Ioannis Papaiacovou. Με επιφύλαξη παντός δικαιώματος.",
    },
}

def _(k: str) -> str:
    return T.get(st.session_state.lang, T["en"]).get(k, k)

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

def num_text_input(label, key, placeholder=""):
    """
    Blank-by-default numeric input (text box), converted to float via nz().
    This avoids Streamlit's number_input(value=None) TypeError.
    """
    s = st.text_input(label, key=key, placeholder=placeholder)
    s = s.strip().replace(",", ".")
    if s == "":
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

# ============================================================
# Config from Google Sheets
# ============================================================
def load_cfg():
    rows = cfg_sheet.get_all_records()
    cfg = {r["key"]: float(r["value"]) for r in rows}
    assert "duty_percent_10" in cfg, "Admin error: duty_percent_10 missing"
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
# LIVE FX (market) + fallback
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

# Flag buttons
c1, c2, _sp = st.columns([1, 1, 10])
with c1:
    if st.button("🇬🇧", use_container_width=True):
        st.session_state.lang = "en"
        st.rerun()
with c2:
    if st.button("🇬🇷", use_container_width=True):
        st.session_state.lang = "el"
        st.rerun()

st.title(_("title"))

# Login gate
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = ""

if not st.session_state.auth:
    with st.form("login"):
        u = st.text_input(_("username"))
        p = st.text_input(_("password"), type="password")
        if st.form_submit_button(_("login")):
            ok, role = verify_login(u, p)
            if ok:
                st.session_state.auth = True
                st.session_state.role = role
                st.rerun()
            else:
                st.error(_("invalid"))
    st.stop()

cfg = load_cfg()
rate, rate_date, rate_src = get_gbp_rate()
is_admin = st.session_state.role == "admin"

# Tabs
tab_names = ["🇬🇧 UK", "🇯🇵 Japan"]
if is_admin:
    tab_names.extend(["💰 Profit Tool", _("admin")])
tabs = st.tabs(tab_names)

# ============================================================
# 🇬🇧 UK TAB (FULL BREAKDOWN) — LOGIC UNCHANGED
# ============================================================
with tabs[0]:
    st.caption(f"GBP → EUR: {rate} — updated {rate_date} ({rate_src})")

    purchase = num_text_input(_("purchase_gbp"), key="uk_purchase", placeholder="e.g. 12000")
    transport = num_text_input(_("transport_gbp"), key="uk_transport", placeholder="e.g. 500")
    insurance = num_text_input(_("insurance_eur"), key="uk_insurance", placeholder="e.g. 200")

    if st.button(_("calculate_uk"), use_container_width=True, key="btn_uk"):
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

        total = cif + duty + vat + cy_fees

        st.session_state.last_final_total = total
        st.session_state.last_cy_vat = vat

        st.success(f"{_('final_total')}: €{total:,.2f}")

        st.markdown(f"### {_('import_breakdown')}")
        st.write(f"Purchase EUR (incl UK VAT): €{purchase_eur:,.2f}")
        st.write(f"Transport EUR: €{transport_eur:,.2f}")
        st.write(f"Insurance: €{insurance:,.2f}")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty (10%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown(f"### {_('cyprus_fees')}")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"Road Tax: €{cfg['road_tax']:,.2f}")
        st.write(f"Registration: €{cfg['registration']:,.2f}")
        st.write(f"Certifying Officer: €{cfg['certifying_officer']:,.2f}")
        st.write(f"Service: €{cfg['service']:,.2f}")
        st.write(f"Customs agent: €{cfg['customs_agent']:,.2f}")
        st.write(f"Port charges: €{cfg['port_charges']:,.2f}")

# ============================================================
# 🇯🇵 JAPAN TAB (FULL BREAKDOWN) — LOGIC UNCHANGED
# ============================================================
with tabs[1]:
    purchase = num_text_input(_("purchase_eur"), key="jp_purchase", placeholder="e.g. 10000")
    shipping = num_text_input(_("shipping_eur"), key="jp_shipping", placeholder="e.g. 1500")
    duty_choice = st.radio(_("duty_rate"), ["10%", "5%"], horizontal=True, key="jp_duty_choice")

    if st.button(_("calculate_jp"), use_container_width=True, key="btn_jp"):
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

        st.session_state.last_final_total = total
        st.session_state.last_cy_vat = vat

        st.success(f"{_('final_total')}: €{total:,.2f}")

        st.markdown(f"### {_('import_breakdown')}")
        st.write(f"CIF: €{cif:,.2f}")
        st.write(f"Duty ({duty_rate}%): €{duty:,.2f}")
        st.write(f"Cyprus VAT: €{vat:,.2f}")

        st.markdown(f"### {_('cyprus_fees')}")
        st.write(f"MOT: €{cfg['mot']:,.2f}")
        st.write(f"Plates: €{cfg['plates']:,.2f}")
        st.write(f"Road Tax: €{cfg['road_tax']:,.2f}")
        st.write(f"Registration: €{cfg['registration']:,.2f}")
        st.write(f"Certifying Officer: €{cfg['certifying_officer']:,.2f}")
        st.write(f"Service: €{cfg['service']:,.2f}")
        st.write(f"Customs agent: €{cfg['customs_agent']:,.2f}")
        st.write(f"Port charges: €{cfg['port_charges']:,.2f}")
        st.write(f"SVA (Japan): €{cfg['sva_japan']:,.2f}")

# ============================================================
# 💰 PROFIT TOOL (ADMIN ONLY) — LOGIC UNCHANGED
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader(_("profit_tool"))

        if "last_final_total" not in st.session_state:
            st.info(_("run_calc_first"))
        else:
            final_total = st.session_state.last_final_total
            cy_vat = st.session_state.last_cy_vat
            cost_net = final_total - cy_vat

            st.write(f"**{_('car_cost_net')} €{cost_net:,.2f}**")
            st.divider()

            target_profit = st.number_input(_("target_profit"), value=None, step=500.0)
            if target_profit is not None:
                net_sale = cost_net + target_profit
                selling_price = net_sale * 1.19
                vat_on_sale = selling_price * 19 / 119

                st.success(
                    f"To make **€{target_profit:,.2f}** profit:\n\n"
                    f"• Sell price (VAT incl): **€{selling_price:,.2f}**\n\n"
                    f"• VAT on sale: **€{vat_on_sale:,.2f}**"
                )

            st.divider()

            manual_sell = st.number_input(_("manual_sell"), value=None, step=500.0)
            if manual_sell is not None:
                vat_on_sale = manual_sell * 19 / 119
                net_sale = manual_sell - vat_on_sale
                profit = net_sale - cost_net

                st.info(
                    f"At selling price **€{manual_sell:,.2f}**:\n\n"
                    f"• VAT payable: **€{vat_on_sale:,.2f}**\n\n"
                    f"• Net sale: **€{net_sale:,.2f}**\n\n"
                    f"• **Profit: €{profit:,.2f}**"
                )

# ============================================================
# ⚙️ ADMIN SETTINGS — LOGIC UNCHANGED
# ============================================================
if is_admin:
    with tabs[3]:
        st.subheader(_("admin_settings"))

        cfg_edit = dict(cfg)
        for k in cfg_edit:
            label = k.replace("_", " ").title()
            if k == "duty_percent_10":
                label = "Duty Percent (10)"
            if k == "duty_percent_5":
                label = "Duty Percent (5)"
            cfg_edit[k] = st.number_input(label, value=float(cfg_edit[k]))

        if st.button(_("save_settings"), use_container_width=True):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success(_("saved"))
            st.rerun()

# ============================================================
# Footer
# ============================================================
st.markdown(
    f"<hr><center>{_('footer')}</center>",
    unsafe_allow_html=True
)
