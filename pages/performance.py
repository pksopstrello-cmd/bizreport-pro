# BizReport Pro - Performance Page
# Agent Deposit & Withdraw Summary Tables
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def pt_to_seconds(val):
    try:
        if pd.isna(val) or str(val).strip() in ["", "-"]: return np.nan
        parts = str(val).strip().split(":")
        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+float(parts[2])
        elif len(parts) == 2: return int(parts[0])*60+float(parts[1])
        return float(val)
    except: return np.nan

def sec_fmt(sec):
    if sec is None or (isinstance(sec,float) and np.isnan(sec)): return "-"
    sec=int(sec)
    return f"{sec//3600}:{(sec%3600)//60:02d}:{sec%60:02d}"

def normalize_col(df, candidates):
    cols_lower = {c.lower().replace(" ","").replace("_",""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(" ","").replace("_","")
        if key in cols_lower: return cols_lower[key]
    return None

def safe_sum(series):
    try: return series.dropna().sum()
    except: return 0

BUCKET_COLS = ["\u22641 Min","1-3 Mins","3-5 Mins","5-10 Mins","10-15 Mins","15-30 Mins","30-60 Mins",">1 Hr"]
GROUPS = {
    "KS Group": ["ks group","ksgroup","ks-group"],
    "Ma Group": ["ma group","magroup","ma-group"],
    "JKPAY Group": ["jkpay group","jkpaygroup","jkpay-group"],
}
FIXED_ORDER = ["apluspay-wake","expay","kingpay","kingpayWD","okpay","oxpay",
               "paypay","paypay-wake","simplypay","smilepayz","vvpay","yfrdnqpay-wake"]

def build_agent_summary(df, tx_type="Deposit", merchant="JP-INR", date_from=None, date_to=None):
    type_col = normalize_col(df, ["Type","Transaction Type","TX Type"])
    merchant_col = normalize_col(df, ["Merchant","Team","Agent Team","Merchant Name"])
    agent_col = normalize_col(df, ["Agent Group","Agent","Agent Name","AgentGroup"])
    dff = df.copy()
    if type_col:
        dff = dff[dff[type_col].astype(str).str.lower().str.contains(tx_type.lower(), na=False)]
    if merchant_col and merchant:
        dff = dff[dff[merchant_col].astype(str).str.lower().str.contains(merchant.lower(), na=False)]
    date_col = normalize_col(df, ["Date","Transaction Date","Created At","Tx Date"])
    if date_col and date_from and date_to:
        try:
            dff[date_col] = pd.to_datetime(dff[date_col], errors="coerce")
            dff = dff[(dff[date_col]>=pd.Timestamp(date_from))&(dff[date_col]<=pd.Timestamp(date_to))]
        except: pass
    if tx_type == "Deposit":
        cnt_c=normalize_col(dff,["DP Count","Deposit Count","Count"])
        amt_c=normalize_col(dff,["DP Amount","Deposit Amount","Amount"])
        rdp_cnt=normalize_col(dff,["RDP Count","ROP Count","MDP Count","Manual Count"])
        rdp_amt=normalize_col(dff,["RDP Amount","ROP Amount","MDP Amount","Manual Amount"])
    else:
        cnt_c=normalize_col(dff,["WD Count","Withdraw Count","Count"])
        amt_c=normalize_col(dff,["WD Amount","Withdraw Amount","Amount"])
        rdp_cnt=normalize_col(dff,["RWD Count","MWD Count","Manual WD Count"])
        rdp_amt=normalize_col(dff,["RWD Amount","MWD Amount","Manual WD Amount"])
    pt_c=normalize_col(dff,["Avg PT","Processing Time","PT Auto","Avg Processing Time"])
    min_c=normalize_col(dff,["Min PT","Min Processing Time","MinPT"])
    max_c=normalize_col(dff,["Max PT","Max Processing Time","MaxPT"])
    fa_c=normalize_col(dff,["Fail Amount","Failed Amount","FailAmount"])
    fag_c=normalize_col(dff,["Failed Agent","Fail Agent","FailedAgent"])
    cpf_c=normalize_col(dff,["Create Payment Failed","CPF","CreatePaymentFailed"])
    fp_c=normalize_col(dff,["Failed Payment","Fail Payment","FailedPayment"])
    sr_c=normalize_col(dff,["Success Rate","SuccessRate"])
    bkt={b: normalize_col(dff,[b,b.replace(" ","")]) for b in BUCKET_COLS}
    if agent_col is None or len(dff)==0: return [],{}
    tot_cnt=safe_sum(dff[cnt_c]) if cnt_c else 0
    tot_amt=safe_sum(dff[amt_c]) if amt_c else 0
    rows=[]; rn=[0]
    def agg(sub, lbl, grp=False, tot=False, ind=False):
        c=safe_sum(sub[cnt_c]) if cnt_c else 0
        a=safe_sum(sub[amt_c]) if amt_c else 0
        rc=safe_sum(sub[rdp_cnt]) if rdp_cnt else 0
        ra=safe_sum(sub[rdp_amt]) if rdp_amt else 0
        cp=(c/tot_cnt*100) if tot_cnt else 0
        ap=(a/tot_amt*100) if tot_amt else 0
        avg_p=min_p=max_p=np.nan
        if pt_c:
            v=sub[pt_c].dropna().apply(pt_to_seconds); avg_p=v.mean() if len(v)>0 else np.nan
        if min_c:
            v=sub[min_c].dropna().apply(pt_to_seconds); min_p=v.min() if len(v)>0 else np.nan
        if max_c:
            v=sub[max_c].dropna().apply(pt_to_seconds); max_p=v.max() if len(v)>0 else np.nan
        bkts={b: safe_sum(sub[bkt[b]]) if bkt.get(b) else 0 for b in BUCKET_COLS}
        fa=safe_sum(sub[fa_c]) if fa_c else 0
        fag=int(safe_sum(sub[fag_c])) if fag_c else 0
        cpf=int(safe_sum(sub[cpf_c])) if cpf_c else 0
        fp=int(safe_sum(sub[fp_c])) if fp_c else 0
        sr=np.nan
        if sr_c:
            sv=sub[sr_c].dropna(); sr=sv.mean() if len(sv)>0 else np.nan
        if not tot: rn[0]+=1; num=rn[0]
        else: num=None
        return {"#":num,"Agent Group":("\u21b3 " if ind else "")+lbl,
                "Count":c,"Amount":a,
                "RDP Count":rc if rc>0 else None,"RDP Amount":ra if ra>0 else None,
                "Count%":cp,"Amount%":ap,
                "Avg PT":sec_fmt(avg_p),"Min PT":sec_fmt(min_p),"Max PT":sec_fmt(max_p),
                **{b:(int(v) if v>0 else None) for b,v in bkts.items()},
                "Fail Amount":fa if fa>0 else None,
                "Failed Agent":fag if fag>0 else None,
                "Create Payment Failed":cpf if cpf>0 else None,
                "Failed Payment":fp if fp>0 else None,
                "Success Rate":sr,
                "_g":grp,"_t":tot,"_i":ind}
    ags=dff[agent_col].dropna().unique().tolist()
    gm={}
    for gn,als in GROUPS.items():
        ms=[a for a in ags if any(al in str(a).lower() for al in als)]
        if ms: gm[gn]=ms
    grouped={a for ms in gm.values() for a in ms}
    for gn,ms in gm.items():
        gdf=dff[dff[agent_col].isin(ms)]
        rows.append(agg(gdf,gn,grp=True))
        r=agg(gdf,f"{gn} Total",ind=True); r["#"]=None; rows.append(r)
    acct=[a for a in ags if "acct" in str(a).lower()]
    if acct:
        rows.append(agg(dff[dff[agent_col].isin(acct)],"Agent_Acct_WD"))
    else:
        rows.append({"#":None,"Agent Group":"Agent_Acct_WD","Count":None,"Amount":None,
                     "RDP Count":None,"RDP Amount":None,"Count%":None,"Amount%":None,
                     "Avg PT":None,"Min PT":None,"Max PT":None,
                     **{b:None for b in BUCKET_COLS},"Fail Amount":None,
                     "Failed Agent":None,"Create Payment Failed":None,
                     "Failed Payment":None,"Success Rate":None,
                     "_g":False,"_t":False,"_i":False})
    ind_ags=[a for a in ags if a not in grouped and a not in set(acct)]
    def sk(a):
        al=str(a).lower()
        for i,f in enumerate(FIXED_ORDER):
            if f.lower() in al or al in f.lower(): return (0,i,al)
        return (1,0,al)
    for ag in sorted(ind_ags,key=sk):
        rows.append(agg(dff[dff[agent_col]==ag],str(ag)))
    tr=agg(dff,"Total/Average",tot=True); tr["#"]=None; rows.append(tr)
    if rdp_cnt:
        mm=dff[rdp_cnt].fillna(0)>0; auto_df=dff[~mm]
    else:
        auto_df=dff; mm=pd.Series([False]*len(dff),index=dff.index)
    pfx2="DP" if tx_type=="Deposit" else "WD"
    ar=agg(auto_df,f"\u2022 Auto (Normal {pfx2})",tot=True); ar["#"]=None; rows.append(ar)
    ml=f"\u2022 Manual ({'MDP' if tx_type=='Deposit' else 'MWD'})"
    if rdp_cnt and mm.any():
        mr=agg(dff[mm],ml,tot=True); mr["#"]=None; rows.append(mr)
    else:
        rows.append({"#":None,"Agent Group":ml,"Count":None,"Amount":None,
                     "RDP Count":None,"RDP Amount":None,"Count%":None,"Amount%":None,
                     "Avg PT":None,"Min PT":None,"Max PT":None,
                     **{b:None for b in BUCKET_COLS},"Fail Amount":None,
                     "Failed Agent":None,"Create Payment Failed":None,
                     "Failed Payment":None,"Success Rate":None,
                     "_g":False,"_t":True,"_i":False})
    return rows,{"total_count":tot_cnt,"total_amount":tot_amt}

def render_table(rows, title, tx_type="Deposit"):
    if not rows: st.warning(f"No data for {title}"); return
    pfx="DP" if tx_type=="Deposit" else "WD"
    rpfx="RDP" if tx_type=="Deposit" else "RWD"
    col_map={"#":"#","Agent Group":"Agent Group",
             "Count":f"Overall {pfx} Count","Amount":f"Overall {pfx} Amount",
             "RDP Count":f"{rpfx} Count","RDP Amount":f"{rpfx} Amount",
             "Count%":f"{pfx} Count Contribution","Amount%":f"{pfx} Amount Contribution",
             "Avg PT":"Avg PT (Auto Only)","Min PT":"Min PT (Auto)","Max PT":"Max PT (Auto)",
             **{b:b for b in BUCKET_COLS},
             "Fail Amount":"Fail Amount","Failed Agent":"Failed Agent",
             "Create Payment Failed":"Create Payment Failed",
             "Failed Payment":"Failed Payment","Success Rate":"Success Rate"}
    records=[]
    for r in rows:
        rec={}
        for k,v in col_map.items():
            val=r.get(k)
            if k in ["Amount","RDP Amount"]:
                rec[v]=f"{float(val):,.2f}" if val is not None else "-"
            elif k=="Fail Amount":
                rec[v]=f"{float(val):,.0f}" if val is not None else "-"
            elif k in ["Count","RDP Count","Failed Agent","Create Payment Failed","Failed Payment"]+list(BUCKET_COLS):
                rec[v]=str(int(val)) if val is not None else "-"
            elif k in ["Count%","Amount%"]:
                rec[v]=f"{float(val):.2f}%" if val is not None else "-"
            elif k=="Success Rate":
                rec[v]=f"{float(val):.2f}%" if val is not None and not (isinstance(val,float) and np.isnan(val)) else "-"
            else:
                rec[v]=str(val) if val is not None else "-"
        records.append(rec)
    st.markdown(f'<div style="background:#FF8C00;color:white;text-align:center;font-weight:bold;padding:8px 4px;font-size:13px;border-radius:3px 3px 0 0;">{title}</div>',unsafe_allow_html=True)
    df_s=pd.DataFrame(records)
    rc_cols=[f"{rpfx} Count",f"{rpfx} Amount"]
    def style_df(df):
        styles=pd.DataFrame("",index=df.index,columns=df.columns)
        for i,rd in enumerate(rows):
            for c in df.columns:
                if c in rc_cols: styles.iloc[i][c]="background-color:#FF8C00;color:white;font-weight:bold"
                elif rd.get("_t"): styles.iloc[i][c]="background-color:#FFD700;color:black;font-weight:bold"
                elif rd.get("_g"): styles.iloc[i][c]="background-color:#FFFACD;font-weight:bold"
                elif rd.get("_i"): styles.iloc[i][c]="background-color:#F0F8FF"
        return styles
    st.dataframe(df_s.style.apply(style_df,axis=None),use_container_width=True,hide_index=True,height=min(650,40+len(rows)*35))

# ─── MAIN ──────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Performance",layout="wide")
st.title("\U0001f4ca Performance \u2013 Agent Summary Tables")
st.markdown("Generate Agent Deposit & Withdraw summary tables from raw back-office data.")
c1,c2=st.columns(2)
with c1: date_from=st.date_input("Date From",value=datetime(2026,4,1))
with c2: date_to=st.date_input("Date To",value=datetime(2026,4,19))
proj_opts={"JP JW INR (JP-INR + DP-INR)":"JPJWINR","PredictGo VF-INR (VF)":"VFINR"}
sel_proj=st.selectbox("Select Project",list(proj_opts.keys()))
proj_code=proj_opts[sel_proj]
st.subheader("Upload Raw Back-Office Files")
c3,c4=st.columns(2)
with c3: dep_file=st.file_uploader("Deposit File (CSV/Excel)",type=["csv","xlsx","xls"],key="dep_f")
with c4: wd_file=st.file_uploader("Withdraw File (CSV/Excel)",type=["csv","xlsx","xls"],key="wd_f")
st.info("\U0001f4cc **Expected columns:** Agent Group, Merchant/Team, DP/WD Count, DP/WD Amount, RDP/RWD Count, RDP/RWD Amount, Avg PT, Min PT, Max PT, \u22641 Min, 1-3 Mins, 3-5 Mins, 5-10 Mins, 10-15 Mins, 15-30 Mins, 30-60 Mins, >1 Hr, Fail Amount, Failed Agent, Create Payment Failed, Failed Payment, Success Rate")
def load_f(f):
    if f is None: return None
    try: return pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
    except Exception as e: st.error(f"Error: {e}"); return None
df_dep=load_f(dep_file); df_wd=load_f(wd_file)
if df_dep is None and df_wd is None:
    st.info("\U0001f446 Upload deposit and/or withdraw files above to generate tables.")
    st.stop()
if df_dep is not None:
    with st.expander("\U0001f4cb Deposit File Preview"):
        st.write(list(df_dep.columns)); st.dataframe(df_dep.head(3))
if df_wd is not None:
    with st.expander("\U0001f4cb Withdraw File Preview"):
        st.write(list(df_wd.columns)); st.dataframe(df_wd.head(3))
dr=f"{date_from.strftime('%Y-%m-%d')} \u2014 {date_to.strftime('%Y-%m-%d')}"
if proj_code=="JPJWINR":
    for merchant in ["JP-INR","DP-INR"]:
        for tx_type,lbl in [("Deposit","Agent Deposit Data"),("Withdraw","Agent Withdraw Data")]:
            df_s=df_dep if tx_type=="Deposit" else df_wd
            if df_s is None: st.warning(f"No {tx_type.lower()} file uploaded."); continue
            st.markdown("---")
            rows,_=build_agent_summary(df_s,tx_type=tx_type,merchant=merchant,date_from=date_from,date_to=date_to)
            render_table(rows,f"{merchant} {lbl} ( {dr} )",tx_type=tx_type)
elif proj_code=="VFINR":
    for tx_type,lbl in [("Deposit","Agent Deposit Data"),("Withdraw","Agent Withdraw Data")]:
        df_s=df_dep if tx_type=="Deposit" else df_wd
        if df_s is None: st.warning(f"No {tx_type.lower()} file uploaded."); continue
        st.markdown("---")
        rows,_=build_agent_summary(df_s,tx_type=tx_type,merchant="VF",date_from=date_from,date_to=date_to)
        render_table(rows,f"VF {lbl} ( {dr} )",tx_type=tx_type)
