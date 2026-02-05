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
            cost_net = final_total - cy_vat

            st.markdown(f"**Car cost (net of Cyprus VAT): €{cost_net:,.2f}**")

            st.divider()

            # ------------------------------------------------
            # PROFIT → REQUIRED SELLING PRICE
            # ------------------------------------------------
            st.markdown("### 🎯 Target profit → Selling price")

            target_profit = st.number_input(
                "Target profit (€)",
                value=None,
                step=500.0,
                placeholder="Enter desired profit"
            )

            if target_profit and target_profit > 0:
                net_sale_required = cost_net + target_profit
                sell_price_required = net_sale_required * 1.19
                vat_on_sale = sell_price_required * 19 / 119

                st.success(
                    f"To make **€{target_profit:,.2f}**, "
                    f"sell at **€{sell_price_required:,.2f}** "
                    f"(VAT €{vat_on_sale:,.2f})"
                )

            st.divider()

            # ------------------------------------------------
            # SELLING PRICE → PROFIT
            # ------------------------------------------------
            st.markdown("### 💶 Selling price → Profit")

            selling_price = st.number_input(
                "Selling price (VAT included €)",
                value=None,
                step=500.0,
                placeholder="Enter selling price"
            )

            if selling_price and selling_price > 0:
                vat_sale = selling_price * 19 / 119
                net_sale = selling_price - vat_sale
                profit = net_sale - cost_net

                st.success(
                    f"Net sale: **€{net_sale:,.2f}**  \n"
                    f"VAT on sale: **€{vat_sale:,.2f}**  \n"
                    f"Profit: **€{profit:,.2f}**"
                )

            st.info(
                "ℹ️ Selling prices include 19% VAT. "
                "Profit is calculated on net amounts only."
            )
