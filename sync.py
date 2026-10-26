import html
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SOURCE = "https://telegra.ph/Spisok-igr-1-12-14-3"
PRICE = re.compile(r"(?<!\d)(\d[\d\s\u00a0]{0,9})\s*(?:₽|руб(?:\.|лей|ля)?|RUB)", re.I)
def main():
    response = requests.get(SOURCE, timeout=40, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    article = BeautifulSoup(response.text, "html.parser").select_one("article")
    if not article:
        raise RuntimeError("Source article not found")
    lines = []
    for el in article.find_all(["p", "h3", "h4", "li"]):
        if not el.find_parent(["p", "h3", "h4", "li"]):
            line = el.get_text(" ", strip=True)
            if line:
                lines.append(line)
    if len(lines) < 50:
        raise RuntimeError("Source list is unexpectedly short")

    data = requests.get("https://api.nbrb.by/exrates/rates/RUB?parammode=2", timeout=25)
    data.raise_for_status()
    rate_data = data.json()
    rate = Decimal(str(rate_data["Cur_OfficialRate"])) / Decimal(str(rate_data["Cur_Scale"]))
    if not Decimal("0.001") < rate < Decimal("1"):
        raise RuntimeError("Invalid RUB/BYN rate")

    def convert(line):
        def repl(match):
            rub = Decimal(match.group(1).replace(" ", "").replace("\u00a0", ""))
            byn = (rub * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return match.group(0).strip() + " / " + format(byn, ".2f").replace(".", ",") + " BYN"
        return PRICE.sub(repl, line)

    converted = [convert(line) for line in lines]
    changed = sum(a != b for a, b in zip(lines, converted))
    if changed < 30:
        raise RuntimeError("Too few converted prices")
    entries = "\n".join(
        '<div class="item" data-search="' + html.escape(line.casefold(), quote=True) + '">' +
        html.escape(line) + '</div>' for line in converted
    )
    template = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Каталог Xbox — 4ILGAMES</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Arial,sans-serif}*{box-sizing:border-box}
body{margin:0;background:#0d1017;color:#eaf0f8}main{max-width:1050px;margin:auto;padding:25px 16px 65px}
header{background:#0e131c;border:1px solid #252f3c;border-radius:20px;padding:24px;margin-bottom:18px}
h1{font-size:13px;margin:0 0 20px;font-weight:800;letter-spacing:.03em}h1 span{color:#4ce19a}
header p{color:#c6d8cf;line-height:1.6;margin:0}header h2{font-size:clamp(22px,4vw,28px);margin:0 0 10px;color:#fff}header .hint{font-size:14px;color:#a9c7bb;border-top:1px solid #334153;padding-top:18px;margin-top:18px}h2{font-size:23px}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-bottom:25px}
.feature{background:#171d28;border:1px solid #2b3947;border-radius:14px;overflow:hidden}
.feature img{display:block;width:100%;aspect-ratio:460/215;object-fit:cover;background:#273445}
.feature-body{padding:13px}.feature-body strong{font-size:16px}
.feature-body p{color:#bfcddb;font-size:13px;line-height:1.5;min-height:45px}
button{border:1px solid #3c9a63;border-radius:9px;padding:10px 12px;background:#245c3d;color:white;cursor:pointer}
.search{position:sticky;top:0;background:#0d1017;padding:12px 0;z-index:2}
input{width:100%;border:1px solid #405264;border-radius:12px;padding:16px;background:#1b2430;color:white;font-size:17px}
#count{color:#a9b6c7;font-size:14px;margin:9px 2px 15px}
.item{background:#171d28;border:1px solid #293242;border-radius:10px;padding:13px 15px;margin:8px 0;line-height:1.5;overflow-wrap:anywhere}
.item[hidden]{display:none}footer{color:#91a0b0;font-size:13px;margin-top:25px}a{color:#6fe5ab}
</style></head><body><main>
<header><h1><span>4ILGAMES / XBOX</span></h1>
<h2>Во что играем сегодня? 💚</h2>
<p>Собрали игры для Xbox в одном месте, чтобы ты не тратил время на поиски.</p>
<p class="hint">Не нашёл нужную? <a href="https://t.me/TomeyanK2" target="_blank" rel="noopener noreferrer">Напиши</a> — попробуем найти.</p></header>
<div class="search"><input id="q" type="search" placeholder="⌕ Найти игру..." aria-label="Поиск игр"></div>
<div id="count"></div><section id="catalog">__ENTRIES__</section>
<footer>Цены в BYN рассчитаны по официальному курсу НБРБ без наценки. Оригинальные цены в ₽ сохранены.
Источник: <a href="__SOURCE__">список игр</a>. Наличие уточняйте перед покупкой.</footer>
</main><script>
const input=document.getElementById('q'),items=[...document.querySelectorAll('.item')],count=document.getElementById('count');
function update(){const term=input.value.trim().toLocaleLowerCase('ru');let shown=0;
for(const el of items){const visible=el.dataset.search.includes(term);el.hidden=!visible;if(visible)shown++}
count.textContent=`Найдено строк: ${shown} из ${items.length}`}
input.addEventListener('input',update);
document.querySelectorAll('[data-find]').forEach(b=>b.addEventListener('click',()=>{
input.value=b.dataset.find;update();input.scrollIntoView({behavior:'smooth',block:'center'});input.focus()}));

update();
</script></body></html>'''
    page = template.replace("__ENTRIES__", entries).replace("__SOURCE__", html.escape(SOURCE, quote=True))
    output = Path("site")
    output.mkdir(exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").touch()
    print(f"Generated {len(lines)} entries, {changed} converted, {len(cards)} featured cards")

if __name__ == "__main__":
    main()
