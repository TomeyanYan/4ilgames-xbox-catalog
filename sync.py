"""Build 4ILGAMES Xbox catalog for GitHub Pages. Dependencies: requests, beautifulsoup4."""
import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SOURCE = 'https://telegra.ph/Spisok-igr-1-12-14-3'
TELEGRAM = 'https://t.me/TomeyanK2'
PRICE = re.compile(r'(?<!\d)(\d[\d\s\u00a0]{0,9})\s*(?:₽|руб(?:\.|лей|ля)?|RUB)', re.I)
NEW = [('Battlefield 6','battlefield 6',2807960),('Borderlands 4','borderlands 4',1285190),('ARC Raiders','arc raiders',1808500),('DOOM: The Dark Ages','doom: the dark ages',3017860),('Kingdom Come: Deliverance II','kingdom come: deliverance ii',1771300)]


def main():
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (4ILGAMES catalog sync)'
    response = session.get(SOURCE, timeout=40)
    response.raise_for_status()
    article = BeautifulSoup(response.text, 'html.parser').select_one('article')
    if not article:
        raise RuntimeError('Source article not found')
    lines = []
    for element in article.find_all(['p','h3','h4','li']):
        if not element.find_parent(['p','h3','h4','li']):
            value = element.get_text(' ', strip=True)
            if value:
                lines.append(value)
    if len(lines) < 50:
        raise RuntimeError('Source unexpectedly short')
    response = session.get('https://api.nbrb.by/exrates/rates/RUB?parammode=2', timeout=25)
    response.raise_for_status()
    rate_info = response.json()
    rate = Decimal(str(rate_info['Cur_OfficialRate'])) / Decimal(str(rate_info['Cur_Scale']))
    if not Decimal('0.001') < rate < Decimal('1'):
        raise RuntimeError('Invalid RUB/BYN exchange rate')

    def convert(line):
        def replace(match):
            rub = Decimal(match.group(1).replace(' ', '').replace('\u00a0', ''))
            byn = (rub * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return match.group(0).strip() + ' / ' + format(byn, '.2f').replace('.', ',') + ' BYN'
        return PRICE.sub(replace, line)

    products = []
    for line in lines:
        match = PRICE.search(line)
        if not match:
            continue
        rub = int(match.group(1).replace(' ', '').replace('\u00a0', ''))
        if rub <= 0:
            continue
        byn = (Decimal(rub) * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        name = line[:match.start()].strip(' \t–—:-') or line.strip()
        lower = line.casefold()
        # Platform detection is conservative: no platform is guessed when the source is silent.
        if 'series x' in lower or 'series s' in lower or 'x|s' in lower:
            platform = 'series'
        elif 'xbox one' in lower:
            platform = 'one'
        else:
            platform = 'unknown'
        kind = 'addon' if any(term in lower for term in ['dlc','дополнение','season pass','expansion','upgrade','add-on']) else ('subscription' if any(term in lower for term in ['game pass','подписка']) else 'game')
        # Discounts are shown only where the source explicitly labels them.
        discount = bool(re.search(r'(?<!\w)(?:скидк[аиу]?|акци[яи]|sale|-[1-9]\d?\s*%)(?!\w)', lower))
        products.append({'id':len(products), 'name':name, 'full':line, 'display':convert(line), 'rub':rub, 'byn':str(byn), 'platform':platform, 'kind':kind, 'discount':discount})
    if len(products) < 30:
        raise RuntimeError('Too few prices recognized')

    featured = []
    for title, needle, appid in NEW:
        product = next((p for p in products if needle in p['name'].casefold() and p['kind']=='game'), None)
        if product:
            featured.append({'title':title, 'productId':product['id'], 'image':f'https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg'})
    # This is NOT a fake markdown: discounts are taken from explicit source labels only.
    offers = [p['id'] for p in products if p['discount']][:8]
    payload = json.dumps({'products':products, 'featured':featured, 'offers':offers}, ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page = TEMPLATE.replace('__DATA__', payload).replace('__TELEGRAM__', html.escape(TELEGRAM, quote=True)).replace('__SOURCE__', html.escape(SOURCE, quote=True))
    output = Path('site')
    output.mkdir(parents=True, exist_ok=True)
    (output/'index.html').write_text(page, encoding='utf-8')
    (output/'.nojekyll').touch()
    print(f'Built {len(products)} products, {len(featured)} new releases, {len(offers)} explicitly marked offers; rate {rate}')

TEMPLATE = r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0d1017"><meta name="description" content="Каталог Xbox 4ILGAMES — игры, новинки и цены в RUB и BYN">
<title>4ILGAMES — каталог Xbox</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color-scheme:dark}*{box-sizing:border-box}
body{background:#0d1017;color:#eef5fa;margin:0}main{max-width:1150px;margin:auto;padding:24px 16px 70px}
a{color:#77eab0}header{border:1px solid #345945;border-radius:22px;background:radial-gradient(circle at 90% 10%,#21543c 0,transparent 35%),linear-gradient(120deg,#102b21,#131b2c);padding:28px;margin-bottom:25px}
.logo{font-weight:900;color:#62eaa4;letter-spacing:.04em}h1{font-size:clamp(28px,5vw,44px);margin:14px 0 10px}header p{color:#c9d9d1;line-height:1.6}h2{font-size:22px;margin:24px 0 14px}
.btn,button{border:1px solid #3c9b64;border-radius:10px;padding:11px 14px;background:#265e40;color:white;cursor:pointer;font:inherit;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:5px}
.btn.primary,button.primary{background:#39c477;color:#06180e;font-weight:800}.btn:hover,button:hover{filter:brightness(1.15)}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #7cf5b4;outline-offset:2px}
.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.arrows{display:flex;gap:8px}
.slider{display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:thin;padding-bottom:12px}
.slide{flex:0 0 min(315px,83vw);scroll-snap-align:start;background:#171e29;border:1px solid #314539;border-radius:15px;overflow:hidden}
.slide img{width:100%;aspect-ratio:460/215;object-fit:cover;display:block;background:#273142}.slide-body{padding:14px}.slide h3{margin:4px 0 9px;font-size:18px}.slide p{color:#bacbda;font-size:14px;min-height:38px}
.toolbar{position:sticky;top:0;z-index:3;background:#0d1017;padding:13px 0;border-bottom:1px solid #263342}
.controls{display:grid;grid-template-columns:minmax(180px,2fr) repeat(3,minmax(125px,1fr));gap:10px}input,select{background:#1b2532;border:1px solid #405264;border-radius:10px;padding:13px;color:#fff;font:inherit;width:100%;min-width:0}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:13px 0 0}.tabs button{padding:8px 12px}.tabs button.active{background:#40c17b;color:#081c11}
#count{font-size:14px;color:#a8bacb;margin:17px 0}.item{display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid #2a3645;background:#171d28;border-radius:12px;padding:13px 15px;margin:9px 0}.item:hover{border-color:#478765}
.item-name{font-weight:650}.prices{color:#b4e4c9;font-size:14px;margin-top:6px}.item-actions{display:flex;gap:8px;flex-shrink:0}.heart{font-size:20px;min-width:44px}.heart.saved{color:#ff829c;border-color:#c05778}
.notice{font-size:13px;color:#a5b5c4;line-height:1.6}.empty{padding:20px;border:1px dashed #3a4d5f;border-radius:12px;color:#a9bbcd}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#1e5238;color:white;padding:12px 18px;border-radius:12px;z-index:10;display:none;max-width:90vw}
footer{color:#8d9fb0;font-size:13px;line-height:1.6;margin-top:32px}
@media(max-width:760px){.controls{grid-template-columns:1fr 1fr}.controls input{grid-column:1/-1}.item{align-items:flex-start;flex-direction:column}.item-actions{align-self:stretch}.item-actions .btn{flex:1}header{padding:21px}}
@media(max-width:400px){.controls{grid-template-columns:1fr}.controls input{grid-column:auto}}
</style></head><body><main>
<header><div class="logo">4ILGAMES · Xbox</div><h1>Во что играем сегодня? 💚</h1>
<p>Собрали игры для Xbox в одном месте, чтобы ты не тратил время на поиски.<br>Не нашёл нужную? Напиши — попробуем найти.<br>Цены в ₽ и BYN.</p>
<a class="btn primary" href="__TELEGRAM__" target="_blank" rel="noopener noreferrer">💬 Написать в Telegram ↗</a></header>
<section id="new-section" hidden><div class="head"><h2>🆕 Новинки Xbox</h2><div class="arrows"><button id="prev" aria-label="Назад">‹</button><button id="next" aria-label="Вперёд">›</button></div></div><div id="slider" class="slider"></div></section>
<section id="offers-section" hidden><h2>🏷️ Скидки недели</h2><div id="offers"></div><p class="notice">Показываются только предложения, явно отмеченные как акции или скидки в исходном списке. Актуальность уточняйте.</p></section>
<section class="toolbar" aria-label="Поиск и фильтры"><div class="controls">
<input id="search" type="search" placeholder="🔎 Найти игру..." aria-label="Поиск по каталогу">
<select id="platform" aria-label="Платформа"><option value="all">Все платформы</option><option value="series">Xbox Series X|S (указано)</option><option value="one">Xbox One (указано)</option><option value="unknown">Платформа не указана</option></select>
<select id="kind" aria-label="Тип товара"><option value="all">Все товары</option><option value="game">Игры</option><option value="addon">Дополнения</option><option value="subscription">Подписки</option></select>
<select id="sort" aria-label="Сортировка"><option value="source">По списку</option><option value="asc">Сначала дешевле</option><option value="desc">Сначала дороже</option><option value="az">По названию</option></select></div>
<div class="tabs"><button id="tab-all" class="active">Весь каталог</button><button id="tab-fav">♡ Избранное <span id="fav-count">0</span></button><button id="send-list">📋 Отправить список в Telegram</button></div></section>
<div id="count" role="status"></div><section id="catalog"></section>
<footer>Цены в BYN рассчитаны по официальному курсу НБРБ без наценки. Стоимость и наличие уточняйте перед покупкой. <a href="__SOURCE__" target="_blank" rel="noopener noreferrer">Источник каталога</a>.<br>Избранное сохраняется только в этом браузере. При очистке данных браузера оно может исчезнуть.</footer>
</main><div id="toast" role="status"></div>
<script id="catalog-data" type="application/json">__DATA__</script>
<script>
(()=>{'use strict';
const data=JSON.parse(document.getElementById('catalog-data').textContent),products=data.products,byId=new Map(products.map(p=>[p.id,p]));
const tg='__TELEGRAM__',site='https://tomeyanyan.github.io/4ilgames-xbox-catalog/';
const $=id=>document.getElementById(id),escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeFav=()=>{try{return JSON.parse(localStorage.getItem('4ilgames-favs')||'[]').filter(Number.isInteger)}catch{return []}};
let fav=new Set(safeFav()),tab='all',toastTimer;
const money=p=>`${p.rub.toLocaleString('ru-RU')} ₽ / ${Number(p.byn).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} BYN`;
function notify(message){const el=$('toast');el.textContent=message;el.style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.style.display='none',3600)}
async function order(items){if(!items.length)return notify('Сначала добавьте игры в избранное');
const text=['Здравствуйте! Хочу купить в 4ILGAMES:',...items.map(p=>'• '+p.name+' — '+money(p)),'Ссылка на каталог: '+site].join('\n');
try{await navigator.clipboard.writeText(text);notify('Список скопирован! Вставьте его в чат Telegram.')}catch{window.prompt('Скопируйте сообщение для Telegram:',text)}
window.open(tg,'_blank','noopener,noreferrer');}
function card(p){const saved=fav.has(p.id);return `<article class="item"><div><div class="item-name">${escape(p.name)}</div><div class="prices">${escape(money(p))}</div></div><div class="item-actions"><button class="heart ${saved?'saved':''}" data-fav="${p.id}" aria-label="${saved?'Удалить из избранного':'В избранное'}" title="Избранное">${saved?'♥':'♡'}</button><button class="primary" data-buy="${p.id}">Купить ↗</button></div></article>`}
function render(){const query=$('search').value.trim().toLocaleLowerCase('ru'),platform=$('platform').value,kind=$('kind').value,sort=$('sort').value;
let result=products.filter(p=>(tab!=='fav'||fav.has(p.id))&&(platform==='all'||p.platform===platform)&&(kind==='all'||p.kind===kind)&&p.full.toLocaleLowerCase('ru').includes(query));
if(sort==='asc')result.sort((a,b)=>a.rub-b.rub);if(sort==='desc')result.sort((a,b)=>b.rub-a.rub);if(sort==='az')result.sort((a,b)=>a.name.localeCompare(b.name,'ru'));
$('catalog').innerHTML=result.length?result.map(card).join(''):'<div class="empty">Ничего не найдено. Попробуйте изменить фильтры.</div>';
$('count').textContent=`Найдено товаров: ${result.length} из ${products.length}`;$('fav-count').textContent=fav.size;
$('tab-all').classList.toggle('active',tab==='all');$('tab-fav').classList.toggle('active',tab==='fav');}
for(const id of ['search','platform','kind','sort'])$(id).addEventListener(id==='search'?'input':'change',render);
$('tab-all').addEventListener('click',()=>{tab='all';render()});$('tab-fav').addEventListener('click',()=>{tab='fav';render()});
$('send-list').addEventListener('click',()=>order([...fav].map(id=>byId.get(id)).filter(Boolean)));
document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
if(button.dataset.buy!==undefined){const p=byId.get(Number(button.dataset.buy));if(p)order([p]);}
if(button.dataset.fav!==undefined){const id=Number(button.dataset.fav);if(fav.has(id))fav.delete(id);else fav.add(id);try{localStorage.setItem('4ilgames-favs',JSON.stringify([...fav]))}catch{notify('Не удалось сохранить избранное в браузере')}render();}
if(button.dataset.find!==undefined){$('search').value=button.dataset.find;tab='all';$('platform').value='all';$('kind').value='all';render();$('search').scrollIntoView({behavior:'smooth',block:'center'});}});
if(data.featured.length){$('new-section').hidden=false;$('slider').innerHTML=data.featured.map(f=>{const p=byId.get(f.productId);return `<article class="slide"><img loading="lazy" src="${escape(f.image)}" alt="Обложка ${escape(f.title)}"><div class="slide-body"><h3>${escape(f.title)}</h3><p>${escape(money(p))}</p><button class="primary" data-buy="${p.id}">Купить ↗</button> <button data-find="${escape(f.title)}">Найти</button></div></article>`}).join('');}
for(const [id,direction] of [['prev',-1],['next',1]])$(id).addEventListener('click',()=>$('slider').scrollBy({left:direction*325,behavior:'smooth'}));
if(data.offers.length){$('offers-section').hidden=false;$('offers').innerHTML=data.offers.map(id=>card(byId.get(id))).join('');}
render();
})();
</script></body></html>'''

if __name__ == '__main__':
    main()
