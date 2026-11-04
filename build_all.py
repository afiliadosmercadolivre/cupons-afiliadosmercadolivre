#!/usr/bin/env python3
"""
build_all.py — orquestrador do projeto "Cupons Afiliados Mercado Livre".

O que faz
  1. Carrega a credencial da Service Account (variável de ambiente ou arquivo local).
  2. Roda os 4 geradores: Cupons, Ganhos Extras, Cupons Extras e Last Minute.
  3. Valida cada HTML gerado (existe? tem dados? campos obrigatórios? sem cupom vencido?
     links de navegação? termos proibidos?) e imprime um resumo.

Uso
  python build_all.py                      # gera + valida as quatro páginas
  python build_all.py --only cupons        # só uma página (cupons | ganhos | extras | last-minute)
  python build_all.py --validate-only      # só valida os HTML que já existem
  python build_all.py --credentials chave.json   # usa arquivo local (NUNCA suba esse arquivo)
  python build_all.py --strict             # falha (exit 1) se alguma página tiver 0 itens

Credencial: em produção vem do secret GOOGLE_SERVICE_ACCOUNT_JSON do GitHub Actions.
Localmente, aponte --credentials para o JSON baixado do Google Cloud ou exporte a variável.
O conteúdo da chave nunca é impresso.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FILE_DIR = Path(__file__).resolve().parent
if (FILE_DIR / "generate.py").exists() and FILE_DIR.name == "scripts":
    ROOT_DIR = FILE_DIR.parent
    SCRIPT_DIR = Path("scripts")
elif (FILE_DIR / "generate.py").exists():
    ROOT_DIR = FILE_DIR
    SCRIPT_DIR = Path(".")
elif (FILE_DIR / "scripts" / "generate.py").exists():
    ROOT_DIR = FILE_DIR
    SCRIPT_DIR = Path("scripts")
elif (FILE_DIR / "cupons-afiliados-ml" / "scripts" / "generate.py").exists():
    ROOT_DIR = FILE_DIR
    SCRIPT_DIR = Path("cupons-afiliados-ml/scripts")
else:
    ROOT_DIR = FILE_DIR
    SCRIPT_DIR = Path("scripts")
SCRIPT_PREFIX = "" if str(SCRIPT_DIR) == "." else SCRIPT_DIR.as_posix() + "/"

PAGES = {
    "cupons": {"script": f"{SCRIPT_PREFIX}generate.py", "output": "index.html", "var": "COUPONS",
               "required": ["nome", "dia_fim", "categoria", "is_mar_aberto", "discount_num"],
               "date_field": "dia_fim"},
    "ganhos": {"script": f"{SCRIPT_PREFIX}generate_ganhos.py", "output": "ganhos-extras.html", "var": "ITEMS",
               "required": ["categoria", "data_fim", "ganho_max"],
               "date_field": "data_fim"},
    "extras": {"script": f"{SCRIPT_PREFIX}generate_cupons_extras.py", "output": "cupons-extras.html", "var": "ITEMS",
               "required": ["categoria", "data_final", "desconto"],
               "date_field": "data_final"},
    "last-minute": {"script": f"{SCRIPT_PREFIX}generate_last_minute.py", "output": "last-minute.html", "var": "ITEMS",
                    "required": ["produto", "vertical", "data_oferta"],
                    "date_field": "data_oferta", "exact_today": True},
}

NAV_LINKS = ["index.html", "ganhos-extras.html", "cupons-extras.html", "last-minute.html"]
# Termos que o time pediu para NÃO aparecerem como texto das páginas públicas
FORBIDDEN = [r"budget", r"comiss"]
BRT = timezone(timedelta(hours=-3))


def today_brt() -> date:
    return datetime.now(timezone.utc).astimezone(BRT).date()


def parse_br_date(s: str):
    try:
        d, m, y = (int(x) for x in str(s).strip().split("/"))
        return date(y, m, d)
    except Exception:
        return None


# ── credenciais ──────────────────────────────────────────────────────────────
def load_credentials(path: str | None) -> None:
    """Garante GOOGLE_SERVICE_ACCOUNT_JSON no ambiente, sem nunca imprimir a chave."""
    if path:
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = Path(path).read_text(encoding="utf-8")
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        sys.exit("✖ Sem credencial. Defina GOOGLE_SERVICE_ACCOUNT_JSON ou use --credentials arquivo.json")
    try:
        info = json.loads(raw)
        assert info.get("private_key") and info.get("client_email")
    except Exception:
        sys.exit("✖ Credencial inválida: precisa ser o JSON completo da Service Account.")
    print(f"🔐 Service Account: {info['client_email']}")


# ── execução ─────────────────────────────────────────────────────────────────
def run_generator(key: str) -> bool:
    page = PAGES[key]
    print(f"\n▶ {key}: python {page['script']}")
    t0 = time.time()
    proc = subprocess.run([sys.executable, page["script"]], cwd=ROOT_DIR)
    ok = proc.returncode == 0
    print(f"{'✅' if ok else '❌'} {key} {'ok' if ok else 'FALHOU'} em {time.time() - t0:.1f}s")
    return ok


# ── validação ────────────────────────────────────────────────────────────────
def extract_array(html: str, var: str):
    m = re.search(rf"const {var} = ", html)
    if not m:
        return None
    arr, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return arr


def validate(key: str) -> tuple[list[str], list[str], int]:
    """Retorna (erros, avisos, nº de itens)."""
    page, errors, warnings = PAGES[key], [], []
    path = ROOT_DIR / page["output"]
    if not path.exists():
        return [f"{page['output']} não existe"], warnings, 0
    html = path.read_text(encoding="utf-8")
    if len(html) < 5000:
        errors.append(f"arquivo muito pequeno ({len(html)} bytes)")

    try:
        items = extract_array(html, page["var"])
    except Exception as e:
        return errors + [f"não consegui ler o array JS '{page['var']}': {e}"], warnings, 0
    if items is None:
        return errors + [f"array JS 'const {page['var']} =' não encontrado"], warnings, 0

    if not items:
        warnings.append("0 itens — confira a aba, a data da oferta e os filtros da planilha")
    for i, it in enumerate(items):
        missing = [f for f in page["required"] if f not in it]
        if missing:
            errors.append(f"item {i} sem campos {missing}")
            break
    today = today_brt()
    vencidos = [it for it in items if (d := parse_br_date(it.get(page["date_field"], ""))) and d < today]
    if vencidos:
        errors.append(f"{len(vencidos)} item(ns) já vencido(s) na página")
    if page.get("exact_today"):
        fora_de_hoje = [it for it in items if parse_br_date(it.get(page["date_field"], "")) != today]
        if fora_de_hoje:
            errors.append(f"{len(fora_de_hoje)} oferta(s) fora da data de hoje na página")

    for link in NAV_LINKS:
        if f'href="{link}"' not in html:
            warnings.append(f"link de navegação ausente: {link}")

    visible = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    for pat in FORBIDDEN:
        if re.search(pat, visible, re.I):
            warnings.append(f"termo proibido no texto da página: /{pat}/")
    return errors, warnings, len(items)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=PAGES.keys(), help="gera/valida só uma página")
    ap.add_argument("--validate-only", action="store_true", help="não gera, só valida os HTML existentes")
    ap.add_argument("--credentials", help="caminho do JSON da Service Account (uso local)")
    ap.add_argument("--strict", action="store_true", help="exit 1 se alguma página tiver 0 itens")
    args = ap.parse_args()

    keys = [args.only] if args.only else list(PAGES)
    failed = False

    if not args.validate_only:
        load_credentials(args.credentials)
        for k in keys:
            failed |= not run_generator(k)

    print("\n══ VALIDAÇÃO ══")
    for k in keys:
        errors, warnings, n = validate(k)
        status = "❌" if errors else ("⚠️ " if warnings else "✅")
        print(f"{status} {PAGES[k]['output']:<20} {n:>3} itens")
        for e in errors:
            print(f"     ✖ {e}")
        for w in warnings:
            print(f"     ! {w}")
        failed |= bool(errors) or (args.strict and n == 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
