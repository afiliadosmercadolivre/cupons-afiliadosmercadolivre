"""
generate.py — v3 (Brand ML)
"""

import json, os, re
from datetime import datetime, date
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1RM03Bn9rVpZ8KND_Y57YqK675z7peYnIekYvz2XnUMw"
SHEET_NAME = "Julho/26"
DATA_START_ROW = 6
OUTPUT_FILE = "index.html"

COL = {
    "acao": 0, "hora_inicio": 1, "dia_inicio": 2, "dia_fim": 3,
    "valor_desconto": 4, "min_compra": 5, "desconto_max": 6,
    "status_cupom": 7, "nome_cupom": 8, "id_cupom": 9,
    "texto_legal": 10, "tipo_cupom": 11, "containers": 12,
    "status_budget": 17,
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
    range_name = f"'{SHEET_NAME}'!A{DATA_START_ROW}:R5000"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    return result.get("values", [])

def safe_get(row, idx, default=""):
    try:
        return row[idx].strip()
    except (IndexError, AttributeError):
        return default

def parse_date(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None

def days_left(s):
    d = parse_date(s)
    return (d - date.today()).days if d else 9999

def is_active(s):
    return days_left(s) >= 0

def extract_container(url_raw):
    url = url_raw.strip().rstrip(".")
    m = re.search(r"_Container_([^\s/\\|]+)", url)
    return url, (m.group(1) if m else "")

def discount_num(val):
    try:
        return int(re.sub(r"[^\d]", "", val.split(",")[0]))
    except:
        return 0

def parse_coupons(rows):
    coupons = []
    for row in rows:
        acao = safe_get(row, COL["acao"])
        dia_inicio = safe_get(row, COL["dia_inicio"])
        dia_fim = safe_get(row, COL["dia_fim"])
        status_budget = safe_get(row, COL["status_budget"])
        if not acao or not dia_inicio or not dia_fim: continue
        if status_budget != "Tem verba": continue
        if not is_active(dia_fim): continue
        container_url, container_name = extract_container(safe_get(row, COL["containers"]))
        dl = days_left(dia_fim)
        dn = discount_num(safe_get(row, COL["valor_desconto"]))
        coupons.append({
            "nome": safe_get(row, COL["nome_cupom"]),
            "acao": acao,
            "dia_inicio": dia_inicio,
            "dia_fim": dia_fim,
            "valor_desconto": safe_get(row, COL["valor_desconto"]),
            "min_compra": safe_get(row, COL["min_compra"]),
            "desconto_max": safe_get(row, COL["desconto_max"]),
            "container_url": container_url,
            "container_name": container_name,
            "is_mar_aberto": container_url == "",
            "days_left": dl,
            "discount_num": dn,
        })
    coupons.sort(key=lambda c: (0 if c["is_mar_aberto"] else 1, c["days_left"], -c["discount_num"]))
    return coupons

def to_js_array(coupons):
    return json.dumps(coupons, ensure_ascii=False, indent=2)

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Cupons Afiliados — Mercado Livre</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --yellow: #FFE600;
      --yellow-dark: #E6CF00;
      --blue: #0A0080;
      --blue-mid: #1A0099;
      --white: #FFFFFF;
      --bg: #F7F7F7;
      --text: #1A1A1A;
      --muted: #666;
      --border: #E8E8E8;
      --green: #00A650;
      --red: #E8003C;
      --orange: #FF6000;
      --radius-pill: 50px;
      --radius-card: 12px;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Montserrat', Arial, sans-serif; background: var(--bg); color: var(--text); }}

    /* ── HEADER ── */
    .hdr {{ background: var(--yellow); padding: 0 24px; height: 64px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,.12); }}
    .hdr-logo {{ display: flex; align-items: center; gap: 12px; text-decoration: none; }}
    .hdr-pill {{ background: var(--blue); color: var(--yellow); font-size: 13px; font-weight: 900; padding: 6px 18px; border-radius: var(--radius-pill); letter-spacing: -.01em; white-space: nowrap; }}
    .hdr-sub {{ font-size: 12px; font-weight: 700; color: var(--blue); opacity: .65; text-transform: uppercase; letter-spacing: .06em; }}
    .hdr-ts {{ font-size: 12px; font-weight: 600; color: var(--blue); opacity: .6; }}

    /* ── HERO ── */
    .hero {{ background: var(--blue); padding: 36px 24px 32px; }}
    .hero-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap; }}
    .hero-left h1 {{ font-size: clamp(24px,3.5vw,40px); font-weight: 900; color: var(--white); line-height: 1.1; letter-spacing: -.02em; }}
    .hero-left h1 span {{ color: var(--yellow); }}
    .hero-left p {{ font-size: 14px; color: rgba(255,255,255,.6); margin-top: 8px; font-weight: 600; }}
    .hero-pills {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .hero-stat {{ background: rgba(255,255,255,.08); border: 1.5px solid rgba(255,230,0,.25); border-radius: var(--radius-pill); padding: 10px 20px; display: flex; flex-direction: column; align-items: center; gap: 2px; }}
    .hero-stat-n {{ font-size: 26px; font-weight: 900; color: var(--yellow); line-height: 1; }}
    .hero-stat-l {{ font-size: 10px; font-weight: 700; color: rgba(255,255,255,.5); text-transform: uppercase; letter-spacing: .08em; }}

    /* ── TOOLBAR ── */
    .toolbar {{ background: var(--white); border-bottom: 1px solid var(--border); padding: 12px 24px; position: sticky; top: 64px; z-index: 90; }}
    .toolbar-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .filter-btn {{ background: var(--white); border: 2px solid var(--border); color: var(--muted); font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 700; padding: 6px 16px; border-radius: var(--radius-pill); cursor: pointer; transition: all .15s; white-space: nowrap; }}
    .filter-btn:hover {{ border-color: var(--blue); color: var(--blue); }}
    .filter-btn.active {{ background: var(--blue); border-color: var(--blue); color: var(--yellow); }}
    .filter-btn .cnt {{ font-size: 11px; opacity: .75; margin-left: 4px; }}
    .search {{ margin-left: auto; padding: 8px 16px; border: 2px solid var(--border); border-radius: var(--radius-pill); font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 600; outline: none; width: 220px; transition: border-color .15s; }}
    .search:focus {{ border-color: var(--blue); }}

    /* ── LIST ── */
    .list-wrap {{ max-width: 1100px; margin: 24px auto; padding: 0 24px; display: flex; flex-direction: column; gap: 10px; }}

    /* ── CARD ── */
    .card {{ background: var(--white); border-radius: var(--radius-card); border: 1.5px solid var(--border); display: grid; grid-template-columns: 110px 1fr auto; overflow: hidden; transition: box-shadow .18s, transform .18s; }}
    .card:hover {{ box-shadow: 0 6px 24px rgba(0,0,0,.1); transform: translateY(-1px); }}

    /* accent stripe via left border */
    .card.site {{ border-left: 5px solid var(--green); }}
    .card.hoje {{ border-left: 5px solid var(--red); }}
    .card.breve {{ border-left: 5px solid var(--orange); }}

    /* badge */
    .card-badge {{ background: var(--blue); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0; padding: 0; }}
    .card.hoje .card-badge {{ background: var(--red); }}
    .card.site .card-badge {{ background: var(--green); }}
    .badge-n {{ font-size: 36px; font-weight: 900; color: var(--yellow); line-height: 1; font-family: 'Montserrat', sans-serif; }}
    .card.hoje .badge-n, .card.site .badge-n {{ color: var(--white); }}
    .badge-unit {{ font-size: 13px; font-weight: 800; color: rgba(255,230,0,.7); margin-top: -2px; }}
    .card.hoje .badge-unit, .card.site .badge-unit {{ color: rgba(255,255,255,.7); }}

    /* body */
    .card-body {{ padding: 16px 20px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
    .card-top {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .coupon-name {{ font-size: 20px; font-weight: 900; color: var(--text); letter-spacing: .01em; }}
    .pill-tag {{ font-size: 10px; font-weight: 800; padding: 3px 10px; border-radius: var(--radius-pill); text-transform: uppercase; letter-spacing: .06em; }}
    .pill-site {{ background: #E6F9EE; color: var(--green); }}
    .pill-cat {{ background: #EFEFFF; color: var(--blue); }}
    .pill-hot {{ background: #FFF0E6; color: var(--orange); }}
    .pill-expira {{ background: #FFE6EC; color: var(--red); }}

    .card-nums {{ display: flex; gap: 24px; flex-wrap: wrap; }}
    .num-item {{ display: flex; flex-direction: column; gap: 1px; }}
    .num-label {{ font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); }}
    .num-val {{ font-size: 15px; font-weight: 800; color: var(--text); }}
    .num-val.green {{ color: var(--green); }}

    .card-footer {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .date-txt {{ font-size: 12px; font-weight: 600; color: var(--muted); }}
    .expiry-pill {{ font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: var(--radius-pill); }}
    .expiry-pill.ok {{ background: #E6F9EE; color: var(--green); }}
    .expiry-pill.hoje {{ background: #FFE6EC; color: var(--red); }}
    .expiry-pill.breve {{ background: #FFF0E6; color: var(--orange); }}

    .container-row {{ display: flex; align-items: center; gap: 6px; }}
    .container-icon {{ font-size: 12px; }}
    .container-lbl {{ font-size: 11px; font-weight: 700; color: var(--muted); flex-shrink: 0; }}
    .container-link {{ font-size: 12px; font-weight: 700; color: var(--blue); text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px; }}
    .container-link:hover {{ text-decoration: underline; }}
    .site-pill {{ font-size: 11px; font-weight: 800; background: #E6F9EE; color: var(--green); padding: 3px 10px; border-radius: var(--radius-pill); }}

    /* action */
    .card-action {{ padding: 20px 16px; display: flex; align-items: center; justify-content: center; border-left: 1px solid var(--border); min-width: 120px; }}
    .copy-btn {{ background: var(--yellow); border: none; border-radius: var(--radius-pill); padding: 11px 20px; font-family: 'Montserrat', sans-serif; font-size: 13px; font-weight: 900; color: var(--blue); cursor: pointer; transition: background .12s, transform .1s; width: 100%; white-space: nowrap; }}
    .copy-btn:hover {{ background: var(--yellow-dark); transform: scale(1.03); }}
    .copy-btn.copied {{ background: var(--green); color: white; }}

    /* empty */
    .empty {{ text-align: center; padding: 64px 24px; color: var(--muted); font-size: 15px; font-weight: 700; background: var(--white); border-radius: var(--radius-card); border: 1.5px solid var(--border); display: none; }}
    .empty.show {{ display: block; }}

    /* footer */
    .footer {{ text-align: center; padding: 32px 24px; font-size: 12px; font-weight: 600; color: var(--muted); border-top: 1px solid var(--border); margin-top: 16px; }}

    @media (max-width: 640px) {{
      .card {{ grid-template-columns: 80px 1fr; }}
      .card-action {{ display: none; }}
      .search {{ width: 130px; }}
      .badge-n {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>

<header class="hdr">
  <a class="hdr-logo" href="#">
    <div class="hdr-pill">Cupons Afiliados</div>
    <span class="hdr-sub">Mercado Livre</span>
  </a>
  <span class="hdr-ts">Atualizado em {generated_at}</span>
</header>

<div class="hero">
  <div class="hero-inner">
    <div class="hero-left">
      <h1>Cupons disponíveis<br>— {month_label}</h1>
      <p>Atualização automática a cada hora</p>
    </div>
    <div class="hero-pills" id="hero-stats"></div>
  </div>
</div>

<div class="toolbar">
  <div class="toolbar-inner">
    <button class="filter-btn active" data-f="all">Todos <span class="cnt" id="c-all"></span></button>
    <button class="filter-btn" data-f="mar">🌐 Todo o site <span class="cnt" id="c-mar"></span></button>
    <button class="filter-btn" data-f="Moda">Moda <span class="cnt" id="c-fas"></span></button>
    <button class="filter-btn" data-f="Casa">Casa e Decoração <span class="cnt" id="c-furn"></span></button>
    <button class="filter-btn" data-f="Sellers">Seleção Vendedores <span class="cnt" id="c-sel"></span></button>
    <button class="filter-btn" data-f="Outros">Outros <span class="cnt" id="c-out"></span></button>
    <input class="search" id="search" type="search" placeholder="🔍  Buscar cupom…"/>
  </div>
</div>

<div class="list-wrap">
  <div id="list"></div>
  <div class="empty" id="empty">Nenhum cupom encontrado para esse filtro.</div>
</div>

<div class="disclaimer" style="max-width:1100px;margin:0 auto 0;padding:0 24px 16px;"><p style="font-size:12px;font-weight:600;color:#888;background:#fff;border:1.5px solid #E8E8E8;border-radius:8px;padding:12px 16px;line-height:1.6;">⚠️ <strong>Atenção:</strong> Os cupons listados têm verba confirmada no momento da última atualização, mas podem ser encerrados antecipadamente sem aviso prévio. Sempre verifique a validade antes de divulgar.</p></div>
  <div class="footer">
  Fonte: Controle Cupons {month_label} · Afiliados Mercado Livre
</div>

<script>
const COUPONS = {coupons_json};

function dl(s){{
  const[d,m,y]=s.split('/').map(Number);
  return Math.round((new Date(y,m-1,d)-new Date(new Date().toDateString()))/86400000);
}}
function expInfo(c){{
  const d=dl(c.dia_fim);
  if(d<0)return{{l:'Expirado',cls:''}};
  if(d===0)return{{l:'Expira hoje',cls:'hoje'}};
  if(d<=3)return{{l:d+'d restantes',cls:'breve'}};
  return{{l:'Válido até '+c.dia_fim,cls:'ok'}};
}}
function cat(a){{
  if(/fashion/i.test(a))return'Moda';
  if(/furnishing|houseware|furniture|living|dining/i.test(a))return'Casa e Decoração';
  if(/sellers/i.test(a))return'Seleção Vendedores';
  return'Outros';
}}
function cardCls(c){{
  if(c.is_mar_aberto)return'site';
  const d=dl(c.dia_fim);
  if(d===0)return'hoje';
  if(d<=3)return'breve';
  return'';
}}
let af='all', sq='';
function matches(c){{
  if(af==='mar'&&!c.is_mar_aberto)return false;
  if(af==='Moda'&&cat(c.acao)!=='Moda')return false;
  if(af==='Casa e Decoração'&&cat(c.acao)!=='Casa e Decoração')return false;
  if(af==='Seleção Vendedores'&&cat(c.acao)!=='Seleção Vendedores')return false;
  if(af==='Outros'&&cat(c.acao)!=='Outros')return false;
  if(sq){{const q=sq.toLowerCase();return c.nome.toLowerCase().includes(q)||(c.container_name||'').toLowerCase().includes(q);}}
  return true;
}}
function renderCard(c){{
  const exp=expInfo(c),cls=cardCls(c);
  const catLabel=c.is_mar_aberto?'Todo o site':cat(c.acao);
  const catCls=c.is_mar_aberto?'pill-site':'pill-cat';
  const container=c.container_url
    ?`<a class="container-link" href="${{c.container_url}}" target="_blank" rel="noopener">/_Container_${{c.container_name}}</a>`
    :`<span class="site-pill">✓ Todo o site</span>`;
  const hotTag=c.discount_num>=20?'<span class="pill-tag pill-hot">🔥 Destaque</span>':'';
  const expTag=cls==='hoje'||cls==='breve'?`<span class="pill-tag pill-expira">${{exp.l}}</span>`:'';
  return`<div class="card ${{cls}}">
  <div class="card-badge">
    <div class="badge-n">${{c.discount_num}}</div>
    <div class="badge-unit">% OFF</div>
  </div>
  <div class="card-body">
    <div class="card-top">
      <span class="coupon-name">${{c.nome}}</span>
      <span class="pill-tag ${{catCls}}">${{catLabel}}</span>
      ${{hotTag}}${{expTag}}
    </div>
    <div class="card-nums">
      <div class="num-item"><span class="num-label">Desconto</span><span class="num-val green">${{c.valor_desconto}}</span></div>
      <div class="num-item"><span class="num-label">Compra mínima</span><span class="num-val">R$${{c.min_compra}}</span></div>
      <div class="num-item"><span class="num-label">Desconto máx.</span><span class="num-val">R$${{c.desconto_max}}</span></div>
      <div class="num-item"><span class="num-label">Período</span><span class="num-val">${{c.dia_inicio}} → ${{c.dia_fim}}</span></div>
    </div>
    <div class="container-row">
      <span class="container-icon">📦</span>
      <span class="container-lbl">Lista:</span>
      ${{container}}
    </div>
  </div>
  <div class="card-action">
    <button class="copy-btn" onclick="copy(this,'${{c.nome}}')">Copiar código</button>
  </div>
</div>`;
}}
function counts(){{
  const n=COUPONS;
  document.getElementById('c-all').textContent=n.length;
  document.getElementById('c-mar').textContent=n.filter(c=>c.is_mar_aberto).length;
  document.getElementById('c-fas').textContent=n.filter(c=>cat(c.acao)==='Moda').length;
  document.getElementById('c-furn').textContent=n.filter(c=>cat(c.acao)==='Casa e Decoração').length;
  document.getElementById('c-sel').textContent=n.filter(c=>cat(c.acao)==='Seleção Vendedores').length;
  document.getElementById('c-out').textContent=n.filter(c=>cat(c.acao)==='Outros').length;
  const maxD=n.length?Math.max(...n.map(c=>c.discount_num)):0;
  const hoje=n.filter(c=>dl(c.dia_fim)===0).length;
  document.getElementById('hero-stats').innerHTML=`
    <div class="hero-stat"><div class="hero-stat-n">${{n.length}}</div><div class="hero-stat-l">Cupons ativos</div></div>
    <div class="hero-stat"><div class="hero-stat-n">${{n.filter(c=>c.is_mar_aberto).length}}</div><div class="hero-stat-l">Todo o site</div></div>
    <div class="hero-stat"><div class="hero-stat-n">${{maxD}}%</div><div class="hero-stat-l">Maior desconto</div></div>
    ${{hoje?`<div class="hero-stat"><div class="hero-stat-n" style="color:var(--red)">${{hoje}}</div><div class="hero-stat-l">Expiram hoje</div></div>`:''}}
  `;
}}
function render(){{
  const v=COUPONS.filter(matches);
  document.getElementById('list').innerHTML=v.map(renderCard).join('');
  document.getElementById('empty').classList.toggle('show',v.length===0);
}}
function copy(btn,code){{
  navigator.clipboard.writeText(code).catch(()=>{{
    const e=document.createElement('textarea');e.value=code;
    document.body.appendChild(e);e.select();document.execCommand('copy');e.remove();
  }});
  btn.textContent='✓ Copiado!';btn.classList.add('copied');
  setTimeout(()=>{{btn.textContent='Copiar código';btn.classList.remove('copied')}},2000);
}}
document.querySelectorAll('.filter-btn').forEach(b=>{{
  b.addEventListener('click',()=>{{
    document.querySelectorAll('.filter-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');af=b.dataset.f;render();
  }});
}});
document.getElementById('search').addEventListener('input',e=>{{sq=e.target.value.trim();render()}});
counts();render();
</script>
</body>
</html>
"""

def generate_html(coupons):
    now = datetime.now()
    months = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
              "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    html = HTML_TEMPLATE.format(
        generated_at=now.strftime("%d/%m/%Y %H:%M"),
        month_label=f"{months[now.month]} {now.year}",
        coupons_json=to_js_array(coupons),
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {OUTPUT_FILE} gerado com {len(coupons)} cupons")

if __name__ == "__main__":
    print("🔐 Autenticando na Google Sheets API…")
    service = get_service()
    print("📊 Buscando dados da planilha…")
    rows = fetch_rows(service)
    print(f"   {len(rows)} linhas lidas")
    coupons = parse_coupons(rows)
    print(f"   {len(coupons)} cupons com 'Tem verba' no mês atual")
    generate_html(coupons)
