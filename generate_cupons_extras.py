"""
generate_cupons_extras.py — Cupons Extras Afiliados ML
"""

import json, os, re
from datetime import datetime, date, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1ipuukzdhcKtTgqrK5MowmRXculVbYnLBSy1ULQEOZjY"
SHEET_NAME     = "Cupons"
DATA_START_ROW = 3
OUTPUT_FILE    = "cupons-extras.html"

# Colunas (0-based a partir de A)
COL = {
    "vertical":       0,   # A
    "categoria":      1,   # B
    "data_inicial":   2,   # C
    "data_final":     3,   # D
    "horario_inicio": 4,   # E
    "status_cupom":   5,   # F (não publicar)
    "pct_consumo":    6,   # G (não publicar)
    "data_fim_valid": 7,   # H (não publicar - sobrepõe D se preenchida)
    "prioridade":     8,   # I (não publicar)
    "tipo_cupom":     9,   # J
    "id_cupom":       10,  # K
    "nome_cupom":     11,  # L
    "mecanica":       12,  # M
    "desconto_cupom": 13,  # N
    "asp_minimo":     14,  # O
    "desconto_max":   15,  # P
    "url":            16,  # Q
    "ponto_focal":    17,  # R (não publicar)
    "obs":            18,  # S
}

def get_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("Secret GOOGLE_SERVICE_ACCOUNT_JSON não encontrado.")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    return build("sheets", "v4", credentials=creds)

def fetch_rows(service):
    range_name = f"'{SHEET_NAME}'!A{DATA_START_ROW}:S5000"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption="FORMATTED_VALUE"
    ).execute()
    return result.get("values", [])

def today_brt():
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3))).date()

def safe_get(row, idx, default=""):
    try:
        v = row[idx]
        return str(v).strip() if v is not None else default
    except (IndexError, AttributeError):
        return default

def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    parts = s.split('/')
    try:
        if len(parts) == 3:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000
            return date(y, m, d)
        elif len(parts) == 2:
            # Sem ano — assume ano atual (se já passou, fica no passado = expirado)
            d, m = int(parts[0]), int(parts[1])
            t = today_brt()
            return date(t.year, m, d)
    except (ValueError, IndexError):
        pass
    return None

def days_left(s):
    d = parse_date(s)
    if d is None:
        return 9999
    return (d - today_brt()).days

def fmt_date(s):
    d = parse_date(s)
    return d.strftime("%d/%m/%Y") if d else str(s)

def discount_num(val):
    try:
        return int(re.sub(r"[^\d]", "", val.split(",")[0]))
    except:
        return 0

def is_reais(val):
    return "R$" in val or "r$" in val.lower()

def parse_rows(rows):
    items = []
    for row in rows:
        vertical      = safe_get(row, COL["vertical"])
        categoria     = safe_get(row, COL["categoria"])
        data_inicial  = safe_get(row, COL["data_inicial"])
        data_final    = safe_get(row, COL["data_final"])
        horario       = safe_get(row, COL["horario_inicio"])
        status_cupom  = safe_get(row, COL["status_cupom"])
        data_fim_val  = safe_get(row, COL["data_fim_valid"])
        tipo_cupom    = safe_get(row, COL["tipo_cupom"])
        id_cupom      = safe_get(row, COL["id_cupom"])
        nome_cupom    = safe_get(row, COL["nome_cupom"])
        mecanica      = safe_get(row, COL["mecanica"])
        desconto      = safe_get(row, COL["desconto_cupom"])
        asp_minimo    = safe_get(row, COL["asp_minimo"])
        desconto_max  = safe_get(row, COL["desconto_max"])
        url           = safe_get(row, COL["url"])
        obs           = safe_get(row, COL["obs"])

        if not categoria and not vertical:
            continue

        print(f"   DEBUG: vertical='{vertical}' categoria='{categoria}' status_cupom={status_cupom!r} data_final='{data_final}'")

        # Status precisa ser "Active"
        if status_cupom.strip().lower() != "active":
            continue

        # Coluna H sobrepõe D se preenchida
        data_final_efetiva = data_fim_val if data_fim_val else data_final

        dl = days_left(data_final_efetiva)
        if dl < 0:
            continue

        dn = discount_num(desconto)
        eh_reais = is_reais(desconto)

        items.append({
            "vertical":       vertical,
            "categoria":      categoria,
            "data_inicial":   fmt_date(data_inicial),
            "data_final":     fmt_date(data_final_efetiva),
            "horario_inicio": horario,
            "tipo_cupom":     tipo_cupom,
            "id_cupom":       id_cupom,
            "nome_cupom":     nome_cupom,
            "mecanica":       mecanica,
            "desconto":       desconto,
            "discount_num":   dn,
            "is_reais":       eh_reais,
            "asp_minimo":     asp_minimo,
            "desconto_max":   desconto_max,
            "url":            url,
            "obs":            obs,
            "days_left":      dl,
        })

    items.sort(key=lambda x: (x["days_left"], -x["discount_num"]))
    return items

def to_js(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Cupons Extras — Afiliados Mercado Livre</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --yellow:#FFE600;--yellow-dark:#E6CF00;--blue:#0A0080;
      --white:#FFFFFF;--bg:#F7F7F7;--text:#1A1A1A;--muted:#666;
      --border:#E8E8E8;--green:#00A650;--red:#E8003C;
      --orange:#FF6000;--teal:#0891B2;--radius-pill:50px;--radius-card:12px;
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
    .filter-btn{{background:var(--white);border:2px solid var(--border);color:var(--muted);font-family:'Montserrat',sans-serif;font-size:13px;font-weight:700;padding:6px 16px;border-radius:var(--radius-pill);cursor:pointer;transition:all .15s;white-space:nowrap}}
    .filter-btn:hover{{border-color:var(--blue);color:var(--blue)}}
    .filter-btn.active{{background:var(--blue);border-color:var(--blue);color:var(--yellow)}}
    .filter-btn .cnt{{font-size:11px;opacity:.75;margin-left:4px}}
    .search{{margin-left:auto;padding:8px 16px;border:2px solid var(--border);border-radius:var(--radius-pill);font-family:'Montserrat',sans-serif;font-size:13px;font-weight:600;outline:none;width:220px;transition:border-color .15s}}
    .search:focus{{border-color:var(--blue)}}
    .count-lbl{{font-size:13px;font-weight:700;color:var(--muted)}}
    .list-wrap{{max-width:1100px;margin:24px auto;padding:0 24px;display:flex;flex-direction:column;gap:10px}}
    .card{{background:var(--white);border-radius:var(--radius-card);border:1.5px solid var(--border);display:grid;grid-template-columns:110px 1fr auto;overflow:hidden;transition:box-shadow .18s,transform .18s}}
    .card:hover{{box-shadow:0 6px 24px rgba(0,0,0,.1);transform:translateY(-1px)}}
    .card.hoje{{border-left:5px solid var(--red)}}
    .card.breve{{border-left:5px solid var(--orange)}}
    .card.ok{{border-left:5px solid var(--teal)}}
    .card-badge{{background:var(--teal);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0;padding:0}}
    .card.hoje .card-badge{{background:var(--red)}}
    .badge-n{{font-size:32px;font-weight:900;color:var(--white);line-height:1;font-family:'Montserrat',sans-serif}}
    .badge-unit{{font-size:11px;font-weight:800;color:rgba(255,255,255,.75);margin-top:2px}}
    .card-body{{padding:16px 20px;display:flex;flex-direction:column;gap:10px;min-width:0}}
    .card-top{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
    .coupon-name{{font-size:19px;font-weight:900;color:var(--text);letter-spacing:.01em}}
    .pill-tag{{font-size:10px;font-weight:800;padding:3px 10px;border-radius:var(--radius-pill);text-transform:uppercase;letter-spacing:.06em}}
    .pill-cat{{background:#E0F7FA;color:var(--teal)}}
    .pill-vert{{background:#EFEFFF;color:var(--blue)}}
    .pill-expira{{background:#FFE6EC;color:var(--red)}}
    .pill-breve{{background:#FFF0E6;color:var(--orange)}}
    .card-nums{{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-end}}
    .num-item{{display:flex;flex-direction:column;gap:1px}}
    .num-label{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
    .num-val{{font-size:14px;font-weight:800;color:var(--text)}}
    .num-val.green{{color:var(--green);font-size:18px}}
    .card-mecanica{{font-size:12px;color:var(--muted);font-weight:600;line-height:1.5;background:#F7F7F7;padding:8px 12px;border-radius:8px}}
    .card-mecanica strong{{color:var(--text)}}
    .card-obs{{font-size:11px;color:var(--muted);font-style:italic}}
    .expiry-pill{{font-size:11px;font-weight:800;padding:3px 10px;border-radius:var(--radius-pill)}}
    .expiry-pill.ok{{background:#E0F7FA;color:var(--teal)}}
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
    <div class="hdr-pill">Cupons Extras</div>
    <span class="hdr-sub">Mercado Livre</span>
  </a>
  <nav class="hdr-nav">
    <a class="hdr-link" href="index.html">Cupons</a>
    <a class="hdr-link" href="ganhos-extras.html">Ganhos Extras</a>
    <a class="hdr-link active" href="cupons-extras.html">Cupons Extras</a>
  </nav>
  <span class="hdr-ts">Atualizado em {generated_at}</span>
</header>
<div class="hero">
  <div class="hero-inner">
    <div class="hero-left">
      <h1>Cupons <span>extras</span> disponíveis</h1>
      <p>Cupons com regras e mecânicas específicas para afiliados</p>
    </div>
    <div class="hero-pills" id="hero-stats"></div>
  </div>
</div>
<div class="toolbar">
  <div class="toolbar-inner">
    <span class="count-lbl"><strong id="count-visible">0</strong> cupons ativos</span>
    <input class="search" id="search" type="search" placeholder="🔍  Buscar cupom…"/>
  </div>
</div>
<div class="list-wrap">
  <div id="list"></div>
  <div class="empty" id="empty">Nenhum item encontrado.</div>
</div>
<div class="disclaimer">
  <p>⚠️ <strong>Atenção:</strong> Os cupons listados podem ser encerrados antecipadamente sem aviso prévio. Sempre verifique a validade antes de divulgar.</p>
</div>
<div class="footer">Fonte: Planejamento Estratégico Mensal — Afiliados Mercado Livre · Atualização automática a cada hora</div>
<script>
const ITEMS = {items_json};
function dl(s){{
  if(!s)return 9999;
  const p=s.split('/').map(Number);
  return Math.round((new Date(p[2],p[1]-1,p[0])-new Date(new Date().toDateString()))/86400000);
}}
function expInfo(s){{
  const d=dl(s);
  if(d<0) return{{l:'Expirado',cls:'exp'}};
  if(d===0)return{{l:'Expira hoje',cls:'hoje'}};
  if(d<=3) return{{l:d+'d restantes',cls:'breve'}};
  return        {{l:'Válido até '+s,cls:'ok'}};
}}
function cardCls(c){{const d=dl(c.data_final);if(d===0)return'hoje';if(d<=3)return'breve';return'ok';}}
let sq='';
function matches(c){{
  if(sq){{
    const q=sq.toLowerCase();
    return (c.nome_cupom||'').toLowerCase().includes(q)
        || (c.categoria||'').toLowerCase().includes(q)
        || (c.vertical||'').toLowerCase().includes(q)
        || (c.id_cupom||'').toLowerCase().includes(q);
  }}
  return true;
}}
function renderCard(c){{
  const exp=expInfo(c.data_final),cls=cardCls(c);
  const expTag=cls==='hoje'||cls==='breve'?`<span class="pill-tag pill-expira">${{exp.l}}</span>`:'';
  const btnHTML=c.url?`<a class="ver-btn" href="${{c.url}}" target="_blank" rel="noopener">Ver cupom</a>`:`<span class="ver-btn no-url">Sem link</span>`;
  const badgeUnit=c.is_reais?'R$ OFF':'% OFF';
  const nome=c.nome_cupom||c.id_cupom||'Cupom';
  const mecanicaHTML=c.mecanica?`<div class="card-mecanica"><strong>Mecânica:</strong> ${{c.mecanica}}</div>`:'';
  const obsHTML=c.obs?`<div class="card-obs">${{c.obs}}</div>`:'';
  return`<div class="card ${{cls}}">
  <div class="card-badge">
    <div class="badge-n">${{c.discount_num}}</div>
    <div class="badge-unit">${{badgeUnit}}</div>
  </div>
  <div class="card-body">
    <div class="card-top">
      <span class="coupon-name">${{nome}}</span>
      ${{c.categoria?`<span class="pill-tag pill-cat">${{c.categoria}}</span>`:''}}
      ${{c.vertical?`<span class="pill-tag pill-vert">${{c.vertical}}</span>`:''}}
      ${{expTag}}
    </div>
    <div class="card-nums">
      <div class="num-item"><span class="num-label">Desconto</span><span class="num-val green">${{c.desconto||'—'}}</span></div>
      <div class="num-item"><span class="num-label">ASP Mínimo</span><span class="num-val">${{c.asp_minimo||'—'}}</span></div>
      <div class="num-item"><span class="num-label">Desconto Máx.</span><span class="num-val">${{c.desconto_max||'—'}}</span></div>
      <div class="num-item"><span class="num-label">Tipo</span><span class="num-val">${{c.tipo_cupom||'—'}}</span></div>
      <div class="num-item"><span class="num-label">Período</span><span class="num-val">${{c.data_inicial}} → ${{c.data_final}}</span></div>
      <div class="num-item"><span class="num-label">Validade</span><span class="expiry-pill ${{exp.cls}}">${{exp.l}}</span></div>
    </div>
    ${{mecanicaHTML}}
    ${{obsHTML}}
  </div>
  <div class="card-action">${{btnHTML}}</div>
</div>`;
}}
function render(){{
  const v=ITEMS.filter(matches);
  document.getElementById('list').innerHTML=v.map(renderCard).join('');
  document.getElementById('count-visible').textContent=v.length;
  document.getElementById('empty').classList.toggle('show',v.length===0);
  const hoje=ITEMS.filter(c=>dl(c.data_final)===0).length;
  document.getElementById('hero-stats').innerHTML=`
    <div class="hero-stat"><div class="hero-stat-n">${{ITEMS.length}}</div><div class="hero-stat-l">Cupons ativos</div></div>
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
    print("📊 Buscando Cupons Extras…")
    rows = fetch_rows(service)
    print(f"   {len(rows)} linhas lidas")
    items = parse_rows(rows)
    print(f"   {len(items)} itens ativos")
    generate_html(items)
