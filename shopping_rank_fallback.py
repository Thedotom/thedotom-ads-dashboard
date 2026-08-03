import importlib.util
import json
import math
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

CRAWLER = Path(r"D:\광고보고서\rank\rank_crawler.py")
RANK_DATA = Path(r"D:\광고보고서\rank\rank_data.json")
OUTPUT_DIR = Path("data")
WORKERS = 8

spec = importlib.util.spec_from_file_location("rank_crawler", CRAWLER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
items = list(module.SHOPPING_KEYWORDS)
lock = threading.Lock()


def make_driver():
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument("--headless=new")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-background-networking")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(15)
    return driver


def check_chunk(chunk):
    driver = make_driver()
    results = []
    try:
        for item in chunk:
            keyword = item["keyword"]
            product_id = item["product_id"]
            url = (
                "https://search.naver.com/search.naver?where=nexearch&query="
                + urllib.parse.quote(keyword)
            )
            result = {
                "keyword": keyword,
                "productId": product_id,
                "rank": None,
                "status": "4위 밖",
                "image": "",
                "title": "",
            }
            try:
                driver.get(url)
                time.sleep(1.4)
                if "접속이 일시적으로 제한" in driver.page_source:
                    result["status"] = "접속 제한"
                else:
                    links = driver.find_elements(
                        "css selector", f"[href*='/products/{product_id}']"
                    )
                    if links:
                        product_li = links[-1].find_element("xpath", "ancestor::li[1]")
                        parent = product_li.find_element("xpath", "..")
                        siblings = parent.find_elements("xpath", "./li")
                        result["rank"] = siblings.index(product_li) + 1
                        result["status"] = "노출"
                        result["title"] = (links[-1].text or "").strip()
                        images = product_li.find_elements("css selector", "img")
                        if images:
                            result["image"] = images[0].get_attribute("src") or images[0].get_attribute("data-src") or ""
            except Exception as exc:
                result["status"] = "확인 오류"
                result["error"] = str(exc)[:160]
            results.append(result)
            with lock:
                print(
                    f"[{len(results):02d}/{len(chunk):02d}] "
                    f"{keyword} / {product_id}: "
                    f"{result['rank'] or '-'} {result['status']}",
                    flush=True,
                )
    finally:
        driver.quit()
    return results


chunks = [[] for _ in range(min(WORKERS, len(items)))]
for index, item in enumerate(items):
    chunks[index % len(chunks)].append(item)

all_results = []
with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
    futures = [executor.submit(check_chunk, chunk) for chunk in chunks]
    for future in as_completed(futures):
        all_results.extend(future.result())

order = {
    (item["keyword"], item["product_id"]): index for index, item in enumerate(items)
}
all_results.sort(key=lambda row: order[(row["keyword"], row["productId"])])
now = datetime.now()
today = now.strftime("%Y-%m-%d")
slot = "morning" if now.hour < module.MORNING_CUTOFF_HOUR else "afternoon"
payload = {
    "checkedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
    "source": "naver_integrated_search",
    "scope": "top4",
    "results": all_results,
}
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
output = OUTPUT_DIR / f"current-shopping-top4-{today}-{slot}.json"
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
rank_data = json.loads(RANK_DATA.read_text(encoding="utf-8-sig")) if RANK_DATA.exists() else {}
product_metadata = {}
for date_key in sorted(rank_data):
    for slot_name in ("morning", "afternoon"):
        for value in rank_data.get(date_key, {}).get(slot_name, {}).get("shopping", {}).values():
            product_id = str(value.get("product_id") or "")
            if not product_id:
                continue
            metadata = product_metadata.setdefault(product_id, {"image": "", "title": ""})
            if value.get("image"):
                metadata["image"] = value["image"]
            if value.get("title"):
                metadata["title"] = value["title"]
confirmed_ranks = {}
for date_key in sorted(rank_data):
    for slot_name in ("morning", "afternoon"):
        for key, value in rank_data.get(date_key, {}).get(slot_name, {}).get("shopping", {}).items():
            if isinstance(value.get("rank"), int) and value.get("source") != "naver_integrated_search":
                confirmed_ranks[key] = {"rank": value["rank"], "date": date_key, "slot": slot_name}

current_month = today[:7]
for date_key in sorted(rank_data):
    if not date_key.startswith(current_month):
        continue
    for slot_name in ("morning", "afternoon"):
        for key, value in rank_data.get(date_key, {}).get(slot_name, {}).get("shopping", {}).items():
            metadata = product_metadata.get(str(value.get("product_id") or ""), {})
            if not value.get("image"):
                value["image"] = metadata.get("image", "")
            if not value.get("title"):
                value["title"] = metadata.get("title", "")
            confirmed = confirmed_ranks.get(key, {})
            value["last_known_rank"] = confirmed.get("rank")
            value["last_known_date"] = confirmed.get("date", "")
            value["last_known_slot"] = confirmed.get("slot", "")

slot_data = rank_data.setdefault(today, {}).setdefault(slot, {"shopping": {}, "powerlink": {}})
shopping = slot_data.setdefault("shopping", {})
status_rank = {"4위 밖": "outside_top4", "접속 제한": "blocked", "확인 오류": "error"}
for row in all_results:
    key = f"{row['keyword']}_{row['productId']}"
    previous = shopping.get(key, {})
    metadata = product_metadata.get(row["productId"], {})
    confirmed = confirmed_ranks.get(key, {})
    shopping[key] = {
        "keyword": row["keyword"], "product_id": row["productId"],
        "rank": row["rank"] if row["rank"] is not None else status_rank.get(row["status"], "error"),
        "status": row["status"], "scope": "top4", "source": "naver_integrated_search",
        "image": row.get("image") or previous.get("image") or metadata.get("image", ""),
        "title": row.get("title") or previous.get("title") or metadata.get("title", ""),
        "last_known_rank": confirmed.get("rank"),
        "last_known_date": confirmed.get("date", ""),
        "last_known_slot": confirmed.get("slot", ""),
        "collected_at": now.strftime("%H:%M:%S"),
    }
RANK_DATA.write_text(json.dumps(rank_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"SAVED {output}", flush=True)
print(f"UPDATED {RANK_DATA} {today} {slot}", flush=True)