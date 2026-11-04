"""Gera a página diária de ofertas Last Minute para Afiliados Mercado Livre."""

import json
import os
import re
from datetime import date, datetime, timezone, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1ipuukzdhcKtTgqrK5MowmRXculVbYnLBSy1ULQEOZjY"
SHEET_NAME = "Last Minute"
DATA_START_ROW = 2
OUTPUT_FILE = "last-minute.html"
BRT = timezone(timedelta(hours=-3))
SHEET_ERROR_VALUES = {"#N/A", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#NULL!", "#ERROR!", "#SPILL!", "#CALC!"}

# Colunas (0-based a partir de A)
COL = {
    "mes": 0,
    "vertical": 1,
    "data_oferta": 2,
    "produto": 4,
    "url": 5,
    "preco_de": 6,
    "preco_por": 7,
    "cupom": 8,
    "tipo_cupom": 9,
    "desconto": 10,
    "codigo": 11,
    "informacoes_extras": 12,
}


def get_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("Secret GOOGLE_SERVICE_ACCOUNT_JSON não encontrado.")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    return build("sheets", "v4", credentials=creds)


def fetch_rows(service):
    range_name = f"'{SHEET_NAME}'!A{DATA_START_ROW}:M"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    return result.get("values", [])


def today_brt():
    return datetime.now(timezone.utc).astimezone(BRT).date()


def safe_get(row, idx, default=""):
    try:
        value = row[idx]
        if value is None:
            return default
        value = str(value).strip()
        return default if value.upper() in SHEET_ERROR_VALUES else value
    except (IndexError, AttributeError):
        return default


def is_valid_offer_url(value):
    match = re.match(r"^https?://[^/\s]+(?:/[^\s]*)?$", str(value or "").strip(), re.IGNORECASE)
    return bool(match)


def parse_offer_date(value, today=None):
    """Interpreta datas exibidas como DD/MM[/AAAA] ou AAAA-MM-DD."""
    if not value:
        return None
    today = today or today_brt()
    raw = str(value).strip()
    match = re.search(r"(\d{1,4})[/-](\d{1,2})(?:[/-](\d{2,4}))?", raw)
    if not match:
        return None
    first, second, third = match.groups()
    try:
        if len(first) == 4:  # ISO: AAAA-MM-DD
            year, month, day = int(first), int(second), int(third)
        else:  # Brasil: DD/MM[/AAAA]
            day, month = int(first), int(second)
            year = int(third) if third else today.year
            if year < 100:
                year += 2000
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def parse_rows(rows, today=None):
    """Publica somente ofertas cuja Data Oferta coincide exatamente com hoje."""
    today = today or today_brt()
    items = []
    unparsed_dates = 0
    other_dates = 0
    today_date_matches = 0
    incomplete_offers = 0
    invalid_urls = 0
    date_samples = []

    for offset, row in enumerate(rows):
        raw_date = safe_get(row, COL["data_oferta"])
        offer_date = parse_offer_date(raw_date, today)
        if len(date_samples) < 8:
            date_samples.append({
                "sheet_row": DATA_START_ROW + offset,
                "date_raw": raw_date,
                "date_parsed": offer_date.isoformat() if offer_date else None,
                "columns_read": len(row),
            })

        if offer_date != today:
            if offer_date is None:
                unparsed_dates += 1
            else:
                other_dates += 1
            continue

        today_date_matches += 1
        vertical = safe_get(row, COL["vertical"])
        product = safe_get(row, COL["produto"])
        url = safe_get(row, COL["url"])
        price_from = safe_get(row, COL["preco_de"])
        price_to = safe_get(row, COL["preco_por"])
        if not all((vertical, product, url, price_from, price_to)):
            incomplete_offers += 1
            continue
        if not is_valid_offer_url(url):
            invalid_urls += 1
            continue

        items.append({
            "vertical": vertical,
            "data_oferta": offer_date.strftime("%d/%m/%Y"),
            "produto": product,
            "url": url,
            "preco_de": price_from,
            "preco_por": price_to,
            "cupom": safe_get(row, COL["cupom"]),
            "tipo_cupom": safe_get(row, COL["tipo_cupom"]),
            "desconto": safe_get(row, COL["desconto"]),
            "codigo": safe_get(row, COL["codigo"]),
            "informacoes_extras": safe_get(row, COL["informacoes_extras"]),
        })

    items.sort(key=lambda item: (item["vertical"].casefold(), item["produto"].casefold()))
    print(
        f"[Last Minute] hoje={today.isoformat()} linhas_lidas={len(rows)} "
        f"datas_de_hoje={today_date_matches} datas_invalidas={unparsed_dates} "
        f"outras_datas={other_dates} ofertas_incompletas={incomplete_offers} "
        f"urls_invalidas={invalid_urls} itens_publicados={len(items)}"
    )
    if not items:
        print(f"[Last Minute] amostras_data={json.dumps(date_samples, ensure_ascii=False)}")
    return items

HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta name="theme-color" content="#050505"/>
  <title>Ofertas de hoje — Afiliados Mercado Livre</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --yellow:#FFE600;--yellow-dark:#D6C200;--black:#050505;--panel:#151515;
      --text:#F5F5F5;--muted:#B7B7B7;--border:#333;--green:#00C853;
      --red:#FF375F;--radius:14px;
    }}
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Montserrat',Arial,sans-serif;background:var(--black);color:var(--text);min-height:100vh}}
    .hdr{{background:#050505;border-bottom:1px solid #262626;padding:0 24px;min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:18px;position:sticky;top:0;z-index:10}}
    .brand{{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--text)}}
    .brand-pill{{background:var(--yellow);color:#050505;font-weight:900;font-size:13px;padding:7px 16px;border-radius:50px;white-space:nowrap}}
    .brand-sub,.updated{{font-size:11px;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.08em}}
    .nav{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
    .nav a{{color:#ccc;text-decoration:none;font-size:11px;font-weight:700;padding:7px 10px;border:1px solid #3a3a3a;border-radius:50px}}
    .nav a:hover,.nav a.active{{background:var(--yellow);border-color:var(--yellow);color:#050505}}
    .hero{{background:#0b0b0b;border-bottom:1px solid #202020;padding:38px 24px 32px}}
    .hero-inner{{max-width:1120px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}}
    .eyebrow{{color:var(--yellow);font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.16em;margin-bottom:10px}}
    h1{{font-size:clamp(30px,5vw,48px);line-height:1.02;font-weight:900;letter-spacing:-.04em}}
    h1 span{{color:var(--yellow)}}
    .hero p{{margin-top:10px;color:#aaa;font-size:14px;font-weight:600}}
    .today{{border:1px solid #4a4300;background:#141200;color:var(--yellow);padding:14px 20px;border-radius:var(--radius);font-size:13px;font-weight:900}}
    .toolbar{{background:#101010;border-bottom:1px solid #292929;padding:14px 24px;position:sticky;top:64px;z-index:9}}
    .toolbar-inner{{max-width:1120px;margin:auto;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
    .count{{font-size:13px;color:#bbb;font-weight:700}}
    select,input{{background:#191919;border:1px solid #3a3a3a;color:var(--text);border-radius:50px;padding:10px 15px;font:600 13px 'Montserrat',sans-serif;outline:none}}
    select:focus,input:focus{{border-color:var(--yellow)}}
    select{{min-width:210px}}
    input{{margin-left:auto;width:min(320px,100%)}}
    input::placeholder{{color:#888}}
    .list{{max-width:1120px;margin:24px auto;padding:0 24px 28px;display:flex;flex-direction:column;gap:14px}}
    .category-section{{background:#101010;border:1px solid #303030;border-radius:16px;overflow:hidden}}
    .category-summary{{display:flex;align-items:center;justify-content:space-between;gap:12px;list-style:none;padding:16px 18px;cursor:pointer;background:#171717}}
    .category-summary::-webkit-details-marker{{display:none}}
    .category-summary:hover{{background:#202020}}
    .category-heading{{display:flex;align-items:center;gap:10px;min-width:0;font-size:15px;font-weight:900}}
    .category-dot{{width:9px;height:9px;border-radius:50%;background:var(--yellow);flex:none;box-shadow:0 0 12px rgba(255,230,0,.35)}}
    .category-count{{color:#aaa;font-size:11px;font-weight:700;white-space:nowrap}}
    .category-meta{{display:flex;align-items:center;gap:10px}}
    .category-priority{{border-radius:50px;padding:5px 9px;font-size:9px;font-weight:900;letter-spacing:.07em}}
    .priority-high{{background:var(--yellow);color:#050505}}
    .priority-medium{{background:#493400;border:1px solid #725400;color:#ffe18a}}
    .priority-low{{background:#292929;border:1px solid #414141;color:#ccc}}
    .priority-other{{background:#202020;color:#888}}
    .category-chevron{{color:var(--yellow);font-size:17px;transition:transform .18s ease}}
    .category-section[open] .category-chevron{{transform:rotate(180deg)}}
    .group-grid{{padding:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px}}
    .card{{background:linear-gradient(155deg,#191919 0%,#111 100%);border:1px solid #353535;border-radius:18px;padding:20px;display:flex;flex-direction:column;gap:16px;box-shadow:0 10px 30px rgba(0,0,0,.3)}}
    .card-top,.prices,.meta-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
    .card-top{{justify-content:space-between;align-items:flex-start}}
    .vertical,.offer-date{{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.07em;border-radius:50px;padding:7px 11px}}
    .vertical{{background:#272300;color:var(--yellow);max-width:70%;line-height:1.35}}
    .offer-date{{background:#252525;color:#ddd;white-space:nowrap}}
    .product{{font-size:19px;line-height:1.4;font-weight:800;overflow-wrap:anywhere}}
    .prices{{gap:20px;align-items:flex-end;background:#101010;border:1px solid #292929;border-radius:12px;padding:13px 15px}}
    .price{{display:flex;flex-direction:column;gap:5px}}
    .price-label{{font-size:10px;color:#999;font-weight:800;text-transform:uppercase;letter-spacing:.08em}}
    .price-value{{font-size:14px;color:#aaa;font-weight:700;text-decoration:line-through}}
    .price-value.sale{{color:var(--yellow);font-size:24px;line-height:1.1;text-decoration:none}}
    .details{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}}
    .detail{{background:#1d1d1d;border:1px solid #303030;border-radius:11px;padding:11px 13px;min-width:0}}
    .detail-label{{font-size:10px;color:#aaa;font-weight:800;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:6px}}
    .detail-value{{display:block;font-size:13px;line-height:1.4;color:#f5f5f5;font-weight:700;overflow-wrap:anywhere}}
    .extra{{color:#bbb;font-size:12px;line-height:1.5;background:#1b1b1b;border-left:3px solid var(--yellow);padding:10px 12px;border-radius:0 8px 8px 0}}
    .code{{font-family:monospace;color:var(--yellow);font-size:14px;letter-spacing:.04em}}
    .link{{margin-top:auto;display:block;text-align:center;background:var(--yellow);color:#050505;text-decoration:none;font-weight:900;font-size:13px;padding:12px 16px;border-radius:50px}}
    .link:hover{{background:var(--yellow-dark)}}
    .link.disabled{{background:#2b2b2b;color:#888;pointer-events:none}}
    .empty{{grid-column:1/-1;text-align:center;padding:56px 20px;border:1px dashed #444;border-radius:var(--radius);color:#aaa;font-weight:700}}
    .footer{{text-align:center;color:#777;font-size:11px;font-weight:600;padding:10px 24px 30px}}
    @media(max-width:700px){{.hdr{{padding:10px 16px;flex-wrap:wrap}}.nav{{order:3;width:100%;overflow-x:auto;flex-wrap:nowrap;padding-bottom:4px}}.nav a{{white-space:nowrap}}.updated{{margin-left:auto}}.hero,.toolbar{{padding-left:16px;padding-right:16px}}.list{{padding-left:16px;padding-right:16px}}.group-grid{{padding:10px;grid-template-columns:1fr}}.category-summary{{padding:14px}}input{{margin-left:0;width:100%}}}}
  </style>
</head>
<body>
<header class="hdr">
  <a class="brand" href="last-minute.html"><span class="brand-pill">OFERTAS DE HOJE</span><span class="brand-sub">Black Friday • Afiliados</span></a>
  <nav class="nav">
    <a href="index.html">Cupons</a>
    <a href="ganhos-extras.html">Ganhos Extras</a>
    <a href="cupons-extras.html">Cupons Extras</a>
    <a class="active" href="last-minute.html">Ofertas de hoje</a>
  </nav>
  <span class="updated">Atualizado em {generated_at}</span>
</header>
<section class="hero">
  <div class="hero-inner">
    <div><div class="eyebrow">11.11 • Black Friday</div><h1>Ofertas <span>de hoje</span></h1><p>Produtos enviados pelo time Comercial, válidos para a data de hoje.</p></div>
    <div class="today" id="today-label"></div>
  </div>
</section>
<section class="toolbar"><div class="toolbar-inner">
  <span class="count"><strong id="count">0</strong> ofertas de hoje</span>
  <select id="category"><option value="">Todas as categorias</option></select>
  <input id="search" type="search" placeholder="Buscar produto ou oferta…" aria-label="Buscar produto ou oferta"/>
</div></section>
<main class="list" id="list"></main>
<div class="footer">Ofertas sujeitas à disponibilidade e às condições informadas pelo Comercial. Confirme os detalhes antes de divulgar.</div>
<script>
const ITEMS = {items_json};
const today = new Intl.DateTimeFormat('pt-BR',{{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',year:'numeric'}}).format(new Date());
document.getElementById('today-label').textContent = `${{today}}`;
const categorySelect = document.getElementById('category');
const CATEGORY_RANK = {{
  fashion:0, moda:0,
  beauty:1, beleza:1,
  he:2, 'moveis&decoracao':2, 'moveis e decoracao':2,
  tech:3, tecnologia:3,
  'f&h':4, 'alimentos&bebidas':4, 'alimentos e bebidas':4,
  'c&i':5, 'casa&construcao':5, 'casa e construcao':5,
  't&b':6, 'brinquedos&bebes':6, 'brinquedos e bebes':6,
  health:7, saude:7,
  vpa:8, 'veiculos&pecas&acessorios':8, 'veiculos e pecas e acessorios':8, 'auto&moto':8,
  sports:9, esportes:9,
  cpg:10, 'cpg(bens de consumo)':10,
  entertainment:11, entretenimento:11,
  pets:12, 'pet shop':12
}};
function categoryKey(value){{return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').replace(/\s*&\s*/g,'&').trim()}}
function categoryRank(value){{return CATEGORY_RANK[categoryKey(value)]??99}}
function priorityInfo(value){{const rank=categoryRank(value);if(rank<=4)return {{label:'HIGH',className:'priority-high'}};if(rank<=8)return {{label:'MEDIUM',className:'priority-medium'}};if(rank<=12)return {{label:'LOW',className:'priority-low'}};return {{label:'OUTRAS',className:'priority-other'}}}}
function compareCategories(a,b){{return categoryRank(a)-categoryRank(b)||a.localeCompare(b,'pt-BR')}}
const categories = [...new Set(ITEMS.map(item=>item.vertical).filter(Boolean))].sort(compareCategories);
for(const category of categories){{const option=document.createElement('option');option.value=category;option.textContent=category;categorySelect.appendChild(option)}}
function esc(value){{return String(value??'').replace(/[&<>"']/g,char=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]))}}
function safeUrl(value){{try{{const url=new URL(String(value||''));return ['http:','https:'].includes(url.protocol)?url.href:''}}catch{{return ''}}}}
function detail(label,value,extraClass=''){{if(!value)return '';return `<div class="detail"><span class="detail-label">${{esc(label)}}</span><span class="detail-value ${{extraClass}}">${{esc(value)}}</span></div>`}}
function render(){{
  const category=categorySelect.value;
  const query=document.getElementById('search').value.trim().toLocaleLowerCase('pt-BR');
  const items=ITEMS.filter(item=>(!category||item.vertical===category)&&(!query||[item.produto,item.vertical,item.tipo_cupom,item.desconto,item.codigo,item.informacoes_extras].join(' ').toLocaleLowerCase('pt-BR').includes(query)));
  document.getElementById('count').textContent=items.length;
  const list=document.getElementById('list');
  if(!items.length){{list.innerHTML='<div class="empty">Nenhuma oferta completa e válida para hoje.</div>';return}}
  const grouped=new Map();
  for(const item of items){{
    if(!grouped.has(item.vertical))grouped.set(item.vertical,[]);
    grouped.get(item.vertical).push(item);
  }}
  list.innerHTML=[...grouped.entries()].sort(([a],[b])=>compareCategories(a,b)).map(([name,groupItems])=>{{
    const open=(!category||name===category)?' open':'';
    const priority=priorityInfo(name);
    const cards=groupItems.map(item=>{{
      const url=safeUrl(item.url);
      const couponLabel=item.cupom||'';
      const details=[detail('Cupom',couponLabel),detail('Tipo de cupom',item.tipo_cupom),detail('Desconto',item.desconto),detail('Código',item.codigo,'code')].filter(Boolean).join('');
      const detailsBlock=details?`<div class="details">${{details}}</div>`:'';
      const prices=`<div class="prices"><div class="price"><span class="price-label">De</span><span class="price-value">${{esc(item.preco_de)}}</span></div><div class="price"><span class="price-label">Por</span><span class="price-value sale">${{esc(item.preco_por)}}</span></div></div>`;
      const extra=item.informacoes_extras?`<div class="extra">${{esc(item.informacoes_extras)}}</div>`:'';
      const link=`<a class="link" href="${{esc(url)}}" target="_blank" rel="noopener noreferrer">Ver oferta</a>`;
      return `<article class="card"><div class="card-top"><span class="vertical">${{esc(item.vertical)}}</span><span class="offer-date">Oferta de ${{esc(item.data_oferta)}}</span></div><h2 class="product">${{esc(item.produto)}}</h2>${{prices}}${{detailsBlock}}${{extra}}${{link}}</article>`;
    }}).join('');
    return `<section class="category-group"><details class="category-section"${{open}}><summary class="category-summary"><span class="category-heading"><span class="category-dot"></span>${{esc(name)}}</span><span class="category-meta"><span class="category-priority ${{priority.className}}">${{priority.label}}</span><span class="category-count">${{groupItems.length}} ofertas</span><span class="category-chevron" aria-hidden="true">⌄</span></span></summary><div class="group-grid">${{cards}}</div></details></section>`;
  }}).join('');
}}
categorySelect.addEventListener('change',render);
document.getElementById('search').addEventListener('input',render);
render();
</script>
</body>
</html>
"""


def main():
    now = datetime.now(timezone.utc).astimezone(BRT)
    items = parse_rows(fetch_rows(get_service()), now.date())
    html = HTML.format(
        generated_at=now.strftime("%d/%m/%Y %H:%M"),
        items_json=(json.dumps(items, ensure_ascii=False, indent=2)
                    .replace("<", "\\u003c")
                    .replace(">", "\\u003e")
                    .replace("&", "\\u0026")),
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as output:
        output.write(html)
    print(f"✅ {OUTPUT_FILE} gerado com {len(items)} ofertas válidas para {now:%d/%m/%Y}")


if __name__ == "__main__":
    main()
