st.write(f"Duty ({duty_rate}%): €{duty:,.2f}")
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

# ============================================================
# 💰 PROFIT TOOL
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader("💰 Profit Calculator (Admin only)")

        if "last_final_total" not in st.session_state:
            st.info("Run a UK or Japan calculation first.")
        else:
            final_total = st.session_state.last_final_total
            cy_vat = st.session_state.last_cy_vat

            cost_net = final_total - cy_vat

            cyprus_fees = (
                cfg["mot"] + cfg["plates"] + cfg["road_tax"]
                + cfg["registration"] + cfg["certifying_officer"]
                + cfg["service"] + cfg["customs_agent"]
                + cfg["port_charges"]
            )

            if st.session_state.get("last_origin") == "JP":
                cyprus_fees += cfg["sva_japan"]

            cost_net += cyprus_fees

            st.write(f"**Car cost (net of CY VAT): €{cost_net:,.2f}**")

            st.divider()

            target_profit = st.number_input(
                "Target profit (€)",
                value=None,
                step=500.0,
                placeholder="e.g. 3000",
                key="target_profit",
            )

            if target_profit:
                selling_price = (cost_net + target_profit) * 1.19
                vat_on_sale = selling_price * 19 / 119
                st.success(
                    f"Sell price (VAT incl): €{selling_price:,.2f}\n\n"
                    f"VAT on sale: €{vat_on_sale:,.2f}"
                )

            st.divider()

            manual_sell = st.number_input(
                "Manual selling price (VAT incl €)",
                value=None,
                step=500.0,
                placeholder="e.g. 15000",
                key="manual_sell",
            )

            if manual_sell:
                vat_on_sale = manual_sell * 19 / 119
                net_sale = manual_sell - vat_on_sale
                profit = net_sale - cost_net
                st.info(f"Profit: €{profit:,.2f}")

            st.divider()

            if st.button("🔄 Reset Profit Tool", use_container_width=True):
                for k in (
                    "last_final_total",
                    "last_cy_vat",
                    "last_origin",
                    "target_profit",
                    "manual_sell",
                ):
                    st.session_state.pop(k, None)
                st.rerun()

# ============================================================
# ⚙️ ADMIN
# ============================================================
if is_admin:
    with tabs[3]:
        cfg_edit = dict(cfg)
        for k in cfg_edit:
            cfg_edit[k] = st.number_input(
                k.replace("_", " ").title(),
                value=float(cfg_edit[k]),
            )

        if st.button("Save settings", use_container_width=True):
            save_cfg(cfg_edit)
            st.cache_data.clear()
            st.success("Saved permanently")
            st.rerun()

# ============================================================
# 🚪 LOGOUT
# ============================================================
if is_admin:
    with tabs[4]:
        st.warning("You are about to log out.")
        if st.button("Confirm Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# ============================================================
# Footer
# ============================================================
st.markdown(
    "<hr><center>© 2025 Ioannis Papaiacovou. All rights reserved.</center>",
    unsafe_allow_html=True
)
