import streamlit as st
import pandas as pd
import numpy as np
import io
from utils.supabase_client import get_supabase

st.set_page_config(page_title="Daily Performance", layout="wide")

st.markdown("""<style>
.stDataFrame {overflow-x: auto;}
thead tr th {background-color:#1a3a5c!important;color:white!important;font-weight:bold!important;}
</style>""", unsafe_allow_html=True)

# helpers
def find_col(df, *candidates):
    norm = {c.lower().replace(" ","_").replace("-","_"): c for c in df.columns}
    for cand in candidates:
        k = cand.lower().replace(" ","_").replace("-","_")
        if k in norm:
            return norm[k]
    return None

def fmt_num(v, dec=0):
    if pd.isna(v) or v == 0:
        return "-"
    if dec == 0:
        return f"{int(v):,}"
    return f"{v:,.{dec}f}"

def fmt_pct(v):
    if pd.isna(v):
        return "-"
    return f"{v:.2f}%"

def project_selector():
    try:
        sb = get_supabase()
        res = sb.table("projects").select("id,name,code,description").eq("is_active", True).order("name").execute()
        projects = res.data or []
    except Exception as e:
        st.error(f"Could not load projects: {e}")
        return None
    if not projects:
        st.warning("No projects found.")
        return None
    names = [p["name"] for p in projects]
    sel = st.selectbox("Project", names, key="daily_project_sel")
    return next((p for p in projects if p["name"] == sel), None)

@st.cache_data(ttl=300)
def load_project_file(project_id):
    try:
        sb = get_supabase()
        res = sb.table("uploads").select("file_url,filename,created_at").eq("project_id", project_id).order("created_at", desc=True).limit(1).execute()
        if not res.data:
            return None, "No uploaded file found for this project."
        row = res.data[0]
        file_url = row["file_url"]
        fname = row.get("filename", "file")
        raw = sb.storage.from_("uploads").download(file_url)
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw), low_memory=False)
        else:
            df = pd.read_excel(io.BytesIO(raw))
        df.columns = [str(c).strip() for c in df.columns]
        return df, None
    except Exception as e:
        return None, str(e)

SUCCESS_VALS = {"success", "successful", "1", "true", "yes", "completed", "approved", "1.0"}

def compute_daily_summary(df, merchant_filter, tx_type_filter):
    d = df.copy()
    col_merchant = find_col(d, "merchant", "team", "agent_team", "merchant_name", "project", "channel")
    col_type = find_col(d, "type", "transaction_type", "tx_type", "order_type")
    col_date = find_col(d, "date", "created_at", "transaction_date", "tx_date", "order_date", "create_time", "payment_date")
    col_amount = find_col(d, "amount", "dp_amount", "wd_amount", "order_amount", "pay_amount")
    col_status = find_col(d, "status", "transaction_status", "order_status", "result", "is_success")
    col_rdp = find_col(d, "rdp_count", "rop_count", "rwd_count", "mwd_count", "mdp_count", "manual_count", "is_manual", "is_rdp", "is_rwd")
    col_rdp_amt = find_col(d, "rdp_amount", "rop_amount", "rwd_amount", "mwd_amount", "mdp_amount", "manual_amount")
    col_fail_amt = find_col(d, "fail_amount", "failed_amount", "fail amount")
    if col_merchant and merchant_filter:
        mask_m = d[col_merchant].astype(str).str.upper().isin([m.upper() for m in merchant_filter])
        d = d[mask_m]
    if col_type and tx_type_filter:
        kw = tx_type_filter.lower()
        type_series = d[col_type].astype(str).str.lower().str.strip()
        if kw == "deposit":
            mask_t = (type_series.str.startswith("dep") | type_series.str.contains("^deposit")) & ~type_series.str.contains("revert")
        else:
            mask_t = (type_series.str.startswith("with") | type_series.str.startswith("wd") | type_series.str.contains("^withdraw")) & ~type_series.str.contains("revert")
        d = d[mask_t]
    if d.empty or col_date is None:
        return None
    d = d.copy()
    d["_date"] = pd.to_datetime(d[col_date], errors="coerce").dt.date
    d = d.dropna(subset=["_date"])
    if d.empty:
        return None
    if col_amount:
        d["_amount"] = pd.to_numeric(d[col_amount], errors="coerce").fillna(0)
    else:
        d["_amount"] = 0
    if col_rdp:
        rdp_vals = d[col_rdp].astype(str).str.lower()
        is_manual = rdp_vals.isin(["1", "true", "yes", "rdp", "rwd", "manual", "1.0"])
        if is_manual.sum() == 0:
            is_manual = d[col_rdp].fillna(0).astype(float) > 0
    else:
        is_manual = pd.Series(False, index=d.index)
    d["_is_manual"] = is_manual
    if col_status:
        d["_success"] = d[col_status].astype(str).str.lower().str.strip().isin(SUCCESS_VALS)
    else:
        d["_success"] = False
    if col_fail_amt:
        d["_fail_amt"] = pd.to_numeric(d[col_fail_amt], errors="coerce").fillna(0)
    else:
        d["_fail_amt"] = 0
    if col_rdp_amt:
        d["_rdp_amt"] = pd.to_numeric(d[col_rdp_amt], errors="coerce").fillna(0)
    else:
        d["_rdp_amt"] = d["_is_manual"].astype(float) * d["_amount"]
    is_dp = "deposit" in tx_type_filter.lower()
    mdp_lbl = "MDP" if is_dp else "MWD"
    rdp_lbl = "RDP" if is_dp else "RWD"
    dp_lbl = "DP" if is_dp else "WD"
    rows = []
    for date_val in sorted(d["_date"].unique()):
        day = d[d["_date"] == date_val]
        auto = day[~day["_is_manual"]]
        manual = day[day["_is_manual"]]
        total_count = len(day)
        total_amt = day["_amount"].sum()
        auto_count = len(auto)
        auto_amt = auto["_amount"].sum()
        mdp_count = len(manual)
        mdp_amt = manual["_amount"].sum()
        mdp_amt_pct = (mdp_amt / total_amt * 100) if total_amt > 0 else 0
        mdp_cnt_pct = (mdp_count / total_count * 100) if total_count > 0 else 0
        net_amt = auto_amt
        fail_amt = day["_fail_amt"].sum()
        fail_count = len(day[~day["_success"]])
        fail_pct = (fail_count / total_count * 100) if total_count > 0 else 0
        auto_success = auto["_success"].sum()
        auto_approve_pct = (auto_success / auto_count * 100) if auto_count > 0 else 0
        total_success = day["_success"].sum()
        total_approve_pct = (total_success / total_count * 100) if total_count > 0 else 0
        rdp_count = mdp_count
        rdp_amt = manual["_rdp_amt"].sum()
        rows.append({
            "Date": date_val.strftime("%m/%d"),
            dp_lbl: fmt_num(auto_amt, 2),
            f"{dp_lbl} Count": fmt_num(auto_count),
            mdp_lbl: fmt_num(mdp_amt, 2) if mdp_amt > 0 else "-",
            f"{mdp_lbl} Count": fmt_num(mdp_count) if mdp_count > 0 else "-",
            f"{mdp_lbl} Amount %": fmt_pct(mdp_amt_pct) if mdp_amt > 0 else "-",
            f"{mdp_lbl} Count %": fmt_pct(mdp_cnt_pct) if mdp_count > 0 else "-",
            f"Net {dp_lbl} Amount": fmt_num(net_amt, 2),
            "Failed Amount": fmt_num(fail_amt, 2) if fail_amt > 0 else "-",
            "Failed Count": fmt_num(fail_count) if fail_count > 0 else "-",
            "Failed Percentage": fmt_pct(fail_pct) if fail_count > 0 else "-",
            "Auto Approve %": fmt_pct(auto_approve_pct),
            "Total Approve %": fmt_pct(total_approve_pct),
            f"{rdp_lbl} Count": fmt_num(rdp_count) if rdp_count > 0 else "-",
            f"{rdp_lbl} Amount": fmt_num(rdp_amt, 2) if rdp_amt > 0 else "-",
            "_auto_amt": auto_amt, "_auto_count": auto_count,
            "_mdp_amt": mdp_amt, "_mdp_count": mdp_count,
            "_net_amt": net_amt, "_fail_amt": float(fail_amt),
            "_fail_count": fail_count, "_total_count": total_count,
            "_total_success": int(total_success), "_auto_success": int(auto_success),
            "_rdp_count": rdp_count, "_rdp_amt": float(rdp_amt),
        })
    if not rows:
        return None
    T_auto_amt = sum(r["_auto_amt"] for r in rows)
    T_auto_count = sum(r["_auto_count"] for r in rows)
    T_mdp_amt = sum(r["_mdp_amt"] for r in rows)
    T_mdp_count = sum(r["_mdp_count"] for r in rows)
    T_net_amt = sum(r["_net_amt"] for r in rows)
    T_fail_amt = sum(r["_fail_amt"] for r in rows)
    T_fail_count = sum(r["_fail_count"] for r in rows)
    T_total_count = sum(r["_total_count"] for r in rows)
    T_total_success = sum(r["_total_success"] for r in rows)
    T_auto_success = sum(r["_auto_success"] for r in rows)
    T_rdp_count = sum(r["_rdp_count"] for r in rows)
    T_rdp_amt = sum(r["_rdp_amt"] for r in rows)
    T_total_amt = T_auto_amt + T_mdp_amt
    T_mdp_amt_pct = (T_mdp_amt / T_total_amt * 100) if T_total_amt > 0 else 0
    T_mdp_cnt_pct = (T_mdp_count / T_total_count * 100) if T_total_count > 0 else 0
    T_fail_pct = (T_fail_count / T_total_count * 100) if T_total_count > 0 else 0
    T_auto_approve = (T_auto_success / T_auto_count * 100) if T_auto_count > 0 else 0
    T_total_approve = (T_total_success / T_total_count * 100) if T_total_count > 0 else 0
    total_row = {
        "Date": "Total",
        dp_lbl: fmt_num(T_auto_amt, 2),
        f"{dp_lbl} Count": fmt_num(T_auto_count),
        mdp_lbl: fmt_num(T_mdp_amt, 2) if T_mdp_amt > 0 else "-",
        f"{mdp_lbl} Count": fmt_num(T_mdp_count) if T_mdp_count > 0 else "-",
        f"{mdp_lbl} Amount %": fmt_pct(T_mdp_amt_pct) if T_mdp_amt > 0 else "-",
        f"{mdp_lbl} Count %": fmt_pct(T_mdp_cnt_pct) if T_mdp_count > 0 else "-",
        f"Net {dp_lbl} Amount": fmt_num(T_net_amt, 2),
        "Failed Amount": fmt_num(T_fail_amt, 2) if T_fail_amt > 0 else "-",
        "Failed Count": fmt_num(T_fail_count) if T_fail_count > 0 else "-",
        "Failed Percentage": fmt_pct(T_fail_pct) if T_fail_count > 0 else "-",
        "Auto Approve %": fmt_pct(T_auto_approve),
        "Total Approve %": fmt_pct(T_total_approve),
        f"{rdp_lbl} Count": fmt_num(T_rdp_count) if T_rdp_count > 0 else "-",
        f"{rdp_lbl} Amount": fmt_num(T_rdp_amt, 2) if T_rdp_amt > 0 else "-",
    }
    display_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    display_rows.append(total_row)
    return display_rows, dp_lbl, mdp_lbl, rdp_lbl

def render_daily_table(display_rows, title, dp_lbl, mdp_lbl, rdp_lbl):
    if not display_rows:
        st.info(f"No data to display for {title}")
        return
    df_out = pd.DataFrame(display_rows)
    n = len(df_out)
    rdp_cols = [f"{rdp_lbl} Count", f"{rdp_lbl} Amount"]
    def style_row(row):
        is_total = row.name == n - 1
        base = "background-color:#FFD700;color:#333;font-weight:bold;" if is_total else ""
        styles = [base] * len(row)
        for i, col in enumerate(df_out.columns):
            if col in rdp_cols:
                styles[i] = "background-color:#FF8C00;color:white;font-weight:bold;"
        return styles
    st.markdown(
        f'<div style="background:#1a3a5c;color:white;font-weight:bold;text-align:center;'
        f'padding:8px;border-radius:4px;margin-bottom:4px;font-size:15px;">{title}</div>',
        unsafe_allow_html=True
    )
    styled = df_out.style.apply(style_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

def show_daily():
    project = project_selector()
    if not project:
        st.info("Please select a project.")
        return
    proj_name = project.get("name", "")
    proj_id = project.get("id", "")
    proj_code = project.get("code", "")
    st.markdown(f"## Daily Performance — {proj_name}")
    with st.spinner("Loading uploaded file..."):
        df, err = load_project_file(proj_id)
    if err:
        st.error(f"Could not load file: {err}")
        return
    if df is None or df.empty:
        st.warning("No data found in the uploaded file.")
        return
    col_date = find_col(df, "date", "created_at", "transaction_date", "tx_date", "order_date", "create_time", "payment_date")
    date_label = ""
    if col_date:
        try:
            dates = pd.to_datetime(df[col_date], errors="coerce").dropna()
            if len(dates) > 0:
                date_label = f" ( {dates.min().strftime('%B %d')} - {dates.max().strftime('%d')} )"
        except Exception:
            pass
    is_vf = "VF" in proj_name.upper() or "VF" in proj_code.upper()
    if is_vf:
        merchant_filter = ["VF", "VF-INR", "VFINR"]
        configs = [
            (merchant_filter, "deposit", f"VF-INR — Deposit Daily Summary{date_label}"),
            (merchant_filter, "withdraw", f"VF-INR — Withdraw Daily Summary{date_label}"),
        ]
        tab_names = ["VF-INR (Deposit)", "VF-INR (Withdraw)"]
    else:
        merchant_filter = ["JP-JWINR", "DP-JWINR", "JP-INR", "DP-INR", "JPINR", "DPINR", "JP INR", "DP INR", "JP", "DP"]
        configs = [
            (merchant_filter, "deposit", f"JP-JWINR — Deposit Daily Summary{date_label}"),
            (merchant_filter, "withdraw", f"JP-JWINR — Withdraw Daily Summary{date_label}"),
        ]
        tab_names = ["JP-JWINR (Deposit)", "DP-JWINR (Withdraw)"]
    tabs = st.tabs(tab_names)
    for i, (mf, tx_type, title) in enumerate(configs):
        with tabs[i]:
            result = compute_daily_summary(df, mf, tx_type)
            if result:
                display_rows, dp_lbl, mdp_lbl, rdp_lbl = result
                render_daily_table(display_rows, title, dp_lbl, mdp_lbl, rdp_lbl)
            else:
                st.warning(f"No {tx_type} data found.")
                col_m = find_col(df, "merchant", "team", "agent_team", "merchant_name", "project", "channel")
                col_t = find_col(df, "type", "transaction_type", "tx_type", "order_type")
                if col_m:
                    st.caption(f"Merchant values found: {list(df[col_m].unique()[:20])}")
                if col_t:
                    st.caption(f"Type values found: {list(df[col_t].unique()[:20])}")
                st.caption(f"All columns: {list(df.columns)}")

show_daily()
