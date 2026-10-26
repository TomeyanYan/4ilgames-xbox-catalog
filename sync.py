"""Copy Xbox game list from Telegraph, convert RUB prices to BYN, publish to owned Telegraph."""
import json
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE = "https://telegra.ph/Spisok-igr-1-12-14-3"
API = "https://api.telegra.ph/"
STATE = Path("state.json")
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "4ILGAMES-catalog-sync/1.0"})
PRICE = re.compile(r"(?<!\d)(\d[\d\s\u00a0]{0,9})\s*(?:₽|руб(?:\.|лей|ля)?|RUB)", re.I)


def get_source():
    r = HTTP.get(SOURCE, timeout=30)
    r.raise_for_status()
    article = BeautifulSoup(r.text, "html.parser").select_one("article")
    if article is None:
        raise RuntimeError("Source article not found")
    lines = []
    for el in article.find_all(["p", "h3", "h4", "li"]):
        if el.find_parent(["p", "h3", "h4", "li"]):
            continue
        text = el.get_text(" ", strip=True)
        if text:
            lines.append(text)
    if len(lines) < 50:
        raise RuntimeError(f"Suspiciously short source: {len(lines)} entries")
    return lines


def get_rate():
    r = HTTP.get("https://api.nbrb.by/exrates/rates/RUB?parammode=2", timeout=20)
    r.raise_for_status()
    data = r.json()
    rate = Decimal(str(data["Cur_OfficialRate"])) / Decimal(str(data["Cur_Scale"]))
    if not Decimal("0.001") < rate < Decimal("1"):
        raise RuntimeError("Invalid exchange rate")
    return rate, data.get("Date", "")[:10]


def convert(text, rate):
    def replacement(m):
        rub = Decimal(m.group(1).replace(" ", "").replace("\u00a0", ""))
        byn = (rub * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{byn:.2f} BYN"
    return PRICE.sub(replacement, text)


def split_nodes(nodes, byte_limit=43000):
    pages, page = [], []
    for node in nodes:
        proposed = page + [node]
        if len(json.dumps(proposed, ensure_ascii=False).encode("utf-8")) > byte_limit:
            if not page:
                raise RuntimeError("Single entry too large")
            pages.append(page)
            page = [node]
        else:
            page = proposed
    if page:
        pages.append(page)
    return pages


def publish(token, title, content, path=None):
    params = {"access_token": token, "title": title, "author_name": "4ILGAMES",
              "content": json.dumps(content, ensure_ascii=False), "return_content": "false"}
    r = HTTP.post(API + ("editPage/" + path if path else "createPage"), data=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph API error: {data.get('error')}")
    time.sleep(0.5)
    return data["result"]


def main():
    token = os.environ.get("TELEGRAPH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAPH_TOKEN GitHub secret")
    lines = get_source()
    rate, date = get_rate()
    nodes = [{"tag": "p", "children": [convert(line, rate)]} for line in lines]
    converted_count = sum(convert(line, rate) != line for line in lines)
    if converted_count < 30:
        raise RuntimeError(f"Only {converted_count} prices recognized; stopping")
    parts = split_nodes(nodes)
    if len(parts) > 40:
        raise RuntimeError("Unexpectedly large catalog")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    previous = state.get("parts", [])
    paths = []
    for i, content in enumerate(parts):
        result = publish(token, f"4ILGAMES | Xbox — часть {i+1}", content,
                         previous[i] if i < len(previous) else None)
        paths.append(result["path"])
        print("Published", result["url"])
    index = [
        {"tag": "p", "children": ["4ILGAMES — игры Xbox. Цены в BYN без наценки."]},
        {"tag": "p", "children": [f"Курс НБРБ: 1 RUB = {rate} BYN, дата курса: {date}."]},
        {"tag": "p", "children": ["Обновлено: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")]},
    ]
    for i, path in enumerate(paths):
        index.append({"tag": "p", "children": [{"tag": "a", "attrs": {"href": "https://telegra.ph/" + path},
                                                   "children": [f"Часть {i+1}"]}]})
    result = publish(token, "4ILGAMES | Каталог игр Xbox", index, state.get("index"))
    STATE.write_text(json.dumps({"index": result["path"], "parts": paths}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CATALOG:", result["url"], "entries:", len(lines), "converted:", converted_count)


if __name__ == "__main__":
    main()
