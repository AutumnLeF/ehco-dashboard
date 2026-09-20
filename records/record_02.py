from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

CHILLED_MAX_TEMP = 5.0  # Chilled food items must arrive <= 5.0°C


def extract_field(rec, keywords):
    """Deep search for matching keywords across flat or nested keys."""
    if not isinstance(rec, dict):
        return None
    clean_targets = [k.lower().replace("_", "").replace(" ", "").replace(".", "") for k in keywords]
    for k, v in rec.items():
        if v is None:
            continue
        k_norm = k.lower().replace("_", "").replace(" ", "").replace(".", "")
        for target in clean_targets:
            if target in k_norm:
                if not isinstance(v, (dict, list)):
                    s_val = str(v).strip()
                    if s_val and s_val.lower() not in ["none", "nan", ""]:
                        return v
        if isinstance(v, dict):
            found = extract_field(v, keywords)
            if found is not None:
                return found
        elif isinstance(v, list):
            for elem in v:
                if isinstance(elem, dict):
                    found = extract_field(elem, keywords)
                    if found is not None:
                        return found
    return None


def parse_record_02_submissions(raw_df):
    """Parses Record 02 Food Delivery submissions handling flat and nested schemas."""
    if raw_df.empty:
        return pd.DataFrame()

    rows = []
    for _, record in raw_df.iterrows():
        rec = record.to_dict()
        sub = rec.get("submission") if isinstance(rec.get("submission"), dict) else {}

        # 1. Date normalization (Direct paths + fallback)
        raw_date = (
            sub.get("date")
            or sub.get("Date")
            or rec.get("submission.date")
            or rec.get("submission.Date")
            or rec.get("Date")
            or rec.get("createdAt")
            or rec.get("dateTimeSubmitted")
            or extract_field(rec, ["date", "createdat"])
            or ""
        )
        parsed_dt = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_dt):
            parsed_dt = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")

        if pd.notna(parsed_dt):
            date_str = parsed_dt.strftime("%d/%m/%Y")
            date_obj = parsed_dt.date()
        else:
            date_str = str(raw_date)[:10]
            date_obj = None

        # 2. Location
        location = str(
            sub.get("Location")
            or sub.get("location")
            or rec.get("submission.Location")
            or rec.get("submission.location")
            or rec.get("Location")
            or "Receiving Bay"
        ).strip()

        # 3. Supplier Name
        sup_main = str(
            sub.get("Name of Supplier")
            or sub.get("Name_of_Supplier")
            or rec.get("submission.Name of Supplier")
            or extract_field(rec, ["nameofsupplier", "supplier"])
            or ""
        ).strip()

        sup_other = str(
            sub.get("Name of Supplier (Other)")
            or sub.get("Name_of_Supplier_Other")
            or rec.get("submission.Name of Supplier (Other)")
            or extract_field(rec, ["nameofsupplierother", "supplierother"])
            or ""
        ).strip()

        if sup_other and sup_other.lower() not in ["none", "nan", ""]:
            supplier = sup_other
        elif sup_main and sup_main.lower() not in ["other", "none", "nan", ""]:
            supplier = sup_main
        else:
            supplier = "Local Supplier"

        # 4. Delivery & Food Type
        delivery_type = str(
            sub.get("Delivery Type")
            or sub.get("Delivery_Type")
            or rec.get("submission.Delivery Type")
            or extract_field(rec, ["deliverytype"])
            or "Perishable"
        ).strip()

        food_type = str(
            sub.get("Food Type")
            or sub.get("Food_Type")
            or rec.get("submission.Food Type")
            or extract_field(rec, ["foodtype", "item", "product"])
            or "Goods Received"
        ).replace("•", "").strip()

        # 5. Temperature Check
        temp_req_raw = str(
            sub.get("Is a Temperature Required?")
            or sub.get("Is_a_Temperature_Required")
            or rec.get("submission.Is a Temperature Required?")
            or extract_field(rec, ["isatemperaturerequired", "temprequired"])
            or "Yes"
        ).strip().upper()
        temp_required = "NO" not in temp_req_raw

        temp_val_raw = (
            sub.get("Temperature °C")
            or sub.get("Temperature")
            or sub.get("temperature")
            or rec.get("submission.Temperature °C")
            or extract_field(rec, ["temperature", "temp"])
        )
        temp_num = pd.to_numeric(str(temp_val_raw).replace("°C", "").strip(), errors="coerce")

        # 6. Critical Limits: Packaging & labelling
        limits_raw = str(
            sub.get("Critical Limits: Packaging in good condition / Product in date / Product correctly labelled")
            or rec.get("submission.Critical Limits: Packaging in good condition / Product in date / Product correctly labelled")
            or extract_field(rec, ["criticallimits", "packaging", "condition"])
            or "Yes"
        ).strip().upper()
        condition_ok = "NO" not in limits_raw

        sign = (
            sub.get("Sign (Initial)")
            or sub.get("Sign")
            or sub.get("sign")
            or rec.get("submission.Sign (Initial)")
            or rec.get("submission.sign")
            or rec.get("Sign (Initial)")
            or extract_field(rec, ["signinitial", "sign", "initial"])
            or "Staff"
        )

        has_temp_breach = temp_required and pd.notna(temp_num) and (temp_num > CHILLED_MAX_TEMP)
        has_breach = has_temp_breach or (not condition_ok)

        rows.append({
            "Date_Str": date_str,
            "Date_Obj": date_obj,
            "Location": location,
            "Supplier": supplier,
            "Delivery_Type": delivery_type,
            "Food_Type": food_type,
            "Temp_Required": temp_required,
            "Temp": temp_num,
            "Temp_Disp": f"{temp_num}°C" if pd.notna(temp_num) else "Ambient",
            "Condition_OK": condition_ok,
            "Has_Breach": has_breach,
            "Sign": str(sign).strip(),
        })

    return pd.DataFrame(rows)


def render_record_02_view(raw_df, selected_day_str, start_date, end_date):
    """Renders Record 02 Daily Audit and 7-Day Card Matrix."""

    # DIAGNOSTIC EXPANDER
    with st.expander("🔍 Record 02 API & Ingestion Diagnostic", expanded=False):
        st.write(f"Total Raw Rows Received from API: **{len(raw_df)}**")
        if not raw_df.empty:
            st.write("Columns in raw_df:", list(raw_df.columns))
            st.dataframe(raw_df.head(5), use_container_width=True)

    df_items = parse_record_02_submissions(raw_df)

    if not df_items.empty and "Date_Obj" in df_items.columns and df_items["Date_Obj"].notna().any():
        range_df = df_items[
            (df_items["Date_Obj"] >= start_date)
            & (df_items["Date_Obj"] <= end_date)
        ]
    else:
        range_df = df_items.copy()

    tab_day, tab_matrix = st.tabs([
        f"📅 Daily Receiving Audit ({selected_day_str})",
        "📈 7-Day Delivery Matrix (1-Month Browser)"
    ])

    # -------------------------------------------------------------
    # TAB 1: DAILY DRILLDOWN
    # -------------------------------------------------------------
    with tab_day:
        day_df = (
            range_df[range_df["Date_Str"] == selected_day_str]
            if not range_df.empty
            else pd.DataFrame()
        )

        excursions = []
        compliant_deliveries = []

        if not day_df.empty:
            for _, r in day_df.iterrows():
                if r["Has_Breach"]:
                    excursions.append(r.to_dict())
                else:
                    compliant_deliveries.append(r.to_dict())

        k1, k2, k3 = st.columns(3)
        with k1:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#dc2626;">{len(excursions)}</div><div class="kpi-lbl">Delivery Temp Breaches</div></div>',
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#16a34a;">{len(compliant_deliveries)}</div><div class="kpi-lbl">Verified Deliveries</div></div>',
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f'<div class="kpi-box"><div class="kpi-num" style="color:#0f172a;">{len(day_df)}</div><div class="kpi-lbl">Total Batches Received</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#dc2626;">🔴 Rejected / Excursions ({len(excursions)})</div>',
                unsafe_allow_html=True,
            )
            if excursions:
                for exc in excursions:
                    err_msg = f"Temp: {exc['Temp_Disp']} (> 5°C)" if exc['Temp'] and exc['Temp'] > CHILLED_MAX_TEMP else "Packaging / Label Issue"
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #dc2626;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{exc['Food_Type']} • {exc['Supplier']}</div>
                        <div style="font-size:0.8rem; color:#dc2626; font-weight:600; margin-top:3px;">
                            {err_msg}
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Received By: {exc['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("All incoming goods arrived within critical temperature limits.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="kanban-col"><div class="kanban-h" style="color:#16a34a;">🟢 Accepted Compliant ({len(compliant_deliveries)})</div>',
                unsafe_allow_html=True,
            )
            if compliant_deliveries:
                for ok in compliant_deliveries:
                    st.markdown(
                        f"""
                    <div class="check-card" style="border-left: 5px solid #16a34a;">
                        <div style="font-weight:700; font-size:0.9rem; color:#0f172a;">{ok['Food_Type']}</div>
                        <div style="font-size:0.8rem; color:#334155; margin-top:3px;">
                            Supplier: <b>{ok['Supplier']}</b> &nbsp;|&nbsp; Temp: <b style="color:#16a34a;">{ok['Temp_Disp']}</b>
                        </div>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Type: {ok['Delivery_Type']} | Received By: {ok['Sign']}</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No deliveries logged for this date.")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 2: 7 FULL-WIDTH DATE COLUMNS
    # -------------------------------------------------------------
    with tab_matrix:
        total_days = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if "rec02_page" not in st.session_state:
            st.session_state.rec02_page = max(0, (total_days - 1) // 7)

        max_page = max(0, (total_days - 1) // 7)

        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("⬅️ Previous 7 Days", key="r02_prev", disabled=(st.session_state.rec02_page <= 0), use_container_width=True):
                st.session_state.rec02_page -= 1
                st.rerun()

        with nav3:
            if st.button("Next 7 Days ➡️", key="r02_next", disabled=(st.session_state.rec02_page >= max_page), use_container_width=True):
                st.session_state.rec02_page += 1
                st.rerun()

        p_start_idx = st.session_state.rec02_page * 7
        page_dates = all_dates[p_start_idx : p_start_idx + 7]

        with nav2:
            if page_dates:
                st.markdown(
                    f"<div style='text-align:center; font-weight:700; color:#0f172a; font-size:0.95rem; padding-top:6px;'>"
                    f"Showing: <b>{page_dates[0].strftime('%d/%m/%Y')}</b> to <b>{page_dates[-1].strftime('%d/%m/%Y')}</b> (Block {st.session_state.rec02_page + 1} of {max_page + 1})"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        cols = st.columns(7)

        # Headers
        for i, d in enumerate(page_dates):
            cols[i].markdown(f"""
            <div style="background:#0f172a; color:#ffffff; font-weight:700; font-size:0.82rem; padding:10px 2px; border-radius:6px; text-align:center; margin-bottom:8px;">
                {d.strftime('%d/%m (%a)')}
            </div>
            """, unsafe_allow_html=True)

        # Daily Cards
        for i, d in enumerate(page_dates):
            d_str = d.strftime("%d/%m/%Y")
            matches = pd.DataFrame()
            if not range_df.empty:
                if "Date_Obj" in range_df.columns:
                    matches = range_df[range_df["Date_Obj"] == d]
                if matches.empty and "Date_Str" in range_df.columns:
                    matches = range_df[range_df["Date_Str"] == d_str]

            with cols[i]:
                if matches.empty:
                    st.markdown("""
                    <div style="background:#ffffff; border:1px dashed #cbd5e1; border-radius:8px; padding:12px 6px; text-align:center; min-height:160px; display:flex; align-items:center; justify-content:center;">
                        <span style="color:#94a3b8; font-weight:600; font-size:0.82rem;">— No Deliveries</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    batch_count = len(matches)
                    has_day_breach = any(matches["Has_Breach"])

                    items_list = list(dict.fromkeys(matches["Food_Type"].dropna().tolist()))
                    items_txt = ", ".join(items_list)

                    suppliers_list = list(dict.fromkeys(matches["Supplier"].dropna().tolist()))
                    suppliers_txt = ", ".join(suppliers_list)

                    temps = matches[matches["Temp"].notna()]["Temp"].tolist()
                    if temps:
                        max_t = max(temps)
                        min_t = min(temps)
                        t_summary = f"{min_t}° to {max_t}°C" if min_t != max_t else f"{max_t}°C"
                    else:
                        t_summary = "Ambient"

                    signs = ", ".join(list(dict.fromkeys(matches["Sign"].dropna().tolist())))

                    if has_day_breach:
                        badge = '<span style="color:#dc2626; font-weight:800; font-size:0.9rem;">🔴 BREACH</span>'
                        card_border = "2px solid #dc2626"
                    else:
                        badge = f'<span style="color:#16a34a; font-weight:800; font-size:0.95rem;">✓ {batch_count} Passed</span>'
                        card_border = "1.5px solid #0f172a"

                    st.markdown(f"""
                    <div style="background:#ffffff; border:{card_border}; border-radius:8px; padding:10px 6px; text-align:center; min-height:160px; box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                        <div>{badge}</div>
                        <div style="height:1px; background:#cbd5e1; margin:6px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:700; color:#0f172a; line-height:1.25; word-wrap:break-word;">
                            {items_txt}
                        </div>
                        <div style="font-size:0.7rem; color:#475569; margin-top:3px;">
                            {suppliers_txt}
                        </div>
                        <div style="height:1px; background:#f1f5f9; margin:5px 0;"></div>
                        <div style="font-size:0.75rem; font-weight:600; color:#16a34a;">
                            Temp: {t_summary}
                        </div>
                        <div style="font-size:0.68rem; color:#64748b; margin-top:4px;">By: {signs}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.divider()

        with st.expander("📋 View All Individual Food Delivery Records (Table View)"):
            if not range_df.empty:
                show_cols = [
                    c for c in [
                        "Date_Str", "Supplier", "Food_Type", "Delivery_Type", "Temp_Disp", "Condition_OK", "Sign"
                    ] if c in range_df.columns
                ]
                st.dataframe(range_df[show_cols], use_container_width=True, hide_index=True)
