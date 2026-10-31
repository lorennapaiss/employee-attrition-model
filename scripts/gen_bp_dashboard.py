"""Generates dashboard/bp_attrition_dashboard.html from risk ranking CSV."""
import pandas as pd
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV  = os.path.join(BASE, 'data', 'raw', 'attrition_risk_ranking.csv')
OUT  = os.path.join(BASE, 'dashboard', 'bp_attrition_dashboard.html')

df = pd.read_csv(CSV)

# ── risk factor flags ────────────────────────────────────────────────────────
df['low_job_sat']     = df['JobSatisfaction']        <= 2
df['low_env_sat']     = df['EnvironmentSatisfaction'] <= 2
df['low_wlb']         = df['WorkLifeBalance']         <= 2
df['frequent_travel'] = df['BusinessTravel']          == 'Travel_Frequently'
df['is_single']       = df['MaritalStatus']           == 'Single'
df['new_hire']        = df['YearsAtCompany']          <  2
df['is_junior']       = df['JobLevel']                == 1
income_q1             = df['MonthlyIncome'].quantile(0.25)
df['low_income']      = df['MonthlyIncome']           <= income_q1

FACTOR_LABELS = {
    'low_job_sat':     'Baixa sat. trabalho',
    'low_env_sat':     'Baixa sat. ambiente',
    'low_wlb':         'WLB comprometido',
    'frequent_travel': 'Viagem frequente',
    'is_single':       'Solteiro(a)',
    'new_hire':        'Menos de 2 anos',
    'is_junior':       'Nível júnior',
    'low_income':      'Salário baixo',
}

PROB    = df['Probabilidade_Saida_Pct']
AT_RISK = df['Acao_RH'] == 'Conversa recomendada'

# ── KPIs ─────────────────────────────────────────────────────────────────────
kpis = {
    'total':     int(len(df)),
    'alto':      int((df['Faixa_Risco'] == 'Alto').sum()),
    'medio':     int((df['Faixa_Risco'] == 'Medio').sum()),
    'baixo':     int((df['Faixa_Risco'] == 'Baixo').sum()),
    'acao':      int(AT_RISK.sum()),
    'pct_risco': round((df['Faixa_Risco'] != 'Baixo').sum() / len(df) * 100, 1),
    'prob_media': round(float(PROB.mean()), 1),
}

# ── probability histogram (2.5pp bins) ───────────────────────────────────────
STEP = 2.5
hist = []
for i in range(40):
    lo = i * STEP
    hi = lo + STEP
    mask = (PROB >= lo) & ((PROB < hi) if i < 39 else (PROB <= hi))
    hist.append({'lo': lo, 'hi': hi, 'n': int(mask.sum())})

# ── dept breakdown ───────────────────────────────────────────────────────────
dept_rows = []
for dept in df['Department'].unique():
    s = df[df['Department'] == dept]
    dept_rows.append({
        'dept':      dept,
        'alto':      int((s['Faixa_Risco'] == 'Alto').sum()),
        'medio':     int((s['Faixa_Risco'] == 'Medio').sum()),
        'baixo':     int((s['Faixa_Risco'] == 'Baixo').sum()),
        'total':     int(len(s)),
        'pct_risco': round((s['Faixa_Risco'] != 'Baixo').sum() / len(s) * 100, 1),
    })
dept_rows.sort(key=lambda x: -x['pct_risco'])

# ── avg probability by tenure, per dept ──────────────────────────────────────
TENURE_BINS = [(i, i, str(i)) for i in range(11)] + [(11, 15, '11–15'), (16, 20, '16–20'), (21, 99, '21+')]
tenure = {'labels': [b[2] for b in TENURE_BINS], 'series': []}
for dept in df['Department'].value_counts().index:
    s = df[df['Department'] == dept]
    vals, ns = [], []
    for lo, hi, _ in TENURE_BINS:
        p = s.loc[s['YearsAtCompany'].between(lo, hi), 'Probabilidade_Saida_Pct']
        vals.append(round(float(p.mean()), 1) if len(p) >= 5 else None)
        ns.append(int(len(p)))
    tenure['series'].append({'dept': dept, 'values': vals, 'n': ns})

# ── roles: share of at-risk employees (top 6 + others) ───────────────────────
role_grp = (df.assign(at_risk=AT_RISK)
              .groupby('JobRole')
              .agg(n_risco=('at_risk', 'sum'), avg=('Probabilidade_Saida_Pct', 'mean'), total=('EmployeeID', 'size'))
              .sort_values('n_risco', ascending=False))
role_data = [{'role': r, 'n_risco': int(v.n_risco), 'avg': round(float(v.avg), 1), 'total': int(v.total)}
             for r, v in role_grp.head(6).iterrows()]
rest = role_grp.iloc[6:]
if len(rest):
    role_data.append({
        'role':    'Outros cargos',
        'n_risco': int(rest['n_risco'].sum()),
        'avg':     round(float((rest['avg'] * rest['total']).sum() / rest['total'].sum()), 1),
        'total':   int(rest['total'].sum()),
    })

# ── employee list (all, JS does filtering) ───────────────────────────────────
employees = []
for _, row in df.iterrows():
    factors = [lbl for col, lbl in FACTOR_LABELS.items() if row[col]]
    employees.append({
        'id':        int(row['EmployeeID']),
        'age':       int(row['Age']),
        'dept':      row['Department'],
        'role':      row['JobRole'],
        'level':     int(row['JobLevel']),
        'marital':   row['MaritalStatus'],
        'travel':    row['BusinessTravel'],
        'income':    int(row['MonthlyIncome']),
        'years':     int(row['YearsAtCompany']),
        'job_sat':   float(row['JobSatisfaction'])        if pd.notna(row['JobSatisfaction'])        else 0,
        'env_sat':   float(row['EnvironmentSatisfaction']) if pd.notna(row['EnvironmentSatisfaction']) else 0,
        'wlb':       float(row['WorkLifeBalance'])         if pd.notna(row['WorkLifeBalance'])         else 0,
        'prob':      float(row['Probabilidade_Saida_Pct']),
        'faixa':     row['Faixa_Risco'],
        'acao':      row['Acao_RH'] == 'Conversa recomendada',
        'factors':   factors,
    })
employees.sort(key=lambda x: -x['prob'])

payload = {
    'kpis':      kpis,
    'hist':      hist,
    'dept_data': dept_rows,
    'tenure':    tenure,
    'role_data': role_data,
    'employees': employees,
}
data_json = json.dumps(payload, ensure_ascii=False)

# ── HTML template ─────────────────────────────────────────────────────────────
HTML = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Attrition Risk · HR Business Partner</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}

:root{
  --page:#E8ECE8; --surface:#FFFFFF; --soft:#F6F6F4; --hover:#FAFAF8;
  --line:#ECECE9; --line-2:#E2E2DE;
  --ink:#151517; --text:#2A2A2E; --muted:#6E6E73; --subtle:#A1A1A6;
  /* status: risk tiers (always paired with a text label) */
  --alto:#E5486B; --alto-l:#FDEDF1;
  --medio:#E9B10F; --medio-l:#FDF6DD;
  --baixo:#1FAF55; --baixo-l:#E7F7EC;
  --lime:#C7E35A;
  /* categorical: departments (validated CVD-safe) */
  --d1:#4263EB; --d2:#0E9AA7; --d3:#9C36B5;
  --font:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;
  --radius:14px;
}

html{scroll-behavior:smooth}
body{
  background:var(--page);
  color:var(--text);
  font-family:var(--font);
  font-size:14px;
  font-feature-settings:'tnum' 1,'cv11' 1;
  -webkit-font-smoothing:antialiased;
  padding:28px;
  min-height:100vh;
}
button,input,select{font-family:inherit}
svg.i{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}

/* ── APP FRAME ───────────────────────────────────────────────── */
.app{
  max-width:1320px;
  margin:0 auto;
  background:var(--surface);
  border-radius:var(--radius);
  box-shadow:0 1px 2px rgba(20,20,20,.04),0 24px 48px -24px rgba(20,20,20,.18);
  overflow:hidden;
}

/* ── TOP BAR ─────────────────────────────────────────────────── */
.topbar{
  display:grid;
  grid-template-columns:1fr auto 1fr;
  align-items:center;
  padding:0 18px;
  height:60px;
  border-bottom:1px solid var(--line);
}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;color:var(--ink);font-size:.95rem;letter-spacing:-.01em}
.brand-mark{
  width:28px;height:28px;border-radius:7px;background:var(--ink);
  display:grid;place-items:center;color:#fff;
}
.brand-mark svg{width:15px;height:15px}
.brand small{display:block;font-size:.68rem;font-weight:500;color:var(--muted);letter-spacing:0}
.tabs{display:flex;gap:4px;height:60px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{
  position:relative;
  display:flex;align-items:center;
  padding:0 14px;
  border:none;background:none;cursor:pointer;
  font-size:.84rem;font-weight:500;color:var(--muted);
  transition:color .15s;
  white-space:nowrap;
}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink)}
.tab.active::after{
  content:'';position:absolute;left:10px;right:10px;bottom:-1px;height:2px;
  background:var(--ink);border-radius:2px;
}
.top-actions{display:flex;justify-content:flex-end}
.btn{
  display:inline-flex;align-items:center;gap:7px;
  padding:8px 13px;
  border:1px solid var(--line-2);border-radius:9px;
  background:var(--surface);color:var(--ink);
  font-size:.8rem;font-weight:500;cursor:pointer;
  box-shadow:0 1px 2px rgba(20,20,20,.05);
  transition:background .15s;
}
.btn:hover{background:var(--soft)}

.subbar{
  display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
  padding:9px 18px;
  background:var(--soft);
  border-bottom:1px solid var(--line);
  font-size:.74rem;color:var(--muted);
}
.subbar span{display:inline-flex;align-items:center;gap:6px}
.subbar b{font-weight:500;color:var(--text)}

/* ── VIEWS & GRID ────────────────────────────────────────────── */
.view{display:none}
.view.active{display:block}

.grid{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(0,1fr)}
.col{min-width:0}
.col + .col{border-left:1px solid var(--line)}
.panel{padding:24px 26px;border-bottom:1px solid var(--line);min-width:0}
.panel:last-child{border-bottom:none}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);border-bottom:1px solid var(--line)}
.split .panel{border-bottom:none}
.split .panel + .panel{border-left:1px solid var(--line)}

.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px}
.panel-title{font-size:1.06rem;font-weight:600;color:var(--ink);letter-spacing:-.015em}
.panel-sub{font-size:.76rem;color:var(--muted);margin-top:4px}
.eyebrow{
  font-size:.64rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);
}
.num{font-size:1.02rem;font-weight:700;color:var(--ink);letter-spacing:-.01em;margin-top:6px}
.num-lg{font-size:1.5rem}
.delta{font-size:.72rem;font-weight:600;color:var(--muted);margin-left:6px}

/* ── KPI TRIO ────────────────────────────────────────────────── */
.kpis{display:grid;grid-template-columns:repeat(3,1fr)}
.kpi{padding:0 20px;min-width:0}
.kpi:first-child{padding-left:0}
.kpi:last-child{padding-right:0}
.kpi + .kpi{border-left:1px solid var(--line)}
.kpi-viz{margin-top:14px;height:34px;position:relative}

.barcode{display:flex;align-items:flex-end;gap:2px;height:28px;margin-top:6px}
.barcode i{flex:1;border-radius:1px;min-height:3px}
.marker{
  position:absolute;top:-2px;width:0;height:0;transform:translateX(-50%);
  border-left:4px solid transparent;border-right:4px solid transparent;border-top:6px solid var(--ink);
}

.gauge-wrap{position:relative;margin-top:21px}
.gauge-wrap .marker{top:-9px}
.gauge{display:flex;gap:2px;height:7px}
.gauge i{height:100%;border-radius:1px}
.gauge-rest{background:var(--line-2)}

.meter{height:7px;background:var(--line);border-radius:2px;margin-top:21px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--ink);border-radius:2px}
.meter-cap{display:flex;justify-content:space-between;font-size:.68rem;color:var(--subtle);margin-top:6px}

/* ── DISTRIBUTION (invoices-style) ───────────────────────────── */
.dist{display:flex;gap:2px}
.dist-col{min-width:0;display:flex;flex-direction:column}
.dist-meta{padding:0 12px 0 10px;border-left:1px solid var(--line);height:96px;display:flex;flex-direction:column}
.dist-col:first-child .dist-meta{border-left:none;padding-left:0}
.dist-meta .eyebrow{white-space:nowrap}
.dist-pct{margin-top:auto;padding-bottom:10px;font-size:.76rem;color:var(--muted)}
.dist-bar{height:6px;border-radius:2px}

/* ── CHIPS & CONTROLS ────────────────────────────────────────── */
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.chips{display:flex;gap:2px;flex-wrap:wrap}
.chip{
  padding:6px 10px;border-radius:7px;border:none;background:none;cursor:pointer;
  font-size:.78rem;font-weight:500;color:var(--muted);
}
.chip:hover{color:var(--ink)}
.chip.active{background:var(--soft);color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)}
.search{
  display:flex;align-items:center;gap:7px;
  padding:6px 10px;border:1px solid var(--line-2);border-radius:8px;
  color:var(--subtle);min-width:200px;
}
.search input{border:none;outline:none;font-size:.8rem;color:var(--ink);background:none;width:100%}
.search:focus-within{border-color:var(--ink)}
.select{
  padding:6px 26px 6px 10px;border:1px solid var(--line-2);border-radius:8px;
  font-size:.78rem;color:var(--text);background:var(--surface);cursor:pointer;outline:none;
  appearance:none;-webkit-appearance:none;max-width:200px;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='2.4'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 9px center;
}
.select:focus{border-color:var(--ink)}
.switch{display:inline-flex;align-items:center;gap:8px;font-size:.78rem;color:var(--muted);cursor:pointer;user-select:none}
.switch input{display:none}
.switch .track{width:28px;height:16px;border-radius:10px;background:var(--line-2);position:relative;transition:background .15s}
.switch .track::after{
  content:'';position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;
  background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.2);transition:transform .15s;
}
.switch input:checked + .track{background:var(--ink)}
.switch input:checked + .track::after{transform:translateX(12px)}
.switch input:checked ~ .lbl{color:var(--ink)}
.spacer{flex:1}

/* ── LINE CHART ──────────────────────────────────────────────── */
.chart-axis-cap{font-size:.7rem;color:var(--subtle);margin-bottom:6px}
.chart-box{position:relative;height:250px}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px}
.legend label{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;color:var(--text);cursor:pointer;user-select:none}
.legend input{display:none}
.legend .box{
  width:15px;height:15px;border-radius:4px;display:grid;place-items:center;
  border:1.5px solid currentColor;
}
.legend .box svg{width:10px;height:10px;stroke:#fff;stroke-width:3;fill:none;opacity:0}
.legend input:checked + .box{background:currentColor}
.legend input:checked + .box svg{opacity:1}
.legend input:not(:checked) ~ .name{color:var(--subtle)}

/* ── STACKED LIST (dept / roles) ─────────────────────────────── */
.dept-row{padding:12px 0;border-top:1px solid var(--line)}
.dept-row:first-of-type{border-top:none;padding-top:0}
.dept-row-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:8px}
.dept-name{font-size:.82rem;font-weight:500;color:var(--ink)}
.dept-pct{font-size:.82rem;font-weight:700;color:var(--ink)}
.dept-pct span{font-weight:400;color:var(--muted);font-size:.72rem;margin-left:4px}
.stack{display:flex;gap:2px;height:8px}
.stack i{height:100%;border-radius:1px}
.stack-legend{display:flex;gap:14px;margin-top:14px;font-size:.72rem;color:var(--muted);flex-wrap:wrap}
.stack-legend span{display:inline-flex;align-items:center;gap:6px}
.sq{width:8px;height:8px;border-radius:2px;display:inline-block}

.seg{display:flex;gap:3px;height:7px;margin-bottom:16px}
.seg i{height:100%;border-radius:2px}
.list-row{display:grid;grid-template-columns:auto 1fr auto auto;gap:10px;align-items:center;padding:6px 0;font-size:.8rem}
.list-row .name{color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.list-row .v{font-weight:600;color:var(--ink);text-align:right;min-width:52px}
.list-row .p{color:var(--muted);text-align:right;min-width:40px}

/* ── TABLE ───────────────────────────────────────────────────── */
.table-scroll{overflow-x:auto;margin:0 -4px}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{
  text-align:left;padding:10px 10px;
  font-size:.74rem;font-weight:600;color:var(--ink);
  border-bottom:1px solid var(--line);
  white-space:nowrap;user-select:none;
}
th[data-col]{cursor:pointer}
th[data-col]:hover{color:var(--muted)}
th .arrow{display:inline-block;margin-left:4px;font-size:.62rem;color:var(--subtle)}
th.sort-asc .arrow::after{content:'▲';color:var(--ink)}
th.sort-desc .arrow::after{content:'▼';color:var(--ink)}
td{padding:9px 10px;border-bottom:1px solid var(--line);color:var(--text);white-space:nowrap;vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--hover)}
.r{text-align:right}
.c{text-align:center}

.who{display:flex;align-items:center;gap:10px}
.avatar{
  width:24px;height:24px;border-radius:6px;display:grid;place-items:center;
  font-size:.62rem;font-weight:700;color:#fff;flex-shrink:0;
}
.who b{font-weight:600;color:var(--ink)}

.badge{
  display:inline-flex;align-items:center;gap:6px;
  padding:3px 9px 3px 7px;border-radius:6px;
  font-size:.72rem;font-weight:500;color:var(--text);background:var(--soft);
  box-shadow:inset 0 0 0 1px var(--line);
}
.dot{width:7px;height:7px;border-radius:2px;display:inline-block;flex-shrink:0}

.prob{display:flex;align-items:center;gap:10px;min-width:130px}
.prob b{font-weight:600;color:var(--ink);min-width:42px}
.prob .track{flex:1;height:5px;background:var(--line);border-radius:2px;overflow:hidden}
.prob .track i{display:block;height:100%;border-radius:2px}

.sat{display:flex;gap:2px}
.sat i{width:9px;height:7px;border-radius:1px;background:var(--line-2)}

.pill{
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 9px;border-radius:6px;
  font-size:.7rem;font-weight:600;background:var(--ink);color:#fff;
}

.table-foot{
  display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding-top:14px;font-size:.76rem;color:var(--muted);
}
.pager{display:flex;align-items:center;gap:8px}
.pager .cur{
  min-width:28px;padding:4px 8px;border:1px solid var(--line-2);border-radius:7px;
  text-align:center;color:var(--ink);font-weight:500;
}
.icon-btn{
  width:28px;height:28px;border-radius:7px;border:none;background:none;cursor:pointer;
  display:grid;place-items:center;color:var(--ink);
}
.icon-btn:hover{background:var(--soft)}
.icon-btn:disabled{color:var(--subtle);cursor:default;background:none}
.link{
  display:inline-flex;align-items:center;gap:6px;border:none;background:none;cursor:pointer;
  font-size:.78rem;font-weight:500;color:var(--ink);
}
.link:hover{text-decoration:underline}
.empty{text-align:center;padding:36px 10px;color:var(--subtle)}

/* ── ACIONÁVEIS ──────────────────────────────────────────────── */
.dept-block{padding:22px 26px;border-bottom:1px solid var(--line)}
.dept-block:last-child{border-bottom:none}
.dept-block-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.dept-block-head .count{font-size:.74rem;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.card{
  border:1px solid var(--line);border-radius:11px;padding:14px 15px;
  transition:border-color .15s,box-shadow .15s;
}
.card:hover{border-color:var(--line-2);box-shadow:0 6px 18px -10px rgba(20,20,20,.18)}
.card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.card-id{font-size:.72rem;color:var(--muted)}
.card-prob{font-size:1.05rem;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:6px}
.card-role{font-size:.85rem;font-weight:600;color:var(--ink)}
.card-meta{font-size:.72rem;color:var(--muted);margin-top:2px}
.card .prob .track{margin:10px 0 0}
.factors{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px}
.factor{font-size:.68rem;padding:3px 7px;border-radius:5px;background:var(--soft);color:var(--muted);font-weight:500}
.more{margin-top:12px}

.page-foot{
  display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
  max-width:1320px;margin:14px auto 0;padding:0 4px;
  font-size:.72rem;color:var(--muted);
}

::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#D4D4D0;border-radius:4px}

@media(max-width:1100px){
  .grid{grid-template-columns:1fr}
  .col + .col{border-left:none;border-top:1px solid var(--line)}
}
@media(max-width:760px){
  body{padding:0}
  .app{border-radius:0}
  .topbar{grid-template-columns:1fr auto;height:auto;padding:12px 16px 0;row-gap:4px}
  .tabs{grid-column:1 / -1;grid-row:2;overflow-x:auto;height:46px;margin:0 -8px}
  .subbar{padding:9px 16px}
  .panel,.dept-block{padding:20px 16px}
  .kpis{grid-template-columns:1fr;gap:18px}
  .kpi{padding:0 !important;border-left:none !important}
  .split{grid-template-columns:1fr}
  .split .panel + .panel{border-left:none;border-top:1px solid var(--line)}
  .search{min-width:0;flex:1 1 100%}
  .page-foot{padding:0 16px 20px}
}
</style>
</head>
<body>

<div class="app">

  <!-- ═══════════════════ TOP BAR ═══════════════════ -->
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19h16"/><path d="M7 15l4-5 3 3 4-6"/></svg>
      </div>
      <div>Attrition Risk<small>HR Business Partner</small></div>
    </div>
    <nav class="tabs">
      <button class="tab active" data-view="painel">Painel Geral</button>
      <button class="tab" data-view="colaboradores">Colaboradores</button>
      <button class="tab" data-view="acoes">Acionáveis</button>
    </nav>
    <div class="top-actions">
      <button class="btn" onclick="exportCsv()" title="Exporta a lista filtrada da aba Colaboradores">
        <svg class="i" viewBox="0 0 24 24"><path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M5 20h14"/></svg>
        Exportar CSV
      </button>
    </div>
  </header>

  <div class="subbar">
    <span>
      <svg class="i" viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>
      Base: <b id="sub-total">—</b> colaboradores ativos
    </span>
    <span>
      <svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>
      Modelo: <b>XGBoost regularizado</b> · threshold <b>t = 0.35</b>
    </span>
  </div>

  <!-- ═══════════════════ PAINEL GERAL ═══════════════════ -->
  <section class="view active" id="view-painel">
    <div class="grid">
      <div class="col">

        <div class="panel">
          <div class="panel-head"><div class="panel-title">Risco de saída</div></div>
          <div class="kpis">
            <div class="kpi">
              <div class="eyebrow">Colaboradores ativos</div>
              <div class="num" id="k-total">—</div>
              <div class="kpi-viz">
                <span class="marker" style="left:35%" title="Threshold t = 0.35"></span>
                <div class="barcode" id="barcode"></div>
              </div>
            </div>
            <div class="kpi">
              <div class="eyebrow">Probabilidade média</div>
              <div class="num" id="k-media">—</div>
              <div class="kpi-viz">
                <div class="gauge-wrap">
                  <span class="marker" id="gauge-marker"></span>
                  <div class="gauge" id="gauge"></div>
                </div>
              </div>
            </div>
            <div class="kpi">
              <div class="eyebrow">Ação recomendada</div>
              <div class="num"><span id="k-acao">—</span><span class="delta" id="k-acao-pct"></span></div>
              <div class="kpi-viz">
                <div class="meter"><i id="acao-meter"></i></div>
                <div class="meter-cap"><span>prob ≥ 35%</span><span>conversa preventiva</span></div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">Risco por tempo de casa</div>
              <div class="panel-sub">Probabilidade média de saída por anos na empresa, por departamento</div>
            </div>
          </div>
          <div class="chart-axis-cap">Prob. média de saída, %</div>
          <div class="chart-box"><canvas id="tenureChart"></canvas></div>
          <div class="legend" id="tenure-legend"></div>
        </div>

        <div class="split">
          <div class="panel">
            <div class="panel-head">
              <div>
                <div class="panel-title">Por departamento</div>
                <div class="panel-sub" id="dept-insight"></div>
              </div>
            </div>
            <div id="dept-list"></div>
            <div class="stack-legend">
              <span><i class="sq" style="background:var(--alto)"></i>Alto</span>
              <span><i class="sq" style="background:var(--medio)"></i>Médio</span>
              <span><i class="sq" style="background:var(--line-2)"></i>Baixo</span>
            </div>
          </div>
          <div class="panel">
            <div class="panel-head">
              <div>
                <div class="panel-title">Cargos em risco</div>
                <div class="panel-sub">Participação nas conversas recomendadas</div>
              </div>
            </div>
            <div class="seg" id="role-seg"></div>
            <div id="role-list"></div>
          </div>
        </div>

      </div>
      <div class="col">

        <div class="panel">
          <div class="panel-head"><div class="panel-title">Distribuição por faixa</div></div>
          <div class="dist" id="dist"></div>
        </div>

        <div class="panel">
          <div class="toolbar" style="margin-bottom:10px">
            <div class="chips" id="top-chips">
              <button class="chip active" data-f="">Todos</button>
              <button class="chip" data-f="Alto">Alto</button>
              <button class="chip" data-f="Medio">Médio</button>
            </div>
            <div class="spacer"></div>
            <span class="eyebrow">Maiores probabilidades</span>
          </div>
          <div class="table-scroll">
            <table>
              <thead><tr><th>Colaborador</th><th>Cargo</th><th>Faixa</th><th class="r">Prob.</th></tr></thead>
              <tbody id="top-body"></tbody>
            </table>
          </div>
          <div class="table-foot">
            <span>Top 12 de <b id="top-count" style="color:var(--ink);font-weight:500">—</b></span>
            <button class="link" onclick="goTo('colaboradores')">
              Ver todos os colaboradores
              <svg class="i" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
          </div>
        </div>

      </div>
    </div>
  </section>

  <!-- ═══════════════════ COLABORADORES ═══════════════════ -->
  <section class="view" id="view-colaboradores">
    <div class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">Colaboradores</div>
          <div class="panel-sub">Clique no cabeçalho para ordenar · <span id="filter-count"></span></div>
        </div>
      </div>
      <div class="toolbar" style="margin-bottom:12px">
        <div class="chips" id="faixa-chips">
          <button class="chip active" data-f="">Todos</button>
          <button class="chip" data-f="Alto">Alto risco</button>
          <button class="chip" data-f="Medio">Risco médio</button>
          <button class="chip" data-f="Baixo">Baixo risco</button>
        </div>
        <select class="select" id="f-dept"><option value="">Todos os departamentos</option></select>
        <select class="select" id="f-role"><option value="">Todos os cargos</option></select>
        <label class="switch">
          <input type="checkbox" id="f-acao"><span class="track"></span><span class="lbl">Apenas com ação</span>
        </label>
        <div class="spacer"></div>
        <label class="search">
          <svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/></svg>
          <input id="search" type="text" placeholder="Buscar ID, cargo ou depto…">
        </label>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th data-col="id">Colaborador<span class="arrow"></span></th>
              <th data-col="dept">Departamento<span class="arrow"></span></th>
              <th data-col="role">Cargo<span class="arrow"></span></th>
              <th data-col="level" class="c">Nível<span class="arrow"></span></th>
              <th data-col="prob">Prob. de saída<span class="arrow"></span></th>
              <th data-col="faixa">Faixa<span class="arrow"></span></th>
              <th>Sat. trabalho</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody id="table-body"></tbody>
        </table>
      </div>
      <div class="table-foot">
        <label style="display:flex;align-items:center;gap:8px">Mostrar
          <select class="select" id="page-size"><option>10</option><option selected>25</option><option>50</option><option>100</option></select>
        </label>
        <div class="pager">
          <button class="icon-btn" id="prev" aria-label="Página anterior"><svg class="i" viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg></button>
          <span class="cur" id="page-cur">1</span><span>/</span><span id="page-total">1</span>
          <button class="icon-btn" id="next" aria-label="Próxima página"><svg class="i" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg></button>
        </div>
      </div>
    </div>
  </section>

  <!-- ═══════════════════ ACIONÁVEIS ═══════════════════ -->
  <section class="view" id="view-acoes">
    <div class="grid">
      <div class="col">
        <div class="panel" style="border-bottom:none">
          <div class="panel-title">Protocolo de retenção ativa</div>
          <div class="panel-sub" style="max-width:460px;line-height:1.5">
            Agende um 1:1 com cada colaborador listado. O threshold t = 0.35 captura ~90% de quem sairia —
            o custo de um falso alarme é apenas uma conversa.
          </div>
        </div>
      </div>
      <div class="col">
        <div class="panel" style="border-bottom:none">
          <div class="dist" id="acoes-dist"></div>
        </div>
      </div>
    </div>
    <div style="padding:0 26px 14px;border-bottom:1px solid var(--line)" class="toolbar">
      <div class="chips" id="acoes-chips"></div>
    </div>
    <div id="action-sections"></div>
  </section>

</div>

<footer class="page-foot">
  <span>Fonte: attrition_risk_ranking.csv · IBM HR Analytics</span>
  <span>Faixas: Alto ≥ 70% · Médio ≥ 35% · Baixo &lt; 35%</span>
</footer>

<script>
const RAW = %DATA_JSON%;
const EMPLOYEES = RAW.employees;
const K = RAW.kpis;

var css = getComputedStyle(document.documentElement);
function v(name){ return css.getPropertyValue(name).trim(); }
var TIER = {
  Alto:  {label:"Alto",  color:v("--alto")},
  Medio: {label:"Médio", color:v("--medio")},
  Baixo: {label:"Baixo", color:v("--baixo")}
};
var DEPT_COLORS = [v("--d1"), v("--d2"), v("--d3")];
var DEPT_COLOR = {};
RAW.tenure.series.forEach(function(s,i){ DEPT_COLOR[s.dept] = DEPT_COLORS[i]; });

function fmt(n){ return n.toLocaleString("pt-BR"); }
function pct(n){ return n.toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:1})+"%"; }
function tierOf(p){ return p>=70?"Alto":p>=35?"Medio":"Baixo"; }
function initials(s){ return s.split(/[\s&]+/).filter(Boolean).map(function(w){return w[0];}).join("").slice(0,2).toUpperCase(); }
function avatar(e){ return "<span class='avatar' style='background:"+DEPT_COLOR[e.dept]+"' title='"+e.dept+"'>"+initials(e.dept)+"</span>"; }
function badge(f){ return "<span class='badge'><i class='dot' style='background:"+TIER[f].color+"'></i>"+TIER[f].label+"</span>"; }
function probCell(p){
  return "<div class='prob'><b>"+pct(p)+"</b><span class='track'><i style='width:"+Math.min(100,p)+"%;background:"+TIER[tierOf(p)].color+"'></i></span></div>";
}

// ── tabs ─────────────────────────────────────────────────────────────────────
function goTo(view){
  document.querySelectorAll(".tab").forEach(function(t){ t.classList.toggle("active", t.dataset.view===view); });
  document.querySelectorAll(".view").forEach(function(s){ s.classList.toggle("active", s.id==="view-"+view); });
  history.replaceState(null,"","#"+view);
  window.scrollTo({top:0});
}
document.querySelectorAll(".tab").forEach(function(t){
  t.addEventListener("click", function(){ goTo(t.dataset.view); });
});

// ── KPIs ─────────────────────────────────────────────────────────────────────
document.getElementById("sub-total").textContent = fmt(K.total);
document.getElementById("k-total").textContent   = fmt(K.total);
document.getElementById("k-media").textContent   = pct(K.prob_media);
document.getElementById("k-acao").textContent    = fmt(K.acao);
document.getElementById("k-acao-pct").textContent = pct(K.acao/K.total*100)+" da base";
document.getElementById("acao-meter").style.width = (K.acao/K.total*100)+"%";

(function(){
  var max = Math.max.apply(null, RAW.hist.map(function(h){return h.n;}));
  document.getElementById("barcode").innerHTML = RAW.hist.map(function(h){
    var hgt = Math.max(10, Math.sqrt(h.n/max)*100);
    return "<i style='height:"+hgt+"%;background:"+TIER[tierOf(h.lo)].color+"' title='"
      +h.lo+"–"+h.hi+"%: "+fmt(h.n)+" colaboradores'></i>";
  }).join("");

  var segs = [[35,"Baixo"],[35,"Medio"],[30,"Alto"]];
  document.getElementById("gauge").innerHTML = segs.map(function(s){
    return "<i style='flex:"+s[0]+";background:"+TIER[s[1]].color+"' title='"+TIER[s[1]].label+"'></i>";
  }).join("");
  document.getElementById("gauge-marker").style.left = K.prob_media+"%";
})();

// ── distribution (invoices-style) ────────────────────────────────────────────
function renderDist(el, parts){
  var total = parts.reduce(function(a,p){return a+p.n;},0);
  el.innerHTML = parts.map(function(p){
    var share = total ? p.n/total*100 : 0;
    return "<div class='dist-col' style='flex:"+Math.max(share,22)+"'>"
      +"<div class='dist-meta'><div class='eyebrow'>"+p.label+"</div>"
      +"<div class='num num-lg'>"+fmt(p.n)+"</div>"
      +"<div class='dist-pct'>"+pct(share)+"</div></div>"
      +"<div class='dist-bar' style='background:"+p.color+"'></div></div>";
  }).join("");
}
renderDist(document.getElementById("dist"), [
  {label:"Alto risco",  n:K.alto,  color:TIER.Alto.color},
  {label:"Risco médio", n:K.medio, color:TIER.Medio.color},
  {label:"Baixo risco", n:K.baixo, color:TIER.Baixo.color}
]);

// ── tenure line chart ────────────────────────────────────────────────────────
(function(){
  var T = RAW.tenure;
  var ink = v("--ink"), muted = v("--muted"), line = v("--line");
  var font = {family:"Inter", size:11};

  var crosshair = {
    id:"crosshair",
    afterDraw:function(chart){
      var act = chart.tooltip && chart.tooltip.getActiveElements();
      if(!act || !act.length) return;
      var x = act[0].element.x, a = chart.chartArea, ctx = chart.ctx;
      ctx.save(); ctx.setLineDash([3,3]); ctx.strokeStyle = muted; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x,a.top); ctx.lineTo(x,a.bottom); ctx.stroke(); ctx.restore();
    }
  };
  var threshold = {
    id:"threshold",
    beforeDatasetsDraw:function(chart){
      var y = chart.scales.y.getPixelForValue(35), a = chart.chartArea, ctx = chart.ctx;
      if(y < a.top || y > a.bottom) return;
      ctx.save(); ctx.setLineDash([4,4]); ctx.strokeStyle = TIER.Medio.color; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(a.left,y); ctx.lineTo(a.right,y); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = muted; ctx.font = "500 10px Inter";
      ctx.textAlign = "right"; ctx.fillText("t = 35%", a.right-2, y-5); ctx.restore();
    }
  };

  var datasets = T.series.map(function(s,i){
    var c = DEPT_COLOR[s.dept];
    return {
      label:s.dept, data:s.values, n:s.n,
      borderColor:c, backgroundColor:c, borderWidth:2,
      pointRadius:0, pointHoverRadius:4, pointHoverBorderColor:"#fff", pointHoverBorderWidth:2,
      tension:0, spanGaps:true,
      fill: i===0 ? {target:"origin"} : false
    };
  });

  var chart = new Chart(document.getElementById("tenureChart"),{
    type:"line",
    data:{labels:T.labels, datasets:datasets},
    plugins:[crosshair, threshold],
    options:{
      responsive:true, maintainAspectRatio:false,
      interaction:{mode:"index", intersect:false},
      plugins:{
        legend:{display:false},
        filler:{propagate:false},
        tooltip:{
          backgroundColor:"#fff", titleColor:muted, bodyColor:ink,
          borderColor:v("--line-2"), borderWidth:1, padding:10, cornerRadius:8,
          titleFont:{family:"Inter", size:10, weight:"500"}, bodyFont:{family:"Inter", size:12},
          boxWidth:8, boxHeight:8, boxPadding:5, usePointStyle:true,
          callbacks:{
            title:function(items){ var l = items[0].label; return (l==="1"?"1 ano":l+" anos")+" de casa"; },
            label:function(c){
              if(c.raw===null) return null;
              return " "+c.dataset.label+":  "+pct(c.raw)+"  (n="+c.dataset.n[c.dataIndex]+")";
            },
            labelPointStyle:function(){ return {pointStyle:"rectRounded", rotation:0}; }
          }
        }
      },
      scales:{
        x:{grid:{display:false}, border:{display:false}, ticks:{font:font, color:muted},
           title:{display:true, text:"Anos na empresa", font:font, color:muted}},
        y:{grid:{color:line}, border:{display:false, dash:[3,3]},
           suggestedMin:20, suggestedMax:60,
           ticks:{font:font, color:muted, stepSize:10, callback:function(x){return x+"%";}}}
      }
    }
  });

  // gradient fill under the first series
  var ctx = chart.ctx, area = chart.chartArea;
  var g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
  g.addColorStop(0, DEPT_COLORS[0]+"22"); g.addColorStop(1, DEPT_COLORS[0]+"00");
  chart.data.datasets[0].backgroundColor = g;
  chart.update("none");

  var tick = "<svg viewBox='0 0 24 24'><path d='M5 12l5 5 9-10'/></svg>";
  document.getElementById("tenure-legend").innerHTML = T.series.map(function(s,i){
    return "<label style='color:"+DEPT_COLOR[s.dept]+"'><input type='checkbox' checked data-i='"+i+"'>"
      +"<span class='box'>"+tick+"</span><span class='name' style='color:var(--text)'>"+s.dept+"</span></label>";
  }).join("");
  document.querySelectorAll("#tenure-legend input").forEach(function(inp){
    inp.addEventListener("change", function(){
      chart.setDatasetVisibility(+inp.dataset.i, inp.checked);
      inp.nextElementSibling.nextElementSibling.style.color = inp.checked ? "var(--text)" : "var(--subtle)";
      chart.update();
    });
  });
})();

// ── departments ──────────────────────────────────────────────────────────────
(function(){
  var D = RAW.dept_data;
  var top = D[0];
  document.getElementById("dept-insight").textContent =
    top.dept+" lidera com "+pct(top.pct_risco)+" em risco";
  document.getElementById("dept-list").innerHTML = D.map(function(d){
    return "<div class='dept-row'><div class='dept-row-head'>"
      +"<span class='dept-name'>"+d.dept+"</span>"
      +"<span class='dept-pct'>"+pct(d.pct_risco)+"<span>"+fmt(d.alto+d.medio)+" de "+fmt(d.total)+"</span></span></div>"
      +"<div class='stack'>"
        +"<i style='flex:"+d.alto+";background:"+TIER.Alto.color+"' title='Alto: "+d.alto+"'></i>"
        +"<i style='flex:"+d.medio+";background:"+TIER.Medio.color+"' title='Médio: "+d.medio+"'></i>"
        +"<i style='flex:"+d.baixo+";background:var(--line-2)' title='Baixo: "+d.baixo+"'></i>"
      +"</div></div>";
  }).join("");
})();

// ── roles ────────────────────────────────────────────────────────────────────
(function(){
  var R = RAW.role_data;
  var shades = ["#151517","#3A3A3F","#5E5E64","#86868C","#ADADB2","#CFCFD3","#E4E4E7"];
  var total = R.reduce(function(a,r){return a+r.n_risco;},0);
  document.getElementById("role-seg").innerHTML = R.map(function(r,i){
    return "<i style='flex:"+r.n_risco+";background:"+shades[i]+"' title='"+r.role+": "+r.n_risco+"'></i>";
  }).join("");
  document.getElementById("role-list").innerHTML = R.map(function(r,i){
    return "<div class='list-row' title='Prob. média: "+pct(r.avg)+"'>"
      +"<i class='sq' style='background:"+shades[i]+"'></i>"
      +"<span class='name'>"+r.role+"</span>"
      +"<span class='v'>"+fmt(r.n_risco)+"</span>"
      +"<span class='p'>"+Math.round(r.n_risco/total*100)+"%</span></div>";
  }).join("");
})();

// ── top risk mini-table ──────────────────────────────────────────────────────
function renderTop(f){
  var rows = EMPLOYEES.filter(function(e){ return f ? e.faixa===f : e.faixa!=="Baixo"; });
  document.getElementById("top-count").textContent = fmt(rows.length);
  document.getElementById("top-body").innerHTML = rows.slice(0,12).map(function(e){
    return "<tr><td><div class='who'>"+avatar(e)+"<b>#"+e.id+"</b></div></td>"
      +"<td>"+e.role+"</td><td>"+badge(e.faixa)+"</td>"
      +"<td class='r'><b style='color:var(--ink)'>"+pct(e.prob)+"</b></td></tr>";
  }).join("");
}
document.querySelectorAll("#top-chips .chip").forEach(function(c){
  c.addEventListener("click", function(){
    document.querySelectorAll("#top-chips .chip").forEach(function(x){ x.classList.toggle("active", x===c); });
    renderTop(c.dataset.f);
  });
});
renderTop("");

// ── TABLE ─────────────────────────────────────────────────────────────────────
var filtered    = EMPLOYEES.slice();
var sortCol     = "prob";
var sortDir     = -1;
var currentPage = 1;
var faixaFilter = "";

var depts = [...new Set(EMPLOYEES.map(function(e){return e.dept}))].sort();
var roles = [...new Set(EMPLOYEES.map(function(e){return e.role}))].sort();
depts.forEach(function(d){
  var o=document.createElement("option"); o.value=d; o.textContent=d; document.getElementById("f-dept").appendChild(o);
});
roles.forEach(function(r){
  var o=document.createElement("option"); o.value=r; o.textContent=r; document.getElementById("f-role").appendChild(o);
});

document.getElementById("search").addEventListener("input", applyFilters);
["f-dept","f-role","f-acao"].forEach(function(id){
  document.getElementById(id).addEventListener("change", applyFilters);
});
document.getElementById("page-size").addEventListener("change", function(){ currentPage=1; renderTable(); });
document.getElementById("prev").addEventListener("click", function(){ currentPage--; renderTable(); });
document.getElementById("next").addEventListener("click", function(){ currentPage++; renderTable(); });
document.querySelectorAll("#faixa-chips .chip").forEach(function(c){
  c.addEventListener("click", function(){
    document.querySelectorAll("#faixa-chips .chip").forEach(function(x){ x.classList.toggle("active", x===c); });
    faixaFilter = c.dataset.f;
    applyFilters();
  });
});
document.querySelectorAll("th[data-col]").forEach(function(th){
  th.addEventListener("click", function(){ sortBy(th.dataset.col); });
});

function applyFilters(){
  var q   = document.getElementById("search").value.toLowerCase();
  var dep = document.getElementById("f-dept").value;
  var rol = document.getElementById("f-role").value;
  var acao = document.getElementById("f-acao").checked;

  filtered = EMPLOYEES.filter(function(e){
    if(q && !(
      String(e.id).includes(q) ||
      e.role.toLowerCase().includes(q) ||
      e.dept.toLowerCase().includes(q)
    )) return false;
    if(dep && e.dept !== dep) return false;
    if(rol && e.role !== rol) return false;
    if(faixaFilter && e.faixa !== faixaFilter) return false;
    if(acao && !e.acao) return false;
    return true;
  });

  applySort();
  currentPage = 1;
  renderTable();
}

function sortBy(col){
  if(sortCol === col) sortDir *= -1;
  else { sortCol = col; sortDir = col === "prob" ? -1 : 1; }
  document.querySelectorAll("th[data-col]").forEach(function(th){
    th.classList.remove("sort-asc","sort-desc");
    if(th.dataset.col === sortCol) th.classList.add(sortDir===1?"sort-asc":"sort-desc");
  });
  applySort();
  renderTable();
}

function applySort(){
  filtered.sort(function(a,b){
    var av=a[sortCol], bv=b[sortCol];
    if(typeof av==="string") return av.localeCompare(bv)*sortDir;
    return (av-bv)*sortDir;
  });
}

function satBars(val){
  var c = val<=1?TIER.Alto.color:val<=2?TIER.Medio.color:TIER.Baixo.color;
  var html = "<div class='sat' title='"+val+" de 4'>";
  for(var i=1;i<=4;i++) html += "<i"+(i<=val?" style='background:"+c+"'":"")+"></i>";
  return html+"</div>";
}

function renderTable(){
  var size = +document.getElementById("page-size").value;
  var total = filtered.length;
  var totalPages = Math.max(1, Math.ceil(total/size));
  currentPage = Math.min(Math.max(1,currentPage), totalPages);

  var start = (currentPage-1)*size;
  var page  = filtered.slice(start, start+size);

  var tbody = document.getElementById("table-body");
  if(!page.length){
    tbody.innerHTML = "<tr><td colspan='8' class='empty'>Nenhum colaborador encontrado</td></tr>";
  } else {
    tbody.innerHTML = page.map(function(e){
      return "<tr>"
        +"<td><div class='who'>"+avatar(e)+"<b>#"+e.id+"</b></div></td>"
        +"<td>"+e.dept+"</td>"
        +"<td>"+e.role+"</td>"
        +"<td class='c'>"+e.level+"</td>"
        +"<td>"+probCell(e.prob)+"</td>"
        +"<td>"+badge(e.faixa)+"</td>"
        +"<td>"+satBars(e.job_sat)+"</td>"
        +"<td>"+(e.acao?"<span class='pill'>Conversa</span>":"")+"</td>"
        +"</tr>";
    }).join("");
  }

  document.getElementById("filter-count").textContent =
    fmt(total)+" colaborador"+(total!==1?"es":"");
  document.getElementById("page-cur").textContent = currentPage;
  document.getElementById("page-total").textContent = totalPages;
  document.getElementById("prev").disabled = currentPage===1;
  document.getElementById("next").disabled = currentPage===totalPages;
}

document.querySelector("th[data-col='prob']").classList.add("sort-desc");
applyFilters();

// ── CSV export (current table filter) ────────────────────────────────────────
function exportCsv(){
  var cols = ["id","dept","role","level","prob","faixa","job_sat","env_sat","wlb","acao"];
  var lines = [cols.join(";")].concat(filtered.map(function(e){
    return cols.map(function(c){
      var x = e[c];
      if(c==="acao") x = x ? "Conversa recomendada" : "";
      if(c==="prob") x = String(x).replace(".",",");
      return '"'+String(x).replace(/"/g,'""')+'"';
    }).join(";");
  }));
  var blob = new Blob(["﻿"+lines.join("\n")], {type:"text/csv;charset=utf-8"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "colaboradores_risco.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── ACIONÁVEIS ───────────────────────────────────────────────────────────────
(function(){
  var actionable = EMPLOYEES.filter(function(e){return e.acao;});
  var nAlto = actionable.filter(function(e){return e.faixa==="Alto";}).length;
  renderDist(document.getElementById("acoes-dist"), [
    {label:"Alto risco",  n:nAlto,                   color:TIER.Alto.color},
    {label:"Risco médio", n:actionable.length-nAlto, color:TIER.Medio.color}
  ]);

  var byDept = {};
  actionable.forEach(function(e){ (byDept[e.dept] = byDept[e.dept] || []).push(e); });
  var names = Object.keys(byDept).sort();
  var container = document.getElementById("action-sections");
  var BATCH = 24;

  function card(e){
    var tags = e.factors.map(function(f){ return "<span class='factor'>"+f+"</span>"; }).join("");
    return "<div class='card'>"
      +"<div class='card-top'><span class='card-id'>#"+e.id+" · "+e.age+" anos</span>"
      +"<span class='card-prob'><i class='dot' style='background:"+TIER[e.faixa].color+"' title='"+TIER[e.faixa].label+"'></i>"+e.prob.toFixed(0)+"%</span></div>"
      +"<div class='card-role'>"+e.role+"</div>"
      +"<div class='card-meta'>Nível "+e.level+" · "+e.years+" ano"+(e.years!==1?"s":"")+" de casa</div>"
      +"<div class='prob'><span class='track'><i style='width:"+e.prob+"%;background:"+TIER[e.faixa].color+"'></i></span></div>"
      +(tags ? "<div class='factors'>"+tags+"</div>" : "")
      +"</div>";
  }

  names.forEach(function(dept){
    var emps = byDept[dept].sort(function(a,b){return b.prob-a.prob;});
    var shown = 0;
    var sec = document.createElement("div");
    sec.className = "dept-block";
    sec.dataset.dept = dept;
    sec.innerHTML = "<div class='dept-block-head'>"
      +"<span class='avatar' style='background:"+DEPT_COLOR[dept]+"'>"+initials(dept)+"</span>"
      +"<span class='panel-title' style='font-size:.95rem'>"+dept+"</span>"
      +"<span class='count'>"+fmt(emps.length)+" colaborador"+(emps.length!==1?"es":"")+"</span></div>"
      +"<div class='cards'></div>"
      +"<div class='more'><button class='btn'></button></div>";
    container.appendChild(sec);
    var grid = sec.querySelector(".cards"), more = sec.querySelector(".more button");
    function showMore(){
      grid.insertAdjacentHTML("beforeend", emps.slice(shown, shown+BATCH).map(card).join(""));
      shown = Math.min(emps.length, shown+BATCH);
      more.textContent = "Mostrar mais ("+fmt(emps.length-shown)+" restantes)";
      more.parentNode.style.display = shown < emps.length ? "" : "none";
    }
    more.addEventListener("click", showMore);
    showMore();
  });

  var chips = document.getElementById("acoes-chips");
  chips.innerHTML = "<button class='chip active' data-d=''>Todos</button>"
    + names.map(function(d){ return "<button class='chip' data-d='"+d+"'>"+d+"</button>"; }).join("");
  chips.querySelectorAll(".chip").forEach(function(c){
    c.addEventListener("click", function(){
      chips.querySelectorAll(".chip").forEach(function(x){ x.classList.toggle("active", x===c); });
      container.querySelectorAll(".dept-block").forEach(function(b){
        b.style.display = !c.dataset.d || b.dataset.dept===c.dataset.d ? "" : "none";
      });
    });
  });
})();

// ── deep link ────────────────────────────────────────────────────────────────
var start = location.hash.slice(1);
if(["colaboradores","acoes"].indexOf(start) >= 0) goTo(start);
</script>
</body>
</html>'''

html_out = HTML.replace('%DATA_JSON%', data_json)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_out)

print("Dashboard gerado em:", OUT)
print("Tamanho:", round(os.path.getsize(OUT)/1024, 1), "KB")
print("Colaboradores no JSON:", len(employees))
print("Com ação recomendada:", sum(1 for e in employees if e['acao']))
