"""
generate_ganhos.py
Lê a aba "Ganhos Extras" da planilha de Ganhos e gera ganhos-extras.html
"""

import json, os, re
from datetime import datetime, date, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1ipuukzdhcKtTgqrK5MowmRXculVbYnLBSy1ULQEOZjY"
SHEET_NAME     = "Ganhos Extras"
DATA_START_ROW = 3
OUTPUT_FILE    = "ganhos-extras.html"

COL = {
    "categoria":   1,  # B
    "data_inicio": 2,  # C
    "data_fim":    3,  # D
    "url":         4,  # E
    "ganho_max":   5,  # F
}

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
        spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    return result.get("values", [])

# ── PARSE ─────────────────────────────────────────────────────────────────────

def safe_get(row, idx, default=""):
    try:
        return row[idx].strip()
    except (IndexError, AttributeError):
        return default

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    # Normaliza D/M/YYYY para DD/MM/YYYY
    parts = s.split('/')
    if len(parts) == 3:
        d, m, y = parts
        s = f"{int(d):02d}/{int(m):02d}/{y}"
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def days_left(s):
    d = parse_date(s)
    return (d - date.today()).days if d else 9999

def is_active(s):
    return days_left(s) >= 0

def expiry_info(dia_fim):
    d = days_left(dia_fim)
    if d < 0:  return {"label": "Expirado",      "cls": "exp"}
    if d == 0: return {"label": "Expira hoje",   "cls": "hoje"}
    if d <= 3: return {"label": f"{d}d restantes","cls": "breve"}
    return            {"label": f"Válido até {dia_fim}", "cls": "ok"}

def parse_rows(rows):
    items = []
    for row in rows:
        # Colunas lidas começam em B, mas range começa em B então idx 0=B
        categoria   = safe_get(row, 0)
        data_inicio = safe_get(row, 1)
        data_fim    = safe_get(row, 2)
        url         = safe_get(row, 3)
        ganho_max   = safe_get(row, 4)

        if not categoria or not data_fim:
            continue
        dl_val = days_left(data_fim)
        if dl_val < 0:
            continue

        categoria = categoria.replace("CPG (Bens de Consumo)", "Bens de Consumo")
        items.append({
            "categoria":   categoria,
            "data_inicio": data_inicio,
            "data_fim":    data_fim,
            "url":         url,
            "ganho_max":   ganho_max,
            "days_left":   days_left(data_fim),
        })

    items.sort(key=lambda x: (x["days_left"],))
    return items

def debug_rows(rows):
    """Imprime todas as linhas para diagnóstico."""
    print("\n=== DEBUG LINHAS BRUTAS ===")
    for i, row in enumerate(rows):
        categoria   = safe_get(row, 0)
        data_inicio = safe_get(row, 1)
        data_fim    = safe_get(row, 2)
        ganho_max   = safe_get(row, 4)
        d = parse_date(data_fim)
        dl_val = (d - date.today()).days if d else None
        print(f"L{i+3}: cat='{categoria}' | inicio='{data_inicio}' | fim='{data_fim}' | parsed={d} | days_left={dl_val} | ganho='{ganho_max}'")
    print("=== FIM DEBUG ===\n")

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
      --yellow: #FFE600;
      --yellow-dark: #E6CF00;
      --blue: #0A0080;
      --white: #FFFFFF;
      --bg: #F7F7F7;
      --text: #1A1A1A;
      --muted: #666;
      --border: #E8E8E8;
      --green: #00A650;
      --red: #E8003C;
      --orange: #FF6000;
      --purple: #7B2FBE;
      --radius-pill: 50px;
      --radius-card: 12px;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Montserrat', Arial, sans-serif; background: var(--bg); color: var(--text); }}

    /* HEADER */
    .hdr {{ background: var(--yellow); padding: 0 24px; height: 64px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
    .hdr-logo {{ display: flex; align-items: center; gap: 12px; text-decoration: none; }}
    .hdr-pill {{ background: var(--blue); color: var(--yellow); font-size: 13px; font-weight: 900; padding: 6px 18px; border-radius: var(--radius-pill); white-space: nowrap; }}
    .hdr-sub {{ font-size: 12px; font-weight: 700; color: var(--blue); opacity: .65; text-transform: uppercase; letter-spacing: .06em; }}
    .hdr-nav {{ display: flex; gap: 8px; align-items: center; }}
    .hdr-link {{ font-size: 12px; font-weight: 700; color: var(--blue); text-decoration: none; padding: 6px 14px; border-radius: var(--radius-pill); border: 2px solid var(--blue); opacity: .6; transition: opacity .15s; }}
    .hdr-link:hover {{ opacity: 1; }}
    .hdr-link.active {{ background: var(--blue); color: var(--yellow); opacity: 1; }}
    .hdr-ts {{ font-size: 12px; font-weight: 600; color: var(--blue); opacity: .6; }}

    /* HERO */
    .hero {{ background: var(--blue); padding: 36px 24px 32px; }}
    .hero-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap; }}
    .hero-left h1 {{ font-size: clamp(22px,3.5vw,38px); font-weight: 900; color: var(--white); line-height: 1.1; letter-spacing: -.02em; }}
    .hero-left h1 span {{ color: var(--yellow); }}
    .hero-left p {{ font-size: 14px; color: rgba(255,255,255,.6); margin-top: 8px; font-weight: 600; }}
    .hero-pills {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .hero-stat {{ background: rgba(255,255,255,.08); border: 1.5px solid rgba(255,230,0,.25); border-radius: var(--radius-pill); padding: 10px 20px; display: flex; flex-direction: column; align-items: center; gap: 2px; }}
    .hero-stat-n {{ font-size: 26px; font-weight: 900; color: var(--yellow); line-height: 1; }}
    .hero-stat-l {{ font-size: 10px; font-weight: 700; color: rgba(255,255,255,.5); text-transform: uppercase; letter-spacing: .08em; }}

    /* TOOLBAR */
    .toolbar {{ background: var(--white); border-bottom: 1px solid var(--border); padding: 12px 24px; position: sticky; top: 64px; z-index: 90; }}
    .toolbar-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .filter-btn {{ background: var(--white); border: 2px solid var(--border); color: var(--muted); font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 700; padding: 6px 16px; border-radius: var(--radius-pill); cursor: pointer; transition: all .15s; white-space: nowrap; }}
    .filter-btn:hover {{ border-color: var(--blue); color: var(--blue); }}
    .filter-btn.active {{ background: var(--blue); border-color: var(--blue); color: var(--yellow); }}
    .filter-btn .cnt {{ font-size: 11px; opacity: .75; margin-left: 4px; }}
    .search {{ margin-left: auto; padding: 8px 16px; border: 2px solid var(--border); border-radius: var(--radius-pill); font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 600; outline: none; width: 220px; transition: border-color .15s; }}
    .search:focus {{ border-color: var(--blue); }}

    /* LIST */
    .list-wrap {{ max-width: 1100px; margin: 24px auto; padding: 0 24px; display: flex; flex-direction: column; gap: 10px; }}

    /* CARD */
    .card {{ background: var(--white); border-radius: var(--radius-card); border: 1.5px solid var(--border); display: grid; grid-template-columns: 110px 1fr auto; overflow: hidden; transition: box-shadow .18s, transform .18s; }}
    .card:hover {{ box-shadow: 0 6px 24px rgba(0,0,0,.1); transform: translateY(-1px); }}
    .card.hoje {{ border-left: 5px solid var(--red); }}
    .card.breve {{ border-left: 5px solid var(--orange); }}
    .card.ok {{ border-left: 5px solid var(--green); }}

    /* badge */
    .card-badge {{ background: var(--purple); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; padding: 16px 8px; }}
    .card.hoje .card-badge {{ background: var(--red); }}
    .badge-icon {{ font-size: 28px; line-height: 1; }}
    .badge-lbl {{ font-size: 9px; font-weight: 800; color: rgba(255,255,255,.7); text-transform: uppercase; letter-spacing: .06em; text-align: center; margin-top: 4px; }}

    /* body */
    .card-body {{ padding: 16px 20px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
    .card-top {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .cat-name {{ font-size: 18px; font-weight: 900; color: var(--text); }}
    .pill-tag {{ font-size: 10px; font-weight: 800; padding: 3px 10px; border-radius: var(--radius-pill); text-transform: uppercase; letter-spacing: .06em; }}
    .pill-expira {{ background: #FFE6EC; color: var(--red); }}
    .pill-breve {{ background: #FFF0E6; color: var(--orange); }}

    .card-nums {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-end; }}
    .num-item {{ display: flex; flex-direction: column; gap: 1px; }}
    .num-label {{ font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); }}
    .num-val {{ font-size: 15px; font-weight: 800; color: var(--text); }}
    .num-val.green {{ color: var(--green); font-size: 20px; }}
    .num-val.purple {{ color: var(--purple); }}

    .card-footer {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .date-txt {{ font-size: 12px; font-weight: 600; color: var(--muted); }}
    .expiry-pill {{ font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: var(--radius-pill); }}
    .expiry-pill.ok {{ background: #E6F9EE; color: var(--green); }}
    .expiry-pill.hoje {{ background: #FFE6EC; color: var(--red); }}
    .expiry-pill.breve {{ background: #FFF0E6; color: var(--orange); }}

    /* action */
    .card-action {{ padding: 20px 16px; display: flex; align-items: center; justify-content: center; border-left: 1px solid var(--border); min-width: 130px; }}
    .ver-btn {{ background: var(--yellow); border: none; border-radius: var(--radius-pill); padding: 11px 20px; font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 900; color: var(--blue); cursor: pointer; transition: background .12s, transform .1s; width: 100%; white-space: nowrap; text-decoration: none; display: block; text-align: center; }}
    .ver-btn:hover {{ background: var(--yellow-dark); transform: scale(1.03); }}
    .ver-btn.no-url {{ background: var(--border); color: var(--muted); cursor: default; }}
    .ver-btn.no-url:hover {{ transform: none; }}

    /* empty */
    .empty {{ text-align: center; padding: 64px 24px; color: var(--muted); font-size: 15px; font-weight: 700; background: var(--white); border-radius: var(--radius-card); border: 1.5px solid var(--border); display: none; }}
    .empty.show {{ display: block; }}

    /* disclaimer */
    .disclaimer {{ max-width: 1100px; margin: 0 auto; padding: 0 24px 16px; }}
    .disclaimer p {{ font-size: 12px; font-weight: 600; color: #888; background: var(--white); border: 1.5px solid var(--border); border-radius: 8px; padding: 12px 16px; line-height: 1.6; }}

    /* footer */
    .footer {{ text-align: center; padding: 32px 24px; font-size: 12px; font-weight: 600; color: var(--muted); border-top: 1px solid var(--border); margin-top: 16px; }}

    @media (max-width: 640px) {{
      .card {{ grid-template-columns: 80px 1fr; }}
      .card-action {{ display: none; }}
      .search {{ width: 130px; }}
      .hdr-nav {{ display: none; }}
    }}
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
    <button class="filter-btn active" data-f="all">Todos <span class="cnt" id="c-all"></span></button>
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

<div class="footer">
  Fonte: Planejamento Estratégico Mensal — Afiliados Mercado Livre · Atualização automática a cada hora
</div>

<script>
const ITEMS = {items_json};

function dl(s){{
  if(!s)return 9999;
  const parts=s.split('/').map(Number);
  const[d,m,y]=[parts[0],parts[1],parts[2]];
  return Math.round((new Date(y,m-1,d)-new Date(new Date().toDateString()))/86400000);
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
  if(d===0)return'hoje';
  if(d<=3)return'breve';
  return'ok';
}}

let sq='';
function matches(c){{
  if(sq){{const q=sq.toLowerCase();return c.categoria.toLowerCase().includes(q);}}
  return true;
}}

function renderCard(c){{
  c.categoria = c.categoria.replace('CPG (Bens de Consumo)', 'Bens de Consumo');
  const exp=expInfo(c.data_fim),cls=cardCls(c);
  const expTag=cls==='hoje'||cls==='breve'?`<span class="pill-tag pill-${{cls}}">${{exp.l}}</span>`:'';
  const btnHTML=c.url
    ?`<a class="ver-btn" href="${{c.url}}" target="_blank" rel="noopener">Ver lista</a>`
    :`<span class="ver-btn no-url">Sem link</span>`;
  return`<div class="card ${{cls}}">
  <div class="card-badge">
    <div class="badge-icon">💰</div>
    <div class="badge-lbl">Ganho Extra</div>
  </div>
  <div class="card-body">
    <div class="card-top">
      <span class="cat-name">${{c.categoria}}</span>
      ${{expTag}}
    </div>
    <div class="card-nums">
      <div class="num-item">
        <span class="num-label">Ganho máximo</span>
        <span class="num-val green">${{c.ganho_max || '—'}}</span>
      </div>
      <div class="num-item">
        <span class="num-label">Período</span>
        <span class="num-val purple">${{c.data_inicio}} → ${{c.data_fim}}</span>
      </div>
      <div class="num-item">
        <span class="num-label">Validade</span>
        <span class="expiry-pill ${{exp.cls}}">${{exp.l}}</span>
      </div>
    </div>
  </div>
  <div class="card-action">${{btnHTML}}</div>
</div>`;
}}

function counts(){{
  document.getElementById('c-all').textContent=ITEMS.length;
  const maxG=ITEMS.length?ITEMS.reduce((a,b)=>a.ganho_max>b.ganho_max?a:b).ganho_max:'—';
  const hoje=ITEMS.filter(c=>dl(c.data_fim)===0).length;
  document.getElementById('hero-stats').innerHTML=`
    <div class="hero-stat"><div class="hero-stat-n">${{ITEMS.length}}</div><div class="hero-stat-l">Listas ativas</div></div>
    <div class="hero-stat"><div class="hero-stat-n" style="color:var(--yellow)">${{maxG}}</div><div class="hero-stat-l">Maior ganho</div></div>
    ${{hoje?`<div class="hero-stat"><div class="hero-stat-n" style="color:var(--red)">${{hoje}}</div><div class="hero-stat-l">Expiram hoje</div></div>`:''}}
  `;
}}

function render(){{
  const v=ITEMS.filter(matches);
  document.getElementById('list').innerHTML=v.map(renderCard).join('');
  document.getElementById('empty').classList.toggle('show',v.length===0);
}}

document.getElementById('search').addEventListener('input',e=>{{sq=e.target.value.trim();render()}});
counts();render();
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
    debug_rows(rows)
    items = parse_rows(rows)
    print(f"   {len(items)} itens ativos")
    generate_html(items)
