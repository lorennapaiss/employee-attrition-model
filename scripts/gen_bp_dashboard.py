"""Generates attrition-dashboard/bp_attrition_dashboard.html from risk ranking CSV."""
import pandas as pd
import json
import os

BASE = r'C:\Users\loren\Documents\Projetos - Portfólio\employee-attrition'
CSV  = os.path.join(BASE, 'data', 'raw', 'attrition_risk_ranking.csv')
OUT  = os.path.join(BASE, 'attrition-dashboard', 'bp_attrition_dashboard.html')

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

# ── KPIs ─────────────────────────────────────────────────────────────────────
kpis = {
    'total':     int(len(df)),
    'alto':      int((df['Faixa_Risco'] == 'Alto').sum()),
    'medio':     int((df['Faixa_Risco'] == 'Medio').sum()),
    'acao':      int((df['Acao_RH'] == 'Conversa recomendada').sum()),
    'pct_risco': round((df['Faixa_Risco'] != 'Baixo').sum() / len(df) * 100, 1),
}

# ── donut ────────────────────────────────────────────────────────────────────
vc = df['Faixa_Risco'].value_counts()
donut = {
    'labels': ['Alto Risco', 'Risco Médio', 'Baixo Risco'],
    'values': [int(vc.get('Alto', 0)), int(vc.get('Medio', 0)), int(vc.get('Baixo', 0))],
}

# ── dept bar ─────────────────────────────────────────────────────────────────
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

# ── role horizontal bar (top 10 avg prob) ────────────────────────────────────
role_avg = (df.groupby('JobRole')['Probabilidade_Saida_Pct']
              .mean()
              .sort_values(ascending=False)
              .head(10))
role_data = [{'role': r, 'avg': round(float(v), 1)} for r, v in role_avg.items()]

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
    'donut':     donut,
    'dept_data': dept_rows,
    'role_data': role_data,
    'employees': employees,
}
data_json = json.dumps(payload, ensure_ascii=False)

# ── HTML template ─────────────────────────────────────────────────────────────
HTML = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Painel de Risco · HR Business Partner</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,700;1,9..144,400&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}

:root{
  --navy:#0F172A; --navy2:#1E293B; --navy3:#334155;
  --bg:#F1F5F9; --surface:#FFFFFF; --border:#E2E8F0;
  --red:#DC2626; --red-l:#FEF2F2; --red-m:#FCA5A5;
  --amber:#D97706; --amber-l:#FFFBEB; --amber-m:#FCD34D;
  --green:#16A34A; --green-l:#F0FDF4; --green-m:#86EFAC;
  --purple:#7C3AED; --purple-l:#F5F3FF;
  --blue:#2563EB; --blue-l:#EFF6FF;
  --text:#0F172A; --muted:#64748B; --subtle:#94A3B8;
  --font-d:'Fraunces',Georgia,serif;
  --font-b:'DM Sans',system-ui,sans-serif;
  --sidebar-w:240px;
  --radius:10px;
  --shadow:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06);
  --shadow-md:0 4px 6px rgba(0,0,0,.07),0 2px 4px rgba(0,0,0,.06);
}

html{scroll-behavior:smooth}
body{
  background:var(--bg);
  color:var(--text);
  font-family:var(--font-b);
  display:flex;
  min-height:100vh;
}

/* ── SIDEBAR ─────────────────────────────────────────────────── */
.sidebar{
  width:var(--sidebar-w);
  min-width:var(--sidebar-w);
  background:var(--navy);
  display:flex;
  flex-direction:column;
  position:fixed;
  top:0;left:0;bottom:0;
  overflow-y:auto;
  z-index:100;
}
.sidebar-header{
  padding:28px 20px 20px;
  border-bottom:1px solid rgba(255,255,255,.07);
}
.sidebar-logo{
  font-family:var(--font-d);
  font-size:1.05rem;
  font-weight:600;
  color:#fff;
  line-height:1.2;
  letter-spacing:-.01em;
}
.sidebar-logo span{
  display:block;
  font-size:.68rem;
  font-family:var(--font-b);
  font-weight:400;
  color:rgba(255,255,255,.45);
  letter-spacing:.08em;
  text-transform:uppercase;
  margin-top:3px;
}
.sidebar-nav{
  padding:16px 10px;
  flex:1;
}
.nav-label{
  font-size:.6rem;
  font-weight:600;
  letter-spacing:.12em;
  text-transform:uppercase;
  color:rgba(255,255,255,.3);
  padding:8px 10px 4px;
}
.nav-item{
  display:flex;
  align-items:center;
  gap:10px;
  padding:9px 12px;
  border-radius:7px;
  cursor:pointer;
  color:rgba(255,255,255,.55);
  font-size:.825rem;
  font-weight:400;
  text-decoration:none;
  transition:all .15s;
  margin-bottom:2px;
}
.nav-item:hover{background:rgba(255,255,255,.07);color:rgba(255,255,255,.9)}
.nav-item.active{background:rgba(255,255,255,.12);color:#fff;font-weight:500}
.nav-icon{font-size:1rem;opacity:.8}

.sidebar-stats{
  padding:16px 14px 20px;
  border-top:1px solid rgba(255,255,255,.07);
}
.stat-mini{
  padding:10px 12px;
  border-radius:7px;
  background:rgba(255,255,255,.05);
  margin-bottom:8px;
}
.stat-mini-label{font-size:.65rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.08em}
.stat-mini-val{font-size:1.3rem;font-weight:600;color:#fff;font-family:var(--font-d);line-height:1.2;margin-top:1px}
.stat-mini-sub{font-size:.68rem;color:rgba(255,255,255,.4);margin-top:1px}

.badge-red{background:rgba(220,38,38,.25);color:#FCA5A5;font-size:.65rem;font-weight:600;padding:2px 7px;border-radius:20px}
.badge-amber{background:rgba(217,119,6,.25);color:#FCD34D;font-size:.65rem;font-weight:600;padding:2px 7px;border-radius:20px}

/* ── MAIN ────────────────────────────────────────────────────── */
.main{
  margin-left:var(--sidebar-w);
  flex:1;
  padding:32px 28px 60px;
  max-width:1200px;
}

.section{margin-bottom:52px}
.section-title{
  font-family:var(--font-d);
  font-size:1.45rem;
  font-weight:600;
  color:var(--text);
  letter-spacing:-.02em;
  margin-bottom:6px;
}
.section-sub{font-size:.82rem;color:var(--muted);margin-bottom:22px}

/* ── KPI CARDS ───────────────────────────────────────────────── */
.kpi-grid{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:14px;
  margin-bottom:24px;
}
.kpi-card{
  background:var(--surface);
  border-radius:var(--radius);
  padding:18px 20px;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  position:relative;
  overflow:hidden;
}
.kpi-card::before{
  content:'';
  position:absolute;top:0;left:0;right:0;
  height:3px;
  border-radius:var(--radius) var(--radius) 0 0;
}
.kpi-card.kpi-total::before{background:var(--blue)}
.kpi-card.kpi-alto::before{background:var(--red)}
.kpi-card.kpi-medio::before{background:var(--amber)}
.kpi-card.kpi-acao::before{background:var(--purple)}

.kpi-label{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.kpi-value{
  font-family:var(--font-d);
  font-size:2rem;
  font-weight:700;
  color:var(--text);
  line-height:1.1;
  margin:4px 0 2px;
}
.kpi-card.kpi-alto .kpi-value{color:var(--red)}
.kpi-card.kpi-medio .kpi-value{color:var(--amber)}
.kpi-card.kpi-acao .kpi-value{color:var(--purple)}
.kpi-desc{font-size:.73rem;color:var(--muted)}

/* ── CHARTS ROW ──────────────────────────────────────────────── */
.charts-row{
  display:grid;
  grid-template-columns:280px 1fr;
  gap:16px;
  margin-bottom:16px;
}
.chart-card{
  background:var(--surface);
  border-radius:var(--radius);
  padding:20px;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
}
.chart-title{
  font-size:.8rem;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:.07em;
  color:var(--muted);
  margin-bottom:16px;
}
.donut-wrap{
  position:relative;
  width:160px;
  height:160px;
  margin:0 auto 16px;
}
.donut-legend{display:flex;flex-direction:column;gap:7px;margin-top:4px}
.legend-item{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--text)}
.legend-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.legend-val{margin-left:auto;font-weight:600;color:var(--muted);font-size:.75rem}

/* ── ROLE CHART ──────────────────────────────────────────────── */
.role-card{
  background:var(--surface);
  border-radius:var(--radius);
  padding:20px;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  margin-bottom:16px;
}

/* ── FILTERS BAR ─────────────────────────────────────────────── */
.filters-bar{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:10px;
  background:var(--surface);
  border-radius:var(--radius);
  padding:14px 18px;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  margin-bottom:14px;
}
.search-wrap{
  position:relative;
  flex:1;
  min-width:180px;
}
.search-icon{
  position:absolute;left:10px;top:50%;transform:translateY(-50%);
  color:var(--muted);font-size:.85rem;pointer-events:none;
}
.search-input{
  width:100%;
  padding:7px 10px 7px 30px;
  border:1px solid var(--border);
  border-radius:7px;
  font-family:var(--font-b);
  font-size:.82rem;
  color:var(--text);
  background:var(--bg);
  outline:none;
  transition:border .15s;
}
.search-input:focus{border-color:var(--blue)}
.filter-select{
  padding:7px 28px 7px 10px;
  border:1px solid var(--border);
  border-radius:7px;
  font-family:var(--font-b);
  font-size:.82rem;
  color:var(--text);
  background:var(--bg);
  outline:none;
  cursor:pointer;
  appearance:none;
  -webkit-appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat:no-repeat;
  background-position:right 8px center;
}
.toggle-btn{
  display:flex;align-items:center;gap:7px;
  padding:7px 12px;
  border:1px solid var(--border);
  border-radius:7px;
  font-family:var(--font-b);
  font-size:.78rem;
  font-weight:500;
  color:var(--muted);
  background:var(--bg);
  cursor:pointer;
  transition:all .15s;
  white-space:nowrap;
}
.toggle-btn.active{background:var(--purple-l);border-color:var(--purple);color:var(--purple)}
.filter-count{
  font-size:.75rem;
  color:var(--muted);
  white-space:nowrap;
  margin-left:auto;
}

/* ── TABLE ───────────────────────────────────────────────────── */
.table-wrap{
  background:var(--surface);
  border-radius:var(--radius);
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  overflow:hidden;
}
table{width:100%;border-collapse:collapse;font-size:.8rem}
thead{background:#F8FAFC}
th{
  padding:11px 14px;
  text-align:left;
  font-size:.67rem;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:.07em;
  color:var(--muted);
  border-bottom:1px solid var(--border);
  cursor:pointer;
  white-space:nowrap;
  user-select:none;
}
th:hover{color:var(--text)}
th .sort-arrow{opacity:.4;margin-left:3px;font-size:.7rem}
th.sort-asc .sort-arrow::after{content:'↑';opacity:1}
th.sort-desc .sort-arrow::after{content:'↓';opacity:1}
td{
  padding:10px 14px;
  border-bottom:1px solid #F1F5F9;
  vertical-align:middle;
  color:var(--text);
}
tr:last-child td{border-bottom:none}
tr:hover td{background:#FAFBFD}

.faixa-badge{
  display:inline-flex;align-items:center;
  padding:3px 10px;
  border-radius:20px;
  font-size:.68rem;
  font-weight:600;
  letter-spacing:.04em;
}
.faixa-Alto{background:var(--red-l);color:var(--red)}
.faixa-Medio{background:var(--amber-l);color:var(--amber)}
.faixa-Baixo{background:var(--green-l);color:var(--green)}

.prob-bar-wrap{display:flex;align-items:center;gap:8px;min-width:90px}
.prob-bar-bg{flex:1;height:5px;background:#E2E8F0;border-radius:3px;overflow:hidden}
.prob-bar-fill{height:100%;border-radius:3px;transition:width .3s}

.sat-dots{display:flex;gap:3px}
.dot{width:8px;height:8px;border-radius:50%}
.dot.filled-1{background:var(--red)}
.dot.filled-2{background:var(--amber)}
.dot.filled-3{background:var(--amber)}
.dot.filled-4{background:var(--green)}
.dot.empty{background:#E2E8F0}

.acao-pill{
  font-size:.65rem;font-weight:600;
  padding:3px 8px;border-radius:20px;
  background:var(--purple-l);color:var(--purple);
  white-space:nowrap;
}

/* pagination */
.pagination{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 18px;
  background:var(--surface);
  border:1px solid var(--border);
  border-top:none;
  border-radius:0 0 var(--radius) var(--radius);
  font-size:.78rem;color:var(--muted);
}
.page-btns{display:flex;gap:4px}
.page-btn{
  padding:5px 10px;border-radius:6px;border:1px solid var(--border);
  background:var(--bg);color:var(--muted);cursor:pointer;font-size:.78rem;font-family:var(--font-b);
  transition:all .15s;
}
.page-btn:hover{background:var(--blue-l);border-color:var(--blue);color:var(--blue)}
.page-btn.active{background:var(--blue);border-color:var(--blue);color:#fff}
.page-btn:disabled{opacity:.4;cursor:default}

/* ── ACIONÁVEIS ──────────────────────────────────────────────── */
.action-banner{
  background:linear-gradient(135deg,var(--navy) 0%,var(--navy2) 100%);
  border-radius:var(--radius);
  padding:20px 24px;
  display:flex;align-items:center;gap:16px;
  margin-bottom:20px;
  box-shadow:var(--shadow-md);
}
.action-banner-icon{font-size:1.8rem}
.action-banner-text h3{
  font-family:var(--font-d);
  font-size:1.1rem;
  color:#fff;
  font-weight:600;
  margin-bottom:3px;
}
.action-banner-text p{font-size:.8rem;color:rgba(255,255,255,.55)}
.action-banner-stat{
  margin-left:auto;
  text-align:right;
}
.action-banner-stat .big{font-family:var(--font-d);font-size:2rem;font-weight:700;color:#fff}
.action-banner-stat .lbl{font-size:.68rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.08em}

.dept-section{margin-bottom:28px}
.dept-section-title{
  font-size:.75rem;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:.1em;
  color:var(--muted);
  padding:6px 0;
  margin-bottom:12px;
  border-bottom:2px solid var(--border);
  display:flex;align-items:center;gap:8px;
}
.dept-section-title .count-badge{
  background:var(--red-l);color:var(--red);
  font-size:.65rem;padding:2px 8px;border-radius:20px;
}

.action-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.action-card{
  background:var(--surface);
  border-radius:var(--radius);
  padding:16px;
  box-shadow:var(--shadow);
  border:1px solid var(--border);
  border-left:4px solid var(--red);
}
.action-card.faixa-Medio{border-left-color:var(--amber)}
.action-card-header{
  display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:10px;
}
.action-card-id{font-size:.7rem;color:var(--muted);margin-bottom:2px}
.action-card-role{font-size:.85rem;font-weight:600;color:var(--text)}
.action-card-dept{font-size:.72rem;color:var(--muted)}
.action-card-prob{
  font-family:var(--font-d);
  font-size:1.3rem;
  font-weight:700;
  line-height:1;
}
.action-card-prob.Alto{color:var(--red)}
.action-card-prob.Medio{color:var(--amber)}
.action-card-factors{display:flex;flex-wrap:wrap;gap:5px}
.factor-tag{
  font-size:.65rem;
  padding:3px 8px;
  border-radius:20px;
  background:#F1F5F9;
  color:var(--muted);
  font-weight:500;
}

/* ── EMPTY STATE ─────────────────────────────────────────────── */
.empty-state{
  text-align:center;padding:40px 20px;color:var(--muted);
}
.empty-state p{margin-top:8px;font-size:.85rem}

/* ── SCROLLBAR ───────────────────────────────────────────────── */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:3px}

@media(max-width:1024px){
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .charts-row{grid-template-columns:1fr}
}
@media(max-width:768px){
  .sidebar{display:none}
  .main{margin-left:0;padding:20px 16px 40px}
}
</style>
</head>
<body>

<!-- ═══════════════════ SIDEBAR ═══════════════════ -->
<aside class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-logo">
      Attrition Risk
      <span>HR Business Partner</span>
    </div>
  </div>

  <nav class="sidebar-nav">
    <div class="nav-label">Navegação</div>
    <a class="nav-item active" href="#painel" onclick="setActive(this)">
      <span class="nav-icon">📊</span> Painel Geral
    </a>
    <a class="nav-item" href="#colaboradores" onclick="setActive(this)">
      <span class="nav-icon">👥</span> Colaboradores
    </a>
    <a class="nav-item" href="#acoes" onclick="setActive(this)">
      <span class="nav-icon">🎯</span> Acionáveis
    </a>

    <div class="nav-label" style="margin-top:16px">Alertas</div>
    <div style="padding:0 6px">
      <div class="stat-mini">
        <div class="stat-mini-label">Alto Risco</div>
        <div class="stat-mini-val" id="sb-alto">—</div>
        <div class="stat-mini-sub">colaboradores</div>
      </div>
      <div class="stat-mini">
        <div class="stat-mini-label">Com Ação</div>
        <div class="stat-mini-val" id="sb-acao">—</div>
        <div class="stat-mini-sub">conversas recomendadas</div>
      </div>
    </div>
  </nav>

  <div class="sidebar-stats" style="padding-bottom:24px">
    <div style="font-size:.65rem;color:rgba(255,255,255,.25);text-align:center">
      Dados: attrition_risk_ranking.csv<br>
      Modelo: XGBoost regularizado<br>
      Threshold: t = 0.35
    </div>
  </div>
</aside>

<!-- ═══════════════════ MAIN ═══════════════════ -->
<main class="main">

  <!-- ── PAINEL GERAL ── -->
  <section class="section" id="painel">
    <div class="section-title">Painel Geral</div>
    <div class="section-sub">Visão consolidada de risco de attrition por colaborador ativo</div>

    <div class="kpi-grid">
      <div class="kpi-card kpi-total">
        <div class="kpi-label">Total Ativos</div>
        <div class="kpi-value" id="k-total">—</div>
        <div class="kpi-desc">colaboradores no ranking</div>
      </div>
      <div class="kpi-card kpi-alto">
        <div class="kpi-label">Alto Risco</div>
        <div class="kpi-value" id="k-alto">—</div>
        <div class="kpi-desc">probabilidade ≥ 70%</div>
      </div>
      <div class="kpi-card kpi-medio">
        <div class="kpi-label">Risco Médio</div>
        <div class="kpi-value" id="k-medio">—</div>
        <div class="kpi-desc">probabilidade 35–70%</div>
      </div>
      <div class="kpi-card kpi-acao">
        <div class="kpi-label">Ação Recomendada</div>
        <div class="kpi-value" id="k-acao">—</div>
        <div class="kpi-desc">prob ≥ 35% · conversa preventiva</div>
      </div>
    </div>

    <div class="charts-row">
      <!-- Donut -->
      <div class="chart-card">
        <div class="chart-title">Distribuição de Risco</div>
        <div class="donut-wrap">
          <canvas id="donutChart"></canvas>
        </div>
        <div class="donut-legend" id="donut-legend"></div>
      </div>

      <!-- Dept stacked bar -->
      <div class="chart-card">
        <div class="chart-title">Risco por Departamento</div>
        <canvas id="deptChart" height="160"></canvas>
      </div>
    </div>

    <!-- Role horizontal bar -->
    <div class="role-card">
      <div class="chart-title">Top Cargos — Probabilidade Média de Saída (%)</div>
      <canvas id="roleChart" height="120"></canvas>
    </div>
  </section>

  <!-- ── COLABORADORES ── -->
  <section class="section" id="colaboradores">
    <div class="section-title">Colaboradores em Risco</div>
    <div class="section-sub">Tabela completa com filtros — clique no cabeçalho para ordenar</div>

    <div class="filters-bar">
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input class="search-input" id="search" type="text" placeholder="Buscar por ID, cargo ou departamento…">
      </div>
      <select class="filter-select" id="f-dept">
        <option value="">Todos os depts</option>
      </select>
      <select class="filter-select" id="f-role">
        <option value="">Todos os cargos</option>
      </select>
      <select class="filter-select" id="f-faixa">
        <option value="">Todas as faixas</option>
        <option value="Alto">Alto Risco</option>
        <option value="Medio">Risco Médio</option>
        <option value="Baixo">Baixo Risco</option>
      </select>
      <button class="toggle-btn" id="toggle-acao" onclick="toggleAcao()">
        🎯 Apenas com ação
      </button>
      <div class="filter-count" id="filter-count"></div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th onclick="sortBy(\'id\')" data-col="id">ID<span class="sort-arrow"></span></th>
            <th onclick="sortBy(\'dept\')" data-col="dept">Departamento<span class="sort-arrow"></span></th>
            <th onclick="sortBy(\'role\')" data-col="role">Cargo<span class="sort-arrow"></span></th>
            <th onclick="sortBy(\'level\')" data-col="level">Nível<span class="sort-arrow"></span></th>
            <th onclick="sortBy(\'prob\')" data-col="prob">Prob. Saída<span class="sort-arrow"></span></th>
            <th onclick="sortBy(\'faixa\')" data-col="faixa">Faixa<span class="sort-arrow"></span></th>
            <th>Satisfação</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
    <div class="pagination">
      <div id="page-info"></div>
      <div class="page-btns" id="page-btns"></div>
    </div>
  </section>

  <!-- ── ACIONÁVEIS ── -->
  <section class="section" id="acoes">
    <div class="section-title">Acionáveis</div>
    <div class="section-sub">Colaboradores com conversa preventiva recomendada, agrupados por departamento</div>

    <div class="action-banner">
      <div class="action-banner-icon">🎯</div>
      <div class="action-banner-text">
        <h3>Protocolo de Retenção Ativa</h3>
        <p>Agende 1:1 com cada colaborador listado — threshold t = 0.35 garante ~90% de recall com custo de apenas uma conversa</p>
      </div>
      <div class="action-banner-stat">
        <div class="big" id="banner-total">—</div>
        <div class="lbl">colaboradores</div>
      </div>
    </div>

    <div id="action-sections"></div>
  </section>

</main>

<script>
const RAW = %DATA_JSON%;
const EMPLOYEES = RAW.employees;

// ── populate KPIs ────────────────────────────────────────────────────────────
const K = RAW.kpis;
document.getElementById("k-total").textContent = K.total.toLocaleString("pt-BR");
document.getElementById("k-alto").textContent  = K.alto;
document.getElementById("k-medio").textContent = K.medio;
document.getElementById("k-acao").textContent  = K.acao;
document.getElementById("sb-alto").textContent = K.alto;
document.getElementById("sb-acao").textContent = K.acao;
document.getElementById("banner-total").textContent = K.acao;

// ── Donut chart ──────────────────────────────────────────────────────────────
(function(){
  const D = RAW.donut;
  const colors = ["#DC2626","#D97706","#16A34A"];
  new Chart(document.getElementById("donutChart"),{
    type:"doughnut",
    data:{
      labels:D.labels,
      datasets:[{data:D.values,backgroundColor:colors,borderWidth:0,hoverOffset:4}]
    },
    options:{
      cutout:"70%",
      plugins:{legend:{display:false},tooltip:{
        callbacks:{label:function(c){
          const total=D.values.reduce((a,b)=>a+b,0);
          return " "+c.raw+" ("+Math.round(c.raw/total*100)+"%)";
        }}
      }}
    }
  });
  const legend = document.getElementById("donut-legend");
  D.labels.forEach(function(lbl,i){
    const total = D.values.reduce(function(a,b){return a+b;},0);
    const pct = Math.round(D.values[i]/total*100);
    legend.innerHTML += "<div class=\\"legend-item\\"><span class=\\"legend-dot\\" style=\\"background:"+colors[i]+"\\"></span>"+lbl+"<span class=\\"legend-val\\">"+D.values[i]+" ("+pct+"%)</span></div>";
  });
})();

// ── Dept stacked bar ─────────────────────────────────────────────────────────
(function(){
  const D = RAW.dept_data;
  new Chart(document.getElementById("deptChart"),{
    type:"bar",
    data:{
      labels:D.map(function(d){return d.dept}),
      datasets:[
        {label:"Alto",data:D.map(function(d){return d.alto}),backgroundColor:"#DC2626",borderRadius:3},
        {label:"Médio",data:D.map(function(d){return d.medio}),backgroundColor:"#D97706",borderRadius:3},
        {label:"Baixo",data:D.map(function(d){return d.baixo}),backgroundColor:"#86EFAC",borderRadius:3}
      ]
    },
    options:{
      responsive:true,
      plugins:{legend:{position:"top",labels:{font:{family:"DM Sans",size:11},boxWidth:10}}},
      scales:{
        x:{stacked:true,grid:{display:false},ticks:{font:{family:"DM Sans",size:11}}},
        y:{stacked:true,grid:{color:"#F1F5F9"},ticks:{font:{family:"DM Sans",size:11}}}
      }
    }
  });
})();

// ── Role horizontal bar ──────────────────────────────────────────────────────
(function(){
  const D = RAW.role_data.slice().reverse();
  new Chart(document.getElementById("roleChart"),{
    type:"bar",
    data:{
      labels:D.map(function(d){return d.role}),
      datasets:[{
        label:"Prob. Média (%)",
        data:D.map(function(d){return d.avg}),
        backgroundColor:D.map(function(d){
          return d.avg>=70?"#DC2626":d.avg>=35?"#D97706":"#16A34A";
        }),
        borderRadius:4,
        barThickness:16
      }]
    },
    options:{
      indexAxis:"y",
      responsive:true,
      plugins:{legend:{display:false},tooltip:{
        callbacks:{label:function(c){return " "+c.raw+"% média";}}
      }},
      scales:{
        x:{grid:{color:"#F1F5F9"},max:100,ticks:{callback:function(v){return v+"%"},font:{family:"DM Sans",size:10}}},
        y:{grid:{display:false},ticks:{font:{family:"DM Sans",size:11}}}
      }
    }
  });
})();

// ── TABLE ─────────────────────────────────────────────────────────────────────
var filtered   = EMPLOYEES.slice();
var sortCol    = "prob";
var sortDir    = -1;
var currentPage = 1;
var PAGE_SIZE   = 25;
var onlyAcao    = false;

// populate filter dropdowns
var depts = [...new Set(EMPLOYEES.map(function(e){return e.dept}))].sort();
var roles = [...new Set(EMPLOYEES.map(function(e){return e.role}))].sort();
var deptSel = document.getElementById("f-dept");
var roleSel = document.getElementById("f-role");
depts.forEach(function(d){
  var o=document.createElement("option"); o.value=d; o.textContent=d; deptSel.appendChild(o);
});
roles.forEach(function(r){
  var o=document.createElement("option"); o.value=r; o.textContent=r; roleSel.appendChild(o);
});

document.getElementById("search").addEventListener("input", applyFilters);
document.getElementById("f-dept").addEventListener("change", applyFilters);
document.getElementById("f-role").addEventListener("change", applyFilters);
document.getElementById("f-faixa").addEventListener("change", applyFilters);

function toggleAcao(){
  onlyAcao = !onlyAcao;
  document.getElementById("toggle-acao").classList.toggle("active", onlyAcao);
  applyFilters();
}

function applyFilters(){
  var q   = document.getElementById("search").value.toLowerCase();
  var dep = document.getElementById("f-dept").value;
  var rol = document.getElementById("f-role").value;
  var fai = document.getElementById("f-faixa").value;

  filtered = EMPLOYEES.filter(function(e){
    if(q && !(
      String(e.id).includes(q) ||
      e.role.toLowerCase().includes(q) ||
      e.dept.toLowerCase().includes(q)
    )) return false;
    if(dep && e.dept !== dep) return false;
    if(rol && e.role !== rol) return false;
    if(fai && e.faixa !== fai) return false;
    if(onlyAcao && !e.acao) return false;
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

function satDots(val, max){
  var html="<div class=\\"sat-dots\\">";
  for(var i=1;i<=max;i++){
    html += "<span class=\\"dot "+(i<=val?"filled-"+Math.round(val):"empty")+"\\"></span>";
  }
  html+="</div>";
  return html;
}

function renderTable(){
  var total = filtered.length;
  var totalPages = Math.max(1, Math.ceil(total/PAGE_SIZE));
  if(currentPage > totalPages) currentPage = totalPages;

  var start = (currentPage-1)*PAGE_SIZE;
  var page  = filtered.slice(start, start+PAGE_SIZE);

  var tbody = document.getElementById("table-body");
  if(!page.length){
    tbody.innerHTML = "<tr><td colspan=\\"8\\" style=\\"text-align:center;padding:32px;color:#94A3B8\\">Nenhum colaborador encontrado</td></tr>";
  } else {
    tbody.innerHTML = page.map(function(e){
      var probColor = e.prob>=70?"#DC2626":e.prob>=35?"#D97706":"#16A34A";
      var barW = Math.min(100,e.prob);
      return "<tr>"
        +"<td><strong>#"+e.id+"</strong></td>"
        +"<td>"+e.dept+"</td>"
        +"<td>"+e.role+"</td>"
        +"<td style=\\"text-align:center\\">"+e.level+"</td>"
        +"<td><div class=\\"prob-bar-wrap\\">"
          +"<span style=\\"font-weight:600;color:"+probColor+";min-width:38px\\">"
          +e.prob.toFixed(1)+"%</span>"
          +"<div class=\\"prob-bar-bg\\"><div class=\\"prob-bar-fill\\" style=\\"width:"+barW+"%;background:"+probColor+"\\"></div></div>"
          +"</div></td>"
        +"<td><span class=\\"faixa-badge faixa-"+e.faixa+"\\">"+
          (e.faixa==="Alto"?"Alto":e.faixa==="Medio"?"Médio":"Baixo")+"</span></td>"
        +"<td>"+satDots(e.job_sat,4)+"</td>"
        +"<td>"+(e.acao?"<span class=\\"acao-pill\\">🎯 Conversa</span>":"")+"</td>"
        +"</tr>";
    }).join("");
  }

  document.getElementById("filter-count").textContent =
    total.toLocaleString("pt-BR")+" colaborador"+(total!==1?"es":"");

  // pagination info
  document.getElementById("page-info").textContent =
    "Página "+currentPage+" de "+totalPages+" · "+total+" resultado"+(total!==1?"s":"");

  // page buttons
  var btns = document.getElementById("page-btns");
  btns.innerHTML="";
  // prev
  var prev=document.createElement("button");
  prev.className="page-btn"; prev.textContent="‹ Ant";
  prev.disabled=(currentPage===1);
  prev.onclick=function(){currentPage--;renderTable();};
  btns.appendChild(prev);
  // numbered (max 5 around current)
  var lo=Math.max(1,currentPage-2), hi=Math.min(totalPages,lo+4);
  for(var p=lo;p<=hi;p++){
    (function(pg){
      var b=document.createElement("button");
      b.className="page-btn"+(pg===currentPage?" active":"");
      b.textContent=pg;
      b.onclick=function(){currentPage=pg;renderTable();};
      btns.appendChild(b);
    })(p);
  }
  // next
  var nxt=document.createElement("button");
  nxt.className="page-btn"; nxt.textContent="Próx ›";
  nxt.disabled=(currentPage===totalPages);
  nxt.onclick=function(){currentPage++;renderTable();};
  btns.appendChild(nxt);
}

// initial sort marker
document.querySelector("th[data-col=\\"prob\\"]").classList.add("sort-desc");
applyFilters();

// ── ACIONÁVEIS ───────────────────────────────────────────────────────────────
(function(){
  var actionable = EMPLOYEES.filter(function(e){return e.acao;});
  var byDept = {};
  actionable.forEach(function(e){
    if(!byDept[e.dept]) byDept[e.dept]=[];
    byDept[e.dept].push(e);
  });
  var container = document.getElementById("action-sections");
  Object.keys(byDept).sort().forEach(function(dept){
    var emps = byDept[dept].sort(function(a,b){return b.prob-a.prob;});
    var sec = document.createElement("div");
    sec.className="dept-section";
    sec.innerHTML="<div class=\\"dept-section-title\\">"+dept+
      "<span class=\\"count-badge\\">"+emps.length+" colaborador"+(emps.length!==1?"es":"")+"</span></div>"+
      "<div class=\\"action-cards\\" id=\\"cards-"+dept.replace(/\\s/g,"_")+"\\"</div>";
    container.appendChild(sec);
    var cards = sec.querySelector(".action-cards");
    emps.forEach(function(e){
      var card = document.createElement("div");
      card.className="action-card faixa-"+e.faixa;
      var factTags = e.factors.map(function(f){
        return "<span class=\\"factor-tag\\">"+f+"</span>";
      }).join("");
      card.innerHTML=
        "<div class=\\"action-card-header\\">"
          +"<div>"
            +"<div class=\\"action-card-id\\">ID #"+e.id+"</div>"
            +"<div class=\\"action-card-role\\">"+e.role+"</div>"
            +"<div class=\\"action-card-dept\\">"+e.dept+"</div>"
          +"</div>"
          +"<div class=\\"action-card-prob "+e.faixa+"\\">"+e.prob.toFixed(0)+"%</div>"
        +"</div>"
        +(factTags?"<div class=\\"action-card-factors\\">"+factTags+"</div>":"");
      cards.appendChild(card);
    });
  });
})();

// ── sidebar nav active ───────────────────────────────────────────────────────
function setActive(el){
  document.querySelectorAll(".nav-item").forEach(function(a){a.classList.remove("active");});
  el.classList.add("active");
}
window.addEventListener("scroll",function(){
  var sections=[["painel",0],["colaboradores",1],["acoes",2]];
  var items=document.querySelectorAll(".nav-item");
  for(var i=sections.length-1;i>=0;i--){
    var el=document.getElementById(sections[i][0]);
    if(el && el.getBoundingClientRect().top<=120){
      items.forEach(function(a){a.classList.remove("active");});
      items[sections[i][1]].classList.add("active");
      break;
    }
  }
});
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
