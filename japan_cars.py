# ============================================================
# 💰 PROFIT TOOL (ADMIN ONLY)
# ============================================================
if is_admin:
    with tabs[2]:
        st.subheader("💰 Profit Calculator (Admin only)")

        if "last_final_total" not in st.session_state:
            st.info("Run a UK or Japan calculation first.")
        else:
            final_total = st.session_state.last_final_total
            cy_vat = st.session_state.last_cy_vat

            # ✅ SAFE READ (FIX)
            cy_fees = st.session_state.get("last_cy_fees", 0.0)

            # ✅ Your rule (unchanged)
            cost_net = final_total - cy_vat + cy_fees

            st.write(f"**Car cost (net of CY VAT): €{cost_net:,.2f}**")

            st.divider()

            target_profit = st.number_input(
                "Target profit (€)",
                value=None,
                step=500.0,
                placeholder="e.g. 3000"
            )

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

            manual_sell = st.number_input(
                "Manual selling price (VAT incl €)",
                value=None,
                step=500.0,
                placeholder="e.g. 15000"
            )

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
