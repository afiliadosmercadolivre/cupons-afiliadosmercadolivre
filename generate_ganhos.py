"""
generate_ganhos.py — Ganhos Extras Afiliados ML
"""

import json, os, re
from datetime import datetime, date, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1ipuukzdhcKtTgqrK5MowmRXculVbYnLBSy1ULQEOZjY"
SHEET_NAME     = "Ganhos Extras"
DATA_START_ROW = 3
OUTPUT_FILE    = "ganhos-extras.html"

# ── AUTH ──────────────────────────────────────────────────────────────────────

def get_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("Secret GOOGLE_SERVICE_ACCOUNT_JSON não encontrado.")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    return build("sheets", "v4", credentials=creds)

def fetch_rows(service):
    range_name = f"'{SHEET_NAME}'!B{DATA_START_ROW}:F5000"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING"
    ).execute()
    return result.get("values", [])

# ── PARSE ─────────────────────────────────────────────────────────────────────

def safe_get(row, idx, default=""):
    try:
        v = row[idx]
        return str(v).strip() if v is not None else default
    except (IndexError, AttributeError):
        return default

def parse_date(s):
    if s is None or s == "":
        return None
    # Serial numérico do Google Sheets (epoch 30/12/1899)
    if isinstance(s, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(s))
    s = str(s).strip()
    if not s:
        return None
    # Normaliza D/M/YYYY ou D/M/YY (sem zero à esquerda)
    parts = s.split('/')
    if len(parts) == 3:
        d, m, y = parts
        s = f"{int(d):02d}/{int(m):02d}/{y.strip()}"
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def days_left(s):
    d = parse_date(s)
    if d is None:
        return 9999
    return (d - date.today()).days

def fmt_date(s):
    """Formata qualquer valor de data para DD/MM/YYYY."""
    d = parse_date(s)
    return d.strftime("%d/%m/%Y") if d else str(s)

def parse_rows(rows):
    items = []
    for row in rows:
        # Range começa em B, então idx 0=B, 1=C, 2=D, 3=E, 4=F
        categoria   = safe_get(row, 0)
        data_inicio = row[1] if len(row) > 1 else ""
        data_fim    = row[2] if len(row) > 2 else ""
        url         = safe_get(row, 3)
        ganho_max   = safe_get(row, 4)

        if not categoria:
            continue

        dl = days_left(data_fim)
        if dl < 0:
            continue

        # Renomeia CPG
        categoria = categoria.replace("CPG (Bens de Consumo)", "Bens de Consumo")

        items.append({
            "categoria":   categoria,
            "data_inicio": fmt_date(data_inicio),
            "data_fim":    fmt_date(data_fim),
            "url":         url,
            "ganho_max":   ganho_max,
            "days_left":   dl,
        })

    items.sort(key=lambda x: x["days_left"])
    return items

# ── HTML ──────────────────────────────────────────────────────────────────────

def to_js(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ganhos Extras — Afiliados Mercado Livre</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --yellow:#FFE600;--yellow-dark:#E6CF00;--blue:#0A0080;
      --white:#FFFFFF;--bg:#F7F7F7;--text:#1A1A1A;--muted:#666;
      --border:#E8E8E8;--green:#00A650;--red:#E8003C;
      --orange:#FF6000;--purple:#7B2FBE;--radius-pill:50px;--radius-card:12px;
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Montserrat',Arial,sans-serif;background:var(--bg);color:var(--text)}}
    .hdr{{background:var(--yellow);padding:0 24px;height:64px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.12)}}
    .hdr-logo{{display:flex;align-items:center;gap:12px;text-decoration:none}}
    .hdr-pill{{background:var(--blue);color:var(--yellow);font-size:13px;font-weight:900;padding:6px 18px;border-radius:var(--radius-pill);white-space:nowrap}}
    .hdr-sub{{font-size:12px;font-weight:700;color:var(--blue);opacity:.65;text-transform:uppercase;letter-spacing:.06em}}
    .hdr-nav{{display:flex;gap:8px;align-items:center}}
    .hdr-link{{font-size:12px;font-weight:700;color:var(--blue);text-decoration:none;padding:6px 14px;border-radius:var(--radius-pill);border:2px solid var(--blue);opacity:.6;transition:opacity .15s}}
    .hdr-link:hover{{opacity:1}}
    .hdr-link.active{{background:var(--blue);color:var(--yellow);opacity:1}}
    .hdr-ts{{font-size:12px;font-weight:600;color:var(--blue);opacity:.6}}
    .hero{{background:var(--blue);padding:36px 24px 32px}}
    .hero-inner{{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}}
    .hero-left h1{{font-size:clamp(22px,3.5vw,38px);font-weight:900;color:var(--white);line-height:1.1;letter-spacing:-.02em}}
    .hero-left h1 span{{color:var(--yellow)}}
    .hero-left p{{font-size:14px;color:rgba(255,255,255,.6);margin-top:8px;font-weight:600}}
    .hero-pills{{display:flex;gap:10px;flex-wrap:wrap}}
    .hero-stat{{background:rgba(255,255,255,.08);border:1.5px solid rgba(255,230,0,.25);border-radius:var(--radius-pill);padding:10px 20px;display:flex;flex-direction:column;align-items:center;gap:2px}}
    .hero-stat-n{{font-size:26px;font-weight:900;color:var(--yellow);line-height:1}}
    .hero-stat-l{{font-size:10px;font-weight:700;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.08em}}
    .toolbar{{background:var(--white);border-bottom:1px solid var(--border);padding:12px 24px;position:sticky;top:64px;z-index:90}}
    .toolbar-inner{{max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
    .search{{margin-left:auto;padding:8px 16px;border:2px solid var(--border);border-radius:var(--radius-pill);font-family:'Montserrat',sans-serif;font-size:13px;font-weight:600;outline:none;width:220px;transition:border-color .15s}}
    .search:focus{{border-color:var(--blue)}}
    .count-lbl{{font-size:13px;font-weight:700;color:var(--muted)}}
    .list-wrap{{max-width:1100px;margin:24px auto;padding:0 24px;display:flex;flex-direction:column;gap:10px}}
    .card{{background:var(--white);border-radius:var(--radius-card);border:1.5px solid var(--border);display:grid;grid-template-columns:110px 1fr auto;overflow:hidden;transition:box-shadow .18s,transform .18s}}
    .card:hover{{box-shadow:0 6px 24px rgba(0,0,0,.1);transform:translateY(-1px)}}
    .card.hoje{{border-left:5px solid var(--red)}}
    .card.breve{{border-left:5px solid var(--orange)}}
    .card.ok{{border-left:5px solid var(--green)}}
    .card-badge{{background:var(--purple);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:16px 8px}}
    .card.hoje .card-badge{{background:var(--red)}}
    .badge-icon{{font-size:28px;line-height:1}}
    .badge-lbl{{font-size:9px;font-weight:800;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.06em;text-align:center;margin-top:4px}}
    .card-body{{padding:16px 20px;display:flex;flex-direction:column;gap:10px;min-width:0}}
    .card-top{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
    .cat-name{{font-size:18px;font-weight:900;color:var(--text)}}
    .pill-tag{{font-size:10px;font-weight:800;padding:3px 10px;border-radius:var(--radius-pill);text-transform:uppercase;letter-spacing:.06em}}
    .pill-hoje{{background:#FFE6EC;color:var(--red)}}
    .pill-breve{{background:#FFF0E6;color:var(--orange)}}
    .card-nums{{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-end}}
    .num-item{{display:flex;flex-direction:column;gap:1px}}
    .num-label{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
    .num-val{{font-size:15px;font-weight:800;color:var(--text)}}
    .num-val.green{{color:var(--green);font-size:20px}}
    .num-val.purple{{color:var(--purple)}}
    .expiry-pill{{font-size:11px;font-weight:800;padding:3px 10px;border-radius:var(--radius-pill)}}
    .expiry-pill.ok{{background:#E6F9EE;color:var(--green)}}
    .expiry-pill.hoje{{background:#FFE6EC;color:var(--red)}}
    .expiry-pill.breve{{background:#FFF0E6;color:var(--orange)}}
    .card-action{{padding:20px 16px;display:flex;align-items:center;justify-content:center;border-left:1px solid var(--border);min-width:130px}}
    .ver-btn{{background:var(--yellow);border:none;border-radius:var(--radius-pill);padding:11px 20px;font-family:'Montserrat',sans-serif;font-size:13px;font-weight:900;color:var(--blue);cursor:pointer;transition:background .12s,transform .1s;width:100%;white-space:nowrap;text-decoration:none;display:block;text-align:center}}
    .ver-btn:hover{{background:var(--yellow-dark);transform:scale(1.03)}}
    .ver-btn.no-url{{background:var(--border);color:var(--muted);cursor:default}}
    .ver-btn.no-url:hover{{transform:none}}
    .empty{{text-align:center;padding:64px 24px;color:var(--muted);font-size:15px;font-weight:700;background:var(--white);border-radius:var(--radius-card);border:1.5px solid var(--border);display:none}}
    .empty.show{{display:block}}
    .disclaimer{{max-width:1100px;margin:0 auto;padding:0 24px 16px}}
    .disclaimer p{{font-size:12px;font-weight:600;color:#888;background:var(--white);border:1.5px solid var(--border);border-radius:8px;padding:12px 16px;line-height:1.6}}
    .footer{{text-align:center;padding:32px 24px;font-size:12px;font-weight:600;color:var(--muted);border-top:1px solid var(--border);margin-top:16px}}
    @media(max-width:640px){{.card{{grid-template-columns:80px 1fr}}.card-action{{display:none}}.search{{width:130px}}.hdr-nav{{display:none}}}}
  </style>
</head>
<body>
<header class="hdr">
  <a class="hdr-logo" href="#">
    <div class="hdr-pill">Ganhos Extras</div>
    <span class="hdr-sub">Mercado Livre</span>
  </a>
  <nav class="hdr-nav">
    <a class="hdr-link" href="index.html">Cupons</a>
    <a class="hdr-link active" href="ganhos-extras.html">Ganhos Extras</a>
  </nav>
  <span class="hdr-ts">Atualizado em {generated_at}</span>
</header>

<div class="hero">
  <div class="hero-inner">
    <div class="hero-left">
      <h1>Listas com <span>ganhos extras</span><br>para afiliados</h1>
      <p>Comissões adicionais de vendedores e marcas além do % padrão do Mercado Livre</p>
    </div>
    <div class="hero-pills" id="hero-stats"></div>
  </div>
</div>

<div class="toolbar">
  <div class="toolbar-inner">
    <span class="count-lbl"><strong id="count-visible">0</strong> listas ativas</span>
    <input class="search" id="search" type="search" placeholder="🔍  Buscar categoria…"/>
  </div>
</div>

<div class="list-wrap">
  <div id="list"></div>
  <div class="empty" id="empty">Nenhum item encontrado.</div>
</div>

<div class="disclaimer">
  <p>⚠️ <strong>Atenção:</strong> Os ganhos extras listados podem ser encerrados antecipadamente sem aviso prévio. Sempre verifique a validade antes de divulgar.</p>
</div>
<div class="footer">Fonte: Planejamento Estratégico Mensal — Afiliados Mercado Livre · Atualização automática a cada hora</div>

<script>
const ITEMS = {items_json};
function dl(s){{
  if(!s)return 9999;
  const parts=s.split('/').map(Number);
  return Math.round((new Date(parts[2],parts[1]-1,parts[0])-new Date(new Date().toDateString()))/86400000);
}}
function expInfo(s){{
  const d=dl(s);
  if(d<0) return{{l:'Expirado',cls:'exp'}};
  if(d===0)return{{l:'Expira hoje',cls:'hoje'}};
  if(d<=3) return{{l:d+'d restantes',cls:'breve'}};
  return        {{l:'Válido até '+s,cls:'ok'}};
}}
function cardCls(c){{
  const d=dl(c.data_fim);
  if(d===0)return'hoje';if(d<=3)return'breve';return'ok';
}}
let sq='';
function matches(c){{
  if(sq){{const q=sq.toLowerCase();return c.categoria.toLowerCase().includes(q);}}
  return true;
}}
function renderCard(c){{
  const exp=expInfo(c.data_fim),cls=cardCls(c);
  const expTag=cls==='hoje'||cls==='breve'?`<span class="pill-tag pill-${{cls}}">${{exp.l}}</span>`:'';
  const btnHTML=c.url
    ?`<a class="ver-btn" href="${{c.url}}" target="_blank" rel="noopener">Ver lista</a>`
    :`<span class="ver-btn no-url">Sem link</span>`;
  return`<div class="card ${{cls}}">
  <div class="card-badge"><div class="badge-icon">💰</div><div class="badge-lbl">Ganho Extra</div></div>
  <div class="card-body">
    <div class="card-top"><span class="cat-name">${{c.categoria}}</span>${{expTag}}</div>
    <div class="card-nums">
      <div class="num-item"><span class="num-label">Ganho máximo</span><span class="num-val green">${{c.ganho_max||'—'}}</span></div>
      <div class="num-item"><span class="num-label">Período</span><span class="num-val purple">${{c.data_inicio}} → ${{c.data_fim}}</span></div>
      <div class="num-item"><span class="num-label">Validade</span><span class="expiry-pill ${{exp.cls}}">${{exp.l}}</span></div>
    </div>
  </div>
  <div class="card-action">${{btnHTML}}</div>
</div>`;
}}
function render(){{
  const v=ITEMS.filter(matches);
  document.getElementById('list').innerHTML=v.map(renderCard).join('');
  document.getElementById('count-visible').textContent=v.length;
  document.getElementById('empty').classList.toggle('show',v.length===0);
  const hoje=ITEMS.filter(c=>dl(c.data_fim)===0).length;
  document.getElementById('hero-stats').innerHTML=`
    <div class="hero-stat"><div class="hero-stat-n">${{ITEMS.length}}</div><div class="hero-stat-l">Listas ativas</div></div>
    ${{hoje?`<div class="hero-stat"><div class="hero-stat-n" style="color:var(--red)">${{hoje}}</div><div class="hero-stat-l">Expiram hoje</div></div>`:''}}
  `;
}}
document.getElementById('search').addEventListener('input',e=>{{sq=e.target.value.trim();render()}});
render();
</script>
</body>
</html>
"""

def generate_html(items):
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3)))
    html = HTML.format(
        generated_at=now.strftime("%d/%m/%Y %H:%M"),
        items_json=to_js(items),
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {OUTPUT_FILE} gerado com {len(items)} itens")

if __name__ == "__main__":
    print("🔐 Autenticando…")
    service = get_service()
    print("📊 Buscando Ganhos Extras…")
    rows = fetch_rows(service)
    print(f"   {len(rows)} linhas lidas")
    items = parse_rows(rows)
    print(f"   {len(items)} itens ativos")
    generate_html(items)
