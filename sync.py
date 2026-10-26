"""4ILGAMES Xbox catalog — friendly header, RUB/BYN, searchable, GitHub Pages."""
import html
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE = 'https://telegra.ph/Spisok-igr-1-12-14-3'
PRICE = re.compile(r'(?<!\d)(\d[\d\s\u00a0]{0,9})\s*(?:₽|руб(?:\.|лей|ля)?|RUB)', re.I)


def main():
    response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    article = BeautifulSoup(response.text, 'html.parser').select_one('article')
    if article is None:
        raise RuntimeError('Не удалось найти каталог в источнике')
    lines = []
    for el in article.find_all(['p', 'h3', 'h4', 'li']):
        if not el.find_parent(['p', 'h3', 'h4', 'li']):
            line = el.get_text(' ', strip=True)
            if line:
                lines.append(line)
    if len(lines) < 50:
        raise RuntimeError('Источник вернул слишком мало строк')

    response = requests.get('https://api.nbrb.by/exrates/rates/RUB?parammode=2', timeout=25)
    response.raise_for_status()
    data = response.json()
    rate = Decimal(str(data['Cur_OfficialRate'])) / Decimal(str(data['Cur_Scale']))
    if not Decimal('0.001') < rate < Decimal('1'):
        raise RuntimeError('Неожиданный курс RUB/BYN')

    def convert(line):
        def replace(match):
            rub = Decimal(match.group(1).replace(' ', '').replace('\u00a0', ''))
            byn = (rub * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return match.group(0).strip() + ' / ' + f'{byn:.2f}'.replace('.', ',') + ' BYN'
        return PRICE.sub(replace, line)

    converted = [convert(line) for line in lines]
    changed = sum(before != after for before, after in zip(lines, converted))
    if changed < 30:
        raise RuntimeError('Не удалось распознать достаточное количество цен')
    entries = '\n'.join(
        '<div class="item" data-search="' + html.escape(before.casefold(), quote=True) + '">' +
        html.escape(after) + '</div>'
        for before, after in zip(lines, converted)
    )
    template = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0d121b"><meta name="description" content="Каталог Xbox 4ILGAMES — игры и цены в RUB и BYN">
<title>Каталог Xbox — 4ILGAMES</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif}*{box-sizing:border-box}
body{margin:0;background:#0d1017;color:#eaf0f8}main{max-width:980px;margin:auto;padding:26px 16px 64px}
header{background:#0d121b;border:1px solid #252f3c;border-radius:20px;padding:22px 20px 17px;margin-bottom:18px}
.brand{display:flex;justify-content:space-between;align-items:center;color:#4ce19a;font-size:13px;font-weight:800;margin-bottom:22px}
.brand svg{width:19px;height:19px;fill:none;stroke:#4ce19a;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
h1{font-size:clamp(22px,4vw,28px);margin:0 0 14px;color:#fff}
.subtitle{color:#c6d2e0;line-height:1.6;margin:0 0 18px}
.hint{color:#aac6ba;border-top:1px solid #334153;padding-top:19px;margin:0 0 14px;font-size:14px}
.search{position:relative}.search:before{content:'⌕';position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#a4b4c6;font-size:25px;pointer-events:none}
input{width:100%;border:1px solid #202d3c;border-radius:11px;padding:15px 16px 15px 40px;background:#1b2533;color:white;font-size:16px;outline:none}
input:focus{border-color:#4ce19a}#count{color:#a9b6c7;font-size:14px;margin:12px 3px 15px}
.item{background:#171d28;border:1px solid #293242;border-radius:10px;padding:13px 15px;margin:8px 0;line-height:1.5;overflow-wrap:anywhere}
.item:hover{border-color:#3c775b}.item[hidden]{display:none}footer{color:#91a0b0;font-size:13px;margin-top:26px;line-height:1.6}
a{color:#6fe5ab}
</style></head><body><main>
<header><div class="brand"><span>4ILGAMES / XBOX</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 8h11a4 4 0 0 1 3.8 3l1.2 5a2.5 2.5 0 0 1-4.1 2.4l-2.7-2.2H8.3l-2.7 2.2A2.5 2.5 0 0 1 1.5 16l1.2-5a4 4 0 0 1 3.8-3Z"/><path d="M7 11v5m-2.5-2.5h5M16.5 12h.01M19 14h.01"/></svg></div>
<h1>Во что играем сегодня? 💚</h1>
<p class="subtitle">Собрали игры для Xbox в одном месте, чтобы ты не тратил время на поиски.</p>
<p class="hint">Не нашёл нужную? <a href="https://t.me/TomeyanK2" target="_blank" rel="noopener noreferrer">Напиши</a> — попробуем найти.</p>
<div class="search"><input id="q" type="search" placeholder="Найти игру..." aria-label="Поиск игр"></div></header>
<div id="count" role="status"></div><section id="catalog">__ENTRIES__</section>
<footer>Цены в BYN рассчитаны по официальному курсу НБРБ без наценки. Цены в ₽ сохранены. Источник: <a href="__SOURCE__" rel="noopener noreferrer">список игр</a>. Наличие уточняйте перед покупкой.</footer>
</main><script>
const input=document.getElementById('q'),items=[...document.querySelectorAll('.item')],count=document.getElementById('count');
function update(){const term=input.value.trim().toLocaleLowerCase('ru');let shown=0;
for(const el of items){const visible=el.dataset.search.includes(term);el.hidden=!visible;if(visible)shown++}
count.textContent=`Найдено строк: ${shown} из ${items.length}`}
input.addEventListener('input',update);update();
</script></body></html>'''
    page = template.replace('__ENTRIES__', entries).replace('__SOURCE__', html.escape(SOURCE, quote=True))
    output = Path('site')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / '.nojekyll').touch()
    print(f'Generated {len(lines)} entries, {changed} converted prices')


if __name__ == '__main__':
    main()
