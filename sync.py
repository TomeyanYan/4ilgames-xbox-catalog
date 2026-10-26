"""Build a searchable Xbox catalog on GitHub Pages from a public Telegraph source."""
import html
import json
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE = "https://telegra.ph/Spisok-igr-1-12-14-3"
OUTPUT = Path("site")
PRICE = re.compile(r"(?<!\d)(\d[\d\s\u00a0]{0,9})\s*(?:₽|руб(?:\.|лей|ля)?|RUB)", re.I)
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "Mozilla/5.0 (compatible; 4ILGAMES-Catalog/2.0)"})


def get_source():
    response = HTTP.get(SOURCE, timeout=40)
    response.raise_for_status()
    article = BeautifulSoup(response.text, "html.parser").select_one("article")
    if article is None:
        raise RuntimeError("Не найден список игр в исходной статье")
    lines = []
    for el in article.find_all(["p", "h3", "h4", "li"]):
        if el.find_parent(["p", "h3", "h4", "li"]):
            continue
        value = el.get_text(" ", strip=True)
        if value:
            lines.append(value)
    if len(lines) < 50:
        raise RuntimeError(f"Слишком мало строк: {len(lines)}")
    return lines


def get_rate():
    response = HTTP.get("https://api.nbrb.by/exrates/rates/RUB?parammode=2", timeout=25)
    response.raise_for_status()
    data = response.json()
    rate = Decimal(str(data["Cur_OfficialRate"])) / Decimal(str(data["Cur_Scale"]))
    if not Decimal("0.001") < rate < Decimal("1"):
        raise RuntimeError("Неожиданный курс RUB/BYN")
    return rate, data["Date"][:10]


def convert(value, rate):
    def replace(match):
        rub = Decimal(match.group(1).replace(" ", "").replace("\u00a0", ""))
        byn = (rub * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{match.group(0).strip()} / {byn:.2f} BYN".replace(f"{byn:.2f}", f"{byn:.2f}".replace(".", ","))
    return PRICE.sub(replace, value)


def build():
    lines = get_source()
    rate, rate_date = get_rate()
    converted = [convert(line, rate) for line in lines]
    converted_count = sum(a != b for a, b in zip(lines, converted))
    if converted_count < 30:
        raise RuntimeError(f"Распознано слишком мало цен: {converted_count}")
    # Source includes informational paragraphs as well as game titles.
    now = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y в %H:%M")
    entries = "\n".join(
        f'<div class="item" data-search="{html.escape(line.casefold(), quote=True)}">{html.escape(line)}</div>'
        for line in converted
    )
    page = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#10131a"><meta name="description" content="4ILGAMES — каталог игр Xbox с ценами в белорусских рублях">
<title>Каталог игр Xbox — 4ILGAMES</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}*{box-sizing:border-box}
body{margin:0;background:#0d1017;color:#eaf0f8}main{max-width:980px;margin:auto;padding:26px 16px 64px}
header{background:linear-gradient(125deg,#102b20,#101622 75%);border:1px solid #2c5943;border-radius:20px;padding:25px;margin-bottom:20px}
h1{margin:0 0 8px;font-size:clamp(28px,5vw,43px)}h1 span{color:#4ce19a}.subtitle{color:#c1d4c9;margin:0 0 16px}
.meta{color:#b5c2d3;font-size:14px;line-height:1.7}.search{position:sticky;top:0;background:#0d1017;padding:12px 0;z-index:2}
input{width:100%;border:1px solid #405264;border-radius:12px;padding:16px;background:#1b2430;color:white;font-size:17px;outline:none}
input:focus{border-color:#4ce19a}#count{color:#a9b6c7;font-size:14px;margin:8px 3px 15px}
.item{background:#171d28;border:1px solid #293242;border-radius:10px;padding:13px 15px;margin:8px 0;line-height:1.5;overflow-wrap:anywhere}
.item:hover{border-color:#3c775b}.item[hidden]{display:none}footer{color:#8795a8;font-size:13px;margin-top:26px}
a{color:#6fe5ab}
</style></head><body><main><header><h1><span>4ILGAMES</span> · Xbox</h1>
<p class="subtitle">Каталог игр и дополнений · цены в BYN без наценки</p>
<div class="meta">Курс НБРБ: 1 RUB = __RATE__ BYN · дата курса: __RATE_DATE__<br>
Обновлено: __UPDATED__ (Минск)<br>Наличие и итоговую стоимость уточняйте перед покупкой.</div></header>
<div class="search"><input id="q" type="search" placeholder="🔎 Найти игру по названию..." aria-label="Поиск игр"></div>
<div id="count" role="status"></div><section id="catalog">__ENTRIES__</section>
<footer>Источник: <a href="__SOURCE__" rel="noopener noreferrer">публичный список игр</a>. Конвертация по официальному курсу НБРБ.</footer></main>
<script>
const input=document.getElementById('q'), items=[...document.querySelectorAll('.item')], count=document.getElementById('count');
function update(){const term=input.value.trim().toLocaleLowerCase('ru');let shown=0;
for(const el of items){const visible=el.dataset.search.includes(term);el.hidden=!visible;if(visible)shown++}
count.textContent=`Найдено строк: ${shown} из ${items.length}`}
input.addEventListener('input',update);update();
</script></body></html>'''
    page = (page.replace("__RATE__", str(rate))
                .replace("__RATE_DATE__", html.escape(rate_date))
                .replace("__UPDATED__", html.escape(now))
                .replace("__ENTRIES__", entries)
                .replace("__SOURCE__", html.escape(SOURCE, quote=True)))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    (OUTPUT / ".nojekyll").touch()
    print(f"Generated site/index.html: {len(lines)} lines, {converted_count} converted, rate {rate}, date {rate_date}")

if __name__ == "__main__":
    build()
