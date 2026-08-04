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
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING"
    ).execute()
    return result.get("values", [])

# ── PARSE ─────────────────────────────────────────────────────────────────────

def safe_get(row, idx, default=""):
    try:
        return row[idx].strip()
    except (IndexError, AttributeError):
        return default

def parse_date(s):
    if not s and s != 0:
        return None
    # Se for número serial do Excel/Sheets (ex: 46645)
    if isinstance(s, (int, float)):
        from datetime import timedelta
        serial = int(s)
        # Sheets usa epoch 30/12/1899
        return (date(1899, 12, 30) + timedelta(days=serial))
    s = str(s).strip()
    if not s:
        return None
    # Normaliza D/M/YYYY ou D/M/YY
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
