import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
from utils.supabase_client import get_supabase
# Project selector is embedded (not imported from modules.dashboard)
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
    sel = st.selectbox("Project", names, key="perf_project_sel")
    return next((p for p in projects if p["name"] == sel), None)

st.set_page_config(page_title="Performance", layout="wide")

st.markdown("""<style>
.stDataFrame {overflow-x: auto;}
thead tr th {background-color:#FF8C00!important;color:white!important;font-weight:bold!important;}
</style>""", unsafe_allow_html=True)

# ── helpers ──────────────────────────────────────────────────────────────────
def find_col(df, *candidates):
    norm = {c.lower().replace(" ","_").replace("-","_"): c for c in df.columns}
    for cand in candidates:
        k = cand.lower().replace(" ","_").replace("-","_")
        if k in norm:
            return norm[k]
    return None

def to_seconds(val):
    if pd.isna(val) or val in ("","-","N/A",None): return np.nan
    s = str(val).strip()
    try:
        parts = s.split(":")
        if len(parts)==3: return int(parts[0])*3600+int(parts[1])*60+float(parts[2])
        if len(parts)==2: return int(parts[0])*60+float(parts[1])
        return float(s)
    except: return np.nan

def fmt_hms(sec):
    if pd.isna(sec): return "-"
    sec = int(sec)
    h,rem = divmod(sec,3600); m,s = divmod(rem,60)
    if h>0: return f"{h}:{m:02d}:{s:02d}"
    return f"0:{m:02d}:{s:02d}"

def fmt_num(v, dec=0):
    if pd.isna(v) or v==0: return "-"
    if dec==0: return f"{int(v):,}"
    return f"{v:,.{dec}f}"

def fmt_pct(v):
    if pd.isna(v): return "-"
    return f"{v:.2f}%"

def pt_bucket(sec):
    if pd.isna(sec): return None
    if sec<=60:   return "le1"
    if sec<=180:  return "1to3"
    if sec<=300:  return "3to5"
    if sec<=600:  return "5to10"
    if sec<=900:  return "10to15"
    if sec<=1800: return "15to30"
    if sec<=3600: return "30to60"
    return "gt1hr"

PT_COLS = ["le1","1to3","3to5","5to10","10to15","15to30","30to60","gt1hr"]
PT_LABELS = ["≤1 Min","1-3 Mins","3-5 Mins","5-10 Mins","10-15 Mins","15-30 Mins","30-60 Mins",">1 Hr"]

AGENTS_ORDER = [
    "apluspay-wake","expay","kingpay","kingpayWD","okpay","oxpay",
    "paypay","paypay-wake","simplypay","smilepayz","vvpay","yfrdnqpay-wake"
]
GROUP_MAP = {
    "apluspay-wake":"KS Group","expay":"KS Group",
    "kingpay":"Ma Group","kingpayWD":"Ma Group",
    "okpay":"Ma Group","oxpay":"Ma Group",
    "paypay":"JKPAY Group","paypay-wake":"JKPAY Group",
    "simplypay":"JKPAY Group","smilepayz":"JKPAY Group",
    "vvpay":"JKPAY Group","yfrdnqpay-wake":"JKPAY Group"
}
GROUPS = ["KS Group","Ma Group","JKPAY Group"]

SUCCESS_VALS = {"success","successful","1","true","yes","completed","approved","1.0"}

# ── load file from Supabase storage ──────────────────────────────────────────
@st.cache_data(ttl=300)
def load_project_file(project_id):
    try:
        sb = get_supabase()
        res = sb.table("uploads").select("file_url,filename,created_at").eq("project_id", project_id).order("created_at", desc=True).limit(1).execute()
        if not res.data:
            return None, "No uploaded file found for this project."
        row = res.data[0]
        file_url = row["file_url"]
        fname = row.get("filename","file")
        raw = sb.storage.from_("uploads").download(file_url)
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw), low_memory=False)
        else:
            df = pd.read_excel(io.BytesIO(raw))
        df.columns = [str(c).strip() for c in df.columns]
        return df, None
    except Exception as e:
        return None, str(e)

# ── compute agent summary ─────────────────────────────────────────────────────
def compute_agent_summary(df, merchant_filter, tx_type_filter):
    """
    merchant_filter: list of merchant values to filter, e.g. ["JP-INR"] or ["VF"]
    tx_type_filter: "deposit" or "withdraw"
    Returns DataFrame with one row per agent.
    """
    d = df.copy()

    # normalize columns
    col_merchant  = find_col(d,"merchant","team","agent_team","merchant_name","project","channel")
    col_type      = find_col(d,"type","transaction_type","tx_type","order_type")
    col_agent     = find_col(d,"agent_group","agent","agent_name","agentgroup","pay_agent")
    col_amount    = find_col(d,"amount","dp_amount","wd_amount","order_amount","pay_amount")
    col_status    = find_col(d,"status","transaction_status","order_status","result","is_success")
    col_pt        = find_col(d,"processing_time","pt","auto_pt","avg_pt","response_time","duration")
    col_rdp       = find_col(d,"rdp_count","rop_count","rwd_count","mwd_count","mdp_count","manual_count","is_manual","is_rdp","is_rwd")
    col_rdp_amt   = find_col(d,"rdp_amount","rop_amount","rwd_amount","mwd_amount","mdp_amount","manual_amount")
    col_fail_amt  = find_col(d,"fail_amount","failed_amount","fail amount")
    col_fail_agent= find_col(d,"failed_agent","fail_agent")
    col_cpf       = find_col(d,"create_payment_failed","cpf")
    col_fp        = find_col(d,"failed_payment","fail_payment")

    # filter by merchant
    if col_merchant and merchant_filter:
        mask_m = d[col_merchant].astype(str).str.upper().isin([m.upper() for m in merchant_filter])
        d = d[mask_m]

    # filter by type
    if col_type and tx_type_filter:
        kw = tx_type_filter.lower()
        mask_t = d[col_type].astype(str).str.lower().str.contains(kw[:3])
        d = d[mask_t]

    if d.empty:
        return None

    # determine manual/RDP rows
    if col_rdp:
        rdp_vals = d[col_rdp].astype(str).str.lower()
        is_manual = rdp_vals.isin(["1","true","yes","rdp","rwd","manual","1.0"])
        if is_manual.sum()==0:
            is_manual = d[col_rdp].fillna(0).astype(float) > 0
    else:
        is_manual = pd.Series(False, index=d.index)

    # PT in seconds
    if col_pt:
        d["_pt_sec"] = d[col_pt].apply(to_seconds)
    else:
        d["_pt_sec"] = np.nan

    # success
    if col_status:
        d["_success"] = d[col_status].astype(str).str.lower().str.strip().isin(SUCCESS_VALS)
    else:
        d["_success"] = False

    # agent column
    if not col_agent:
        return None

    # normalize agent names to lowercase for matching
    d["_agent_norm"] = d[col_agent].astype(str).str.strip().str.lower()

    rows = []
    all_count = len(d)
    all_amount = pd.to_numeric(d[col_amount], errors="coerce").sum() if col_amount else 0

    for agent in AGENTS_ORDER:
        mask = d["_agent_norm"] == agent.lower()
        ag = d[mask]
        ag_auto = ag[~is_manual[mask]]
        ag_manual = ag[is_manual[mask]]

        count = len(ag)
        amount = pd.to_numeric(ag[col_amount], errors="coerce").sum() if col_amount else 0

        # RDP/RWD
        rdp_c = int(ag_manual["_agent_norm"].count()) if len(ag_manual)>0 else 0
        if col_rdp_amt:
            rdp_a = pd.to_numeric(ag_manual[col_rdp_amt], errors="coerce").sum()
        elif col_amount:
            rdp_a = pd.to_numeric(ag_manual[col_amount], errors="coerce").sum()
        else:
            rdp_a = 0
        rdp_a = rdp_a if rdp_c > 0 else 0

        # contributions
        cnt_pct = (count/all_count*100) if all_count>0 else 0
        amt_pct = (amount/all_amount*100) if all_amount>0 else 0

        # PT (auto only)
        auto_pt = ag_auto["_pt_sec"].dropna()
        avg_pt = auto_pt.mean() if len(auto_pt)>0 else np.nan
        min_pt = auto_pt.min() if len(auto_pt)>0 else np.nan
        max_pt = auto_pt.max() if len(auto_pt)>0 else np.nan

        # PT buckets (auto only)
        buckets = {b:0 for b in PT_COLS}
        for sec in auto_pt:
            b = pt_bucket(sec)
            if b: buckets[b] += 1

        # fail amount
        fail_amt = pd.to_numeric(ag[col_fail_amt], errors="coerce").sum() if col_fail_amt else 0

        # failed agent (unique)
        fail_ag = ag[col_fail_agent].nunique() if col_fail_agent else 0

        # CPF
        cpf = pd.to_numeric(ag[col_cpf], errors="coerce").sum() if col_cpf else 0

        # failed payment
        fp = pd.to_numeric(ag[col_fp], errors="coerce").sum() if col_fp else 0

        # success rate
        suc_rate = (ag["_success"].sum()/count*100) if count>0 else 0

        rows.append({
            "agent": agent,
            "count": count,
            "amount": amount,
            "rdp_c": rdp_c,
            "rdp_a": rdp_a,
            "cnt_pct": cnt_pct,
            "amt_pct": amt_pct,
            "avg_pt": avg_pt,
            "min_pt": min_pt,
            "max_pt": max_pt,
            **{f"pt_{b}": buckets[b] for b in PT_COLS},
            "fail_amt": fail_amt,
            "fail_ag": int(fail_ag),
            "cpf": cpf,
            "fp": fp,
            "suc_rate": suc_rate,
            "auto_count": len(ag_auto),
            "auto_amount": pd.to_numeric(ag_auto[col_amount], errors="coerce").sum() if col_amount else 0,
            "manual_count": len(ag_manual),
            "manual_amount": pd.to_numeric(ag_manual[col_amount], errors="coerce").sum() if col_amount else 0,
        })

    return rows, {
        "all_count": all_count, "all_amount": all_amount,
        "is_manual": is_manual, "d": d,
        "col_amount": col_amount, "col_fail_amt": col_fail_amt,
        "col_fail_agent": col_fail_agent, "col_cpf": col_cpf, "col_fp": col_fp,
        "col_rdp": col_rdp, "col_rdp_amt": col_rdp_amt,
    }

def render_agent_table(rows, totals_info, title, tx_type="deposit"):
    if not rows:
        st.info(f"No data found for {title}")
        return

    is_dp = "deposit" in tx_type.lower()
    rdp_lbl = "RDP" if is_dp else "RWD"
    cnt_lbl = "DP" if is_dp else "WD"

    d = totals_info["d"]
    is_manual = totals_info["is_manual"]
    all_count = totals_info["all_count"]
    all_amount = totals_info["all_amount"]
    col_amount = totals_info["col_amount"]
    col_fail_amt = totals_info["col_fail_amt"]
    col_fail_agent = totals_info["col_fail_agent"]
    col_cpf = totals_info["col_cpf"]
    col_fp = totals_info["col_fp"]

    # compute group rows
    group_rows = {}
    for grp in GROUPS:
        members = [a for a,g in GROUP_MAP.items() if g==grp]
        grp_rows = [r for r in rows if r["agent"] in members]
        if not grp_rows: continue
        gc = sum(r["count"] for r in grp_rows)
        ga = sum(r["amount"] for r in grp_rows)
        grc = sum(r["rdp_c"] for r in grp_rows)
        gra = sum(r["rdp_a"] for r in grp_rows)
        g_auto_pt = []
        for ag_name in members:
            mask = d["_agent_norm"] == ag_name.lower()
            auto_mask = mask & ~is_manual
            secs = d[auto_mask]["_pt_sec"].dropna().tolist()
            g_auto_pt.extend(secs)
        group_rows[grp] = {
            "count": gc, "amount": ga, "rdp_c": grc, "rdp_a": gra,
            "cnt_pct": gc/all_count*100 if all_count else 0,
            "amt_pct": ga/all_amount*100 if all_amount else 0,
            "avg_pt": np.mean(g_auto_pt) if g_auto_pt else np.nan,
            "min_pt": np.min(g_auto_pt) if g_auto_pt else np.nan,
            "max_pt": np.max(g_auto_pt) if g_auto_pt else np.nan,
            **{f"pt_{b}": sum(r[f"pt_{b}"] for r in grp_rows) for b in PT_COLS},
            "fail_amt": sum(r["fail_amt"] for r in grp_rows),
            "fail_ag": sum(r["fail_ag"] for r in grp_rows),
            "cpf": sum(r["cpf"] for r in grp_rows),
            "fp": sum(r["fp"] for r in grp_rows),
            "suc_rate": sum(r["suc_rate"]*r["count"] for r in grp_rows)/gc if gc>0 else 0,
        }

    # compute totals row
    auto_d = d[~is_manual]
    manual_d = d[is_manual]
    all_auto_pt = d[~is_manual]["_pt_sec"].dropna()
    tot_rdp_c = sum(r["rdp_c"] for r in rows)
    tot_rdp_a = sum(r["rdp_a"] for r in rows)

    tot_fail_amt = pd.to_numeric(d[col_fail_amt], errors="coerce").sum() if col_fail_amt else 0
    tot_fail_ag = d[col_fail_agent].nunique() if col_fail_agent else 0
    tot_cpf = pd.to_numeric(d[col_cpf], errors="coerce").sum() if col_cpf else 0
    tot_fp = pd.to_numeric(d[col_fp], errors="coerce").sum() if col_fp else 0
    tot_suc = d["_success"].sum()

    tot_auto_amt = pd.to_numeric(auto_d[col_amount], errors="coerce").sum() if col_amount else 0
    tot_manual_amt = pd.to_numeric(manual_d[col_amount], errors="coerce").sum() if col_amount else 0

    # build display rows
    display_rows = []
    row_styles = []
    row_idx = 0

    # header total row (merchant total)
    def make_total_row(label, c, a, rc, ra, cp, ap, avg, mn, mx, bkts, fa, fag, cpf, fp, sr):
        return {
            "#": "-", "Agent Group": label,
            f"Overall {cnt_lbl} Count": fmt_num(c),
            f"Overall {cnt_lbl} Amount": fmt_num(a,2),
            f"{rdp_lbl} Count": fmt_num(rc) if rc>0 else "-",
            f"{rdp_lbl} Amount": fmt_num(ra,2) if ra>0 else "-",
            f"{cnt_lbl} Count Contribution%": fmt_pct(cp),
            f"{cnt_lbl} Amount Contribution%": fmt_pct(ap),
            "Avg PT (Auto Only)": fmt_hms(avg),
            "Min PT (Auto)": fmt_hms(mn),
            "Max PT (Auto)": fmt_hms(mx),
            **{PT_LABELS[i]: fmt_num(bkts.get(PT_COLS[i],0)) for i in range(len(PT_COLS))},
            "Fail Amount": fmt_num(fa,2) if fa else "-",
            "Failed Agent": fmt_num(fag) if fag else "-",
            "Create Payment Failed": fmt_num(cpf) if cpf else "-",
            "Failed Payment": fmt_num(fp) if fp else "-",
            "Success Rate": fmt_pct(sr),
        }

    # top total bar
    all_bkts = {b: sum(r[f"pt_{b}"] for r in rows) for b in PT_COLS}
    top = make_total_row(
        f"{d['_agent_norm'].str.upper().iloc[0].split('-')[0] if len(d)>0 else ''} AGENT",
        all_count, all_amount, tot_rdp_c, tot_rdp_a,
        100.0, 100.0,
        all_auto_pt.mean() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt)>0 else np.nan,
        all_bkts, tot_fail_amt, tot_fail_ag, tot_cpf, tot_fp,
        tot_suc/all_count*100 if all_count>0 else 0
    )
    top["#"] = "-"
    display_rows.append(top)
    row_styles.append("top_total")

    for grp in GROUPS:
        if grp not in group_rows: continue
        g = group_rows[grp]
        # group header
        gr = make_total_row(
            grp, g["count"], g["amount"], g["rdp_c"], g["rdp_a"],
            g["cnt_pct"], g["amt_pct"], g["avg_pt"], g["min_pt"], g["max_pt"],
            {b: g[f"pt_{b}"] for b in PT_COLS},
            g["fail_amt"], g["fail_ag"], g["cpf"], g["fp"], g["suc_rate"]
        )
        gr["#"] = str(GROUPS.index(grp)+1)
        display_rows.append(gr); row_styles.append("group")
        # group total
        gt = dict(gr); gt["Agent Group"] = f"↳ {grp} Total"; gt["#"] = str(GROUPS.index(grp)+2)
        display_rows.append(gt); row_styles.append("group_total")

    # agent_acct_wd row
    acct = {"#": "7", "Agent Group": "Agent_Acct_WD"}
    for k in display_rows[0]:
        if k not in ("#","Agent Group"): acct[k] = "-"
    display_rows.append(acct); row_styles.append("normal")

    # individual agents
    r_idx = 8
    for r in rows:
        rd = make_total_row(
            r["agent"], r["count"], r["amount"], r["rdp_c"], r["rdp_a"],
            r["cnt_pct"], r["amt_pct"], r["avg_pt"], r["min_pt"], r["max_pt"],
            {b: r[f"pt_{b}"] for b in PT_COLS},
            r["fail_amt"], r["fail_ag"], r["cpf"], r["fp"], r["suc_rate"]
        )
        rd["#"] = str(r_idx); r_idx += 1
        display_rows.append(rd); row_styles.append("normal")

    # Total/Average row
    tot_row = make_total_row(
        "Total/Average",
        all_count, all_amount, tot_rdp_c, tot_rdp_a,
        100.0, 100.0,
        all_auto_pt.mean() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt)>0 else np.nan,
        all_bkts, tot_fail_amt, tot_fail_ag, tot_cpf, tot_fp,
        tot_suc/all_count*100 if all_count>0 else 0
    )
    tot_row["#"] = "-"
    display_rows.append(tot_row); row_styles.append("total")

    # Auto row
    auto_bkts = {}
    for b in PT_COLS:
        auto_bkts[b] = sum(r[f"pt_{b}"] for r in rows)  # all from auto only already
    auto_pct_c = len(auto_d)/all_count*100 if all_count else 0
    auto_pct_a = tot_auto_amt/all_amount*100 if all_amount else 0
    auto_row = make_total_row(
        f"• Auto (Normal {cnt_lbl})",
        len(auto_d), tot_auto_amt, 0, 0,
        auto_pct_c, auto_pct_a,
        all_auto_pt.mean() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.min() if len(all_auto_pt)>0 else np.nan,
        all_auto_pt.max() if len(all_auto_pt)>0 else np.nan,
        all_bkts, np.nan, np.nan, np.nan, np.nan, np.nan
    )
    auto_row["#"] = "L"
    display_rows.append(auto_row); row_styles.append("sub")

    # Manual row
    man_pct_c = len(manual_d)/all_count*100 if all_count else 0
    man_pct_a = tot_manual_amt/all_amount*100 if all_amount else 0
    man_row = make_total_row(
        f"• Manual (M{cnt_lbl})",
        len(manual_d) if len(manual_d)>0 else 0,
        tot_manual_amt if tot_manual_amt>0 else 0,
        0,0, man_pct_c, man_pct_a,
        np.nan, np.nan, np.nan,
        {b:0 for b in PT_COLS}, np.nan, np.nan, np.nan, np.nan,
        100.0 if len(manual_d)==0 else np.nan
    )
    man_row["#"] = "L"
    man_row["Avg PT (Auto Only)"] = "-"
    man_row["Min PT (Auto)"] = "N/A"
    man_row["Max PT (Auto)"] = "N/A"
    display_rows.append(man_row); row_styles.append("sub")

    # render table
    df_out = pd.DataFrame(display_rows)
    rdp_cols = [f"{rdp_lbl} Count", f"{rdp_lbl} Amount"]

    # style
    def style_row(row):
        style_type = row_styles[row.name] if row.name < len(row_styles) else "normal"
        base = ""
        if style_type == "top_total":
            base = "background-color:#1a1a2e;color:white;font-weight:bold;"
        elif style_type == "group":
            base = "background-color:#FFFACD;color:#333;font-weight:bold;"
        elif style_type == "group_total":
            base = "background-color:#E8F4FD;color:#333;"
        elif style_type == "total":
            base = "background-color:#FFD700;color:#333;font-weight:bold;"
        elif style_type == "sub":
            base = "background-color:#2a2a3e;color:#aaa;font-style:italic;"
        styles = [base]*len(row)
        for i, col in enumerate(df_out.columns):
            if col in rdp_cols:
                styles[i] = "background-color:#FF8C00;color:white;font-weight:bold;" + (";font-weight:bold" if style_type=="total" else "")
        return styles

    st.markdown(f"""<div style="background:#E67E22;color:white;font-weight:bold;text-align:center;
        padding:8px;border-radius:4px;margin-bottom:4px;font-size:15px;">{title}</div>""",
        unsafe_allow_html=True)

    styled = df_out.style.apply(style_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def show_performance():
    project = project_selector()
    if not project:
        st.info("Please select a project.")
        return

    proj_name = project.get("name","")
    proj_id   = project.get("id","")
    proj_code = project.get("code","")

    st.markdown(f"## Performance — {proj_name}")

    with st.spinner("Loading uploaded file..."):
        df, err = load_project_file(proj_id)

    if err:
        st.error(f"Could not load file: {err}")
        return
    if df is None or df.empty:
        st.warning("No data found in the uploaded file.")
        return

    st.success(f"Loaded {len(df):,} rows × {len(df.columns)} columns")

    # detect date range
    col_date = find_col(df,"date","created_at","transaction_date","tx_date","order_date","create_time","payment_date")
    date_label = ""
    if col_date:
        try:
            dates = pd.to_datetime(df[col_date], errors="coerce").dropna()
            if len(dates)>0:
                date_label = f" ( {dates.min().strftime('%Y-%m-%d')} — {dates.max().strftime('%Y-%m-%d')} )"
        except: pass

    # determine which merchants to show
    is_vf = "VF" in proj_name.upper() or "VF" in proj_code.upper()

    if is_vf:
        merchants = [("VF Agent","VF","deposit"),("VF Agent","VF","withdraw")]
        tabs = st.tabs(["VF (Deposit)","VF (Withdraw)"])
        for i, (tab_name, merchant, tx_type) in enumerate(merchants):
            with tabs[i]:
                title_lbl = "DP" if tx_type=="deposit" else "WD"
                res = compute_agent_summary(df, [merchant], tx_type)
                if res and res[0]:
                    rows, totals = res
                    render_agent_table(rows, totals, f"VF Agent {title_lbl} Data{date_label}", tx_type)
                else:
                    st.warning(f"No {tx_type} data found for VF merchant.")
    else:
        # JP JW INR: two merchants JP-INR and DP-INR
        tab_names = ["JP-JWINR (Deposit)","JP-JWINR (Withdraw)","DP-JWINR (Deposit)","DP-JWINR (Withdraw)"]
        tabs = st.tabs(tab_names)
        configs = [
            ("JP-JWINR","deposit","JP-JWINR Agent Deposit Data"),
            ("JP-JWINR","withdraw","JP-JWINR Agent Withdraw Data"),
            ("DP-JWINR","deposit","DP-JWINR Agent Deposit Data"),
            ("DP-JWINR","withdraw","DP-JWINR Agent Withdraw Data"),
        ]
        for i, (merchant, tx_type, title_base) in enumerate(configs):
            with tabs[i]:
                res = compute_agent_summary(df, [merchant], tx_type)
                if res and res[0]:
                    rows, totals = res
                    render_agent_table(rows, totals, f"{title_base}{date_label}", tx_type)
                else:
                    # try alternate merchant names
                    alt = {"JP-JWINR":["JP-INR","JPINR","JP INR","JP"],"DP-JWINR":["DP-INR","DPINR","DP INR","DP"]}
                    res2 = compute_agent_summary(df, alt.get(merchant,[]), tx_type)
                    if res2 and res2[0]:
                        rows, totals = res2
                        render_agent_table(rows, totals, f"{title_base}{date_label}", tx_type)
                    else:
                        st.warning(f"No {tx_type} data found for {merchant}. Check merchant column values in your CSV.")
                        col_m = find_col(df,"merchant","team","agent_team","merchant_name","project","channel")
                        if col_m:
                            vals = df[col_m].unique()[:20]
                            st.caption(f"Merchant values found: {list(vals)}")

show_performance()
