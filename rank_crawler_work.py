# -*- coding: utf-8 -*-
# =====================================================
# 네이버 순위 수집 v7
# - 하루 2회 (오전 morning / 오후 afternoon) 저장
# - 쇼핑검색: 네이버 Search API (썸네일 포함)
# - 파워링크: SA API 키워드 자동수집 + PC/모바일 분리 순위 확인
#   광고그룹 이름에 (M) → 모바일, (PC) → PC 로 분리
# 파일명: rank_crawler.py
# 실행법: py rank_crawler.py
# =====================================================

import time
import json
import os
import random
import hmac
import hashlib
import base64
import requests
import argparse
import tempfile
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By

try:
    from supabase import create_client as _sb_create
    _SUPABASE_OK = True
except ImportError:
    _SUPABASE_OK = False

# =====================================================
# ★★★ 설정 - 여기만 수정하면 됩니다 ★★★
# =====================================================

NAVER_CLIENT_ID     = "8GHhy2wNRwm2R00V36PV"
NAVER_CLIENT_SECRET = "5od49JPHqT"

SA_ACCOUNTS_PATH = r"D:\광고보고서\state\naver_ads_api_accounts.json"
with open(SA_ACCOUNTS_PATH, "r", encoding="utf-8-sig") as _sa_file:
    _sa_accounts = json.load(_sa_file).get("accounts", [])
_sa_account = next((item for item in _sa_accounts if item.get("enabled")), None)
if not _sa_account:
    raise RuntimeError(f"활성 네이버 광고 API 계정이 없습니다: {SA_ACCOUNTS_PATH}")
SA_ACCESS_LICENSE = str(_sa_account["api_key"])
SA_SECRET_KEY = str(_sa_account["secret_key"])
SA_CUSTOMER_ID = str(_sa_account["customer_id"])

POWERLINK_DOMAIN = "thedotom.com"
POWERLINK_BRAND  = "더도톰"
POWERLINK_CAPTURE_KEYWORDS = {"답례품", "돌답례품", "돌잔치답례품"}
POWERLINK_CAPTURE_DIR = r"D:\광고보고서\rank\search_captures"
POWERLINK_TARGETS = {
    "파워링크_더도톰_자사몰": ["thedotom.com"],
    "파워링크_더도톰_세부 키워드": ["thedotom.com"],
    "파워링크_더도톰스튜디오_스스": ["smartstore.naver.com/thedotomshop"],
}

SKIP_CAMPAIGN_KEYWORDS = ["브랜드검색", "파워컨텐츠"]

MORNING_CUTOFF_HOUR = 13

SA_API_BASE = "https://api.searchad.naver.com"
OUTPUT_DIR  = r"D:\광고보고서\rank"

SUPABASE_URL = "https://bdenaadzlrvdsgrtmnqu.supabase.co"
SUPABASE_KEY = "sb_publishable_I7UGILs1R6vxwX7AuPmLRw_sdY0-1Q9"

# =====================================================
# 쇼핑검색 키워드 + 상품ID 매핑
# =====================================================
SHOPPING_KEYWORDS = [
    # 상품 4624494637
    {"keyword": "돌잔치답례품",     "product_id": "4624494637"},
    {"keyword": "돌답례품",         "product_id": "4624494637"},
    {"keyword": "답례품",           "product_id": "4624494637"},
    {"keyword": "돌잔치수건",       "product_id": "4624494637"},
    {"keyword": "수건답례품",       "product_id": "4624494637"},
    {"keyword": "돌수건답례품",     "product_id": "4624494637"},
    {"keyword": "돌잔치선물",       "product_id": "4624494637"},
    {"keyword": "답례품수건",       "product_id": "4624494637"},
    {"keyword": "돌답례품수건",     "product_id": "4624494637"},
    {"keyword": "돌수건",           "product_id": "4624494637"},
    {"keyword": "돌잔치답례품수건", "product_id": "4624494637"},
    # 상품 4843121925
    {"keyword": "돌잔치답례품",         "product_id": "4843121925"},
    {"keyword": "돌답례품",             "product_id": "4843121925"},
    {"keyword": "답례품",               "product_id": "4843121925"},
    {"keyword": "돌잔치기념품",         "product_id": "4843121925"},
    {"keyword": "답례품세트",           "product_id": "4843121925"},
    {"keyword": "답례품핸드워시",       "product_id": "4843121925"},
    {"keyword": "답례품프리미엄세트",   "product_id": "4843121925"},
    {"keyword": "돌답례품세트",         "product_id": "4843121925"},
    {"keyword": "돌잔치답레품세트",     "product_id": "4843121925"},
    {"keyword": "핸드워시세트",         "product_id": "4843121925"},
    {"keyword": "돌답례품핸드워시세트", "product_id": "4843121925"},
    # 상품 12924495111
    {"keyword": "어린이집수건",     "product_id": "12924495111"},
    {"keyword": "고리수건",         "product_id": "12924495111"},
    {"keyword": "수건고리",         "product_id": "12924495111"},
    {"keyword": "어린이집고리수건", "product_id": "12924495111"},
    {"keyword": "어린이집손수건",   "product_id": "12924495111"},
    {"keyword": "어린이수건",       "product_id": "12924495111"},
    {"keyword": "아기어린이집수건", "product_id": "12924495111"},
    {"keyword": "유치원고리수건",   "product_id": "12924495111"},
    {"keyword": "어린이손수건",     "product_id": "12924495111"},
    {"keyword": "자수고리수건",     "product_id": "12924495111"},
    # 상품 13471936380 - 돌잔치 모바일 초대장 돌초대장 시안제공 간편수정 당일제작
    {"keyword": "모바일돌잔치초대장", "product_id": "13471936380"},
    {"keyword": "돌잔치초대장",       "product_id": "13471936380"},
    {"keyword": "돌초대장",           "product_id": "13471936380"},
    {"keyword": "돌잔치모바일초대장", "product_id": "13471936380"},
    {"keyword": "모바일돌초대장",     "product_id": "13471936380"},
    # 순위 관찰 상품 11562165854
    {"keyword": "돌잔치답례품",   "product_id": "11562165854"},
    {"keyword": "돌답례품",       "product_id": "11562165854"},
    {"keyword": "답례품",         "product_id": "11562165854"},
    {"keyword": "돌잔치수건",     "product_id": "11562165854"},
    {"keyword": "돌수건",         "product_id": "11562165854"},
    {"keyword": "조구만",         "product_id": "11562165854"},
    {"keyword": "돌답례품수건",   "product_id": "11562165854"},
    {"keyword": "돌수건답례품",   "product_id": "11562165854"},
    # 순위 관찰 상품 7444568862
    {"keyword": "꿀답례품",       "product_id": "7444568862"},
    {"keyword": "답례품꿀",       "product_id": "7444568862"},
    {"keyword": "꿀결혼답례품",   "product_id": "7444568862"},
    {"keyword": "돌잔치답례품",   "product_id": "7444568862"},
    {"keyword": "돌답례품",       "product_id": "7444568862"},
    {"keyword": "답례품",         "product_id": "7444568862"},
    {"keyword": "결혼답례품",     "product_id": "7444568862"},
    # 순위 관찰 상품 12047676813
    {"keyword": "결혼식답례품",   "product_id": "12047676813"},
    {"keyword": "결혼답례품",     "product_id": "12047676813"},
    {"keyword": "호두정과답례품", "product_id": "12047676813"},
    {"keyword": "답례품호두정과", "product_id": "12047676813"},
    {"keyword": "돌잔치답례품",   "product_id": "12047676813"},
    {"keyword": "무라호두정과",   "product_id": "12047676813"},
    # 무라 스토어 순위 관찰 상품 11943090047
    {"keyword": "무라호두정과",   "product_id": "11943090047"},
    {"keyword": "호두정과답례품", "product_id": "11943090047"},
    {"keyword": "답례품호두정과", "product_id": "11943090047"},
    {"keyword": "결혼답례품",     "product_id": "11943090047"},
    {"keyword": "결혼식답례품",   "product_id": "11943090047"},
    # 무라 스토어 순위 관찰 상품 11979458131
    {"keyword": "무라꿀",         "product_id": "11979458131"},
    {"keyword": "꿀답례품",       "product_id": "11979458131"},
    {"keyword": "답례품꿀",       "product_id": "11979458131"},
    {"keyword": "꿀결혼답례품",   "product_id": "11979458131"},
    {"keyword": "결혼답례품",     "product_id": "11979458131"},
    {"keyword": "돌잔치답례품",   "product_id": "11979458131"},
    # 순위 관찰 상품 11858377273
    {"keyword": "호텔수건",       "product_id": "11858377273"},
    {"keyword": "수건",           "product_id": "11858377273"},
    {"keyword": "40수수건",       "product_id": "11858377273"},
    {"keyword": "호텔타월",       "product_id": "11858377273"},
    {"keyword": "호텔수건40수",   "product_id": "11858377273"},
    {"keyword": "부드러운수건",   "product_id": "11858377273"},
    {"keyword": "호텔수건5+5",    "product_id": "11858377273"},
    {"keyword": "수건5+5",        "product_id": "11858377273"},
]

# =====================================================
# SA API 공통 함수
# =====================================================
def sa_signature(timestamp, method, path):
    msg = f"{timestamp}.{method}.{path}"
    sig = hmac.new(SA_SECRET_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(sig.digest()).decode()

def sa_headers(method, uri):
    ts = str(int(time.time() * 1000))
    path = uri.split("?")[0]
    return {
        "X-Timestamp":  ts,
        "X-API-KEY":    SA_ACCESS_LICENSE,
        "X-Customer":   SA_CUSTOMER_ID,
        "X-Signature":  sa_signature(ts, method, path),
        "Content-Type": "application/json; charset=UTF-8",
    }

def sa_get(uri):
    url = SA_API_BASE + uri
    resp = requests.get(url, headers=sa_headers("GET", uri), timeout=15)
    resp.raise_for_status()
    return resp.json()

# =====================================================
# 광고그룹 이름으로 디바이스 타입 판별
# =====================================================
def detect_device(group_name):
    """(M) → mobile, (PC) → pc, 둘 다 없으면 pc"""
    name_upper = group_name.upper()
    if "(M)" in name_upper:
        return "mobile"
    if "(PC)" in name_upper:
        return "pc"
    return "pc"  # 기본값

# =====================================================
# SA API로 파워링크 캠페인 키워드 자동수집 (PC/모바일 분리)
# =====================================================
DUAL_DEVICE_POWERLINK_CAMPAIGNS = {"파워링크_더도톰스튜디오_스스"}


def fetch_powerlink_keywords():
    """
    반환 형식:
    {
      "캠페인명": {
        "pc":     ["키워드1", "키워드2"],
        "mobile": ["키워드3", "키워드4"]
      }
    }
    """
    print("[API] 파워링크 캠페인 키워드 수집 중...")
    result = {}

    try:
        campaigns = sa_get("/ncc/campaigns")
        if not isinstance(campaigns, list):
            campaigns = campaigns.get("campaigns", [])

        for camp in campaigns:
            camp_id   = camp.get("nccCampaignId", "")
            camp_name = camp.get("name", camp_id)

            if any(skip in camp_name for skip in SKIP_CAMPAIGN_KEYWORDS):
                print(f"  [SKIP] 캠페인 제외: {camp_name}")
                continue
            if camp.get("userLock") or camp.get("status") in ("PAUSED", "STOPPED"):
                print(f"  [SKIP] 캠페인 OFF: {camp_name}")
                continue

            try:
                adgroups = sa_get(f"/ncc/adgroups?nccCampaignId={camp_id}")
                if not isinstance(adgroups, list):
                    adgroups = adgroups.get("adgroups", [])
            except Exception as e:
                print(f"  [WARN] 캠페인 {camp_name} 광고그룹 조회 실패: {e}")
                continue

            camp_kws = {"pc": [], "mobile": []}

            for group in adgroups:
                group_id   = group.get("nccAdgroupId", "")
                group_name = group.get("name", group_id)

                if group.get("userLock") or group.get("status") in ("PAUSED", "STOPPED"):
                    print(f"    [SKIP] 광고그룹 OFF: {group_name}")
                    continue

                devices = ["pc", "mobile"] if camp_name in DUAL_DEVICE_POWERLINK_CAMPAIGNS else [detect_device(group_name)]

                try:
                    kws = sa_get(f"/ncc/keywords?nccAdgroupId={group_id}")
                    if not isinstance(kws, list):
                        kws = kws.get("keywords", [])
                    for kw in kws:
                        if kw.get("userLock") or kw.get("status") in ("PAUSED", "STOPPED"):
                            continue
                        word = kw.get("keyword", "")
                        for device in devices:
                            if word and word not in camp_kws[device]:
                                camp_kws[device].append(word)
                except Exception as e:
                    print(f"  [WARN] 광고그룹 {group_id} 키워드 조회 실패: {e}")

            # 키워드가 하나라도 있는 캠페인만 저장
            if camp_kws["pc"] or camp_kws["mobile"]:
                result[camp_name] = camp_kws
                pc_cnt = len(camp_kws["pc"])
                mo_cnt = len(camp_kws["mobile"])
                print(f"  캠페인 [{camp_name}] PC {pc_cnt}개 / 모바일 {mo_cnt}개")

    except Exception as e:
        print(f"[ERR] 검색광고 API 오류: {e}")

    return result

# =====================================================
# 쇼핑검색 순위 + 썸네일
# =====================================================
def get_shopping_rank(keyword, product_id):
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": 100, "sort": "sim"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        for i, item in enumerate(items, 1):
            link = item.get("link", "") + item.get("productId", "") + item.get("mallProductId", "")
            if product_id in link:
                return {
                    "rank":  i,
                    "image": item.get("image", ""),
                    "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                }
        return {"rank": None, "image": "", "title": ""}
    except Exception as e:
        print(f"  [ERR] 쇼핑 API 오류 ({keyword}): {e}")
        return {"rank": "error", "image": "", "title": ""}

# =====================================================
# 파워링크 순위 - 브라우저 (PC / 모바일)
# =====================================================
def get_driver(device="pc"):
    last_error = None
    for attempt in range(1, 3):
        profile_dir = tempfile.mkdtemp(prefix=f"naver_rank_{device}_")
        options = ChromeOptions()
        options.add_argument("--lang=ko-KR")
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-background-networking")
        options.add_argument("--headless=new")

        if device == "mobile":
            options.add_argument("--window-size=390,844")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            )
        else:
            options.add_argument("--window-size=1366,768")

        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            driver._rank_profile_dir = profile_dir
            return driver
        except Exception as exc:
            last_error = exc
            print(f"  [WARN] Chrome driver start failed ({device}, attempt {attempt}/2): {exc}")
            shutil.rmtree(profile_dir, ignore_errors=True)
            time.sleep(3)
    raise last_error


def close_driver(driver):
    if not driver:
        return
    profile_dir = getattr(driver, "_rank_profile_dir", "")
    try:
        driver.quit()
    except Exception:
        pass
    if profile_dir:
        shutil.rmtree(profile_dir, ignore_errors=True)

def powerlink_targets_for_campaign(campaign_name):
    return POWERLINK_TARGETS.get(campaign_name, [POWERLINK_DOMAIN])


def _safe_capture_name(value):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value or "")).strip("_")[:90]


def archive_powerlink_capture(driver, keyword, device, campaign_name, cards):
    if keyword not in POWERLINK_CAPTURE_KEYWORDS:
        return ""
    captured_at = datetime.now()
    slot = "morning" if captured_at.hour < MORNING_CUTOFF_HOUR else "afternoon"
    folder = os.path.join(POWERLINK_CAPTURE_DIR, captured_at.strftime("%Y-%m-%d"), slot)
    os.makedirs(folder, exist_ok=True)
    stem = "__".join(_safe_capture_name(value) for value in (device, campaign_name, keyword))
    image_path = os.path.join(folder, stem + ".png")
    metadata_path = os.path.join(folder, stem + ".json")
    driver.save_screenshot(image_path)
    metadata = {
        "capturedAt": captured_at.strftime("%Y-%m-%d %H:%M:%S"),
        "slot": slot,
        "device": device,
        "campaign": campaign_name,
        "keyword": keyword,
        "searchUrl": driver.current_url,
        "image": image_path,
        "ads": cards,
    }
    with open(metadata_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return image_path


def get_powerlink_rank(driver, keyword, device="pc", target_domains=None, campaign_name=""):
    try:
        target_domains = target_domains or [POWERLINK_DOMAIN]
        url = f"https://search.naver.com/search.naver?where=nexearch&query={requests.utils.quote(keyword)}"
        driver.get(url)
        time.sleep(random.uniform(2.5, 4.0))

        cards = driver.execute_script(
            """
            const targets = arguments[0].map(v => String(v || "").toLowerCase());
            const device = arguments[1];
            const visible = el => {
              const style = window.getComputedStyle(el);
              const rect = el.getBoundingClientRect();
              return style.display !== "none" && style.visibility !== "hidden" && rect.width > 80 && rect.height > 30;
            };
            const hrefsOf = el => Array.from(el.querySelectorAll("a")).map(a => a.href || "").join(" ");
            const textOf = el => (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
            let raw = [];
            if (device === "mobile") {
              raw = Array.from(document.querySelectorAll("div[class*='mobilePowerLink'] li.bx"));
              if (!raw.length) raw = Array.from(document.querySelectorAll("li.bx.ext_desc, li.bx.sublink_img"));
            } else {
              raw = Array.from(document.querySelectorAll("div[class*='pcPowerLink'] li.lst"));
              if (!raw.length) raw = Array.from(document.querySelectorAll("ul.lst_ad > li, div.ad_area ul > li, div.ad_area li"));
            }
            raw = raw.filter(el => {
              const hrefs = hrefsOf(el);
              return visible(el)
                && el.querySelectorAll("a").length
                && (textOf(el).includes("광고") || hrefs.includes("adcr.naver.com") || hrefs.includes("ader.naver.com"));
            });
            const unique = [];
            raw.sort((a, b) => {
              const ar = a.getBoundingClientRect();
              const br = b.getBoundingClientRect();
              return ar.top - br.top || ar.left - br.left;
            }).forEach(el => {
              if (unique.some(existing => existing === el || existing.contains(el) || el.contains(existing))) return;
              unique.push(el);
            });
            return unique.map((el, index) => ({
              rank: index + 1,
              text: textOf(el),
              hrefs: hrefsOf(el),
              target: targets.some(target => (hrefsOf(el) + " " + textOf(el)).toLowerCase().includes(target))
            }));
            """,
            target_domains,
            device,
        )

        capture_path = archive_powerlink_capture(driver, keyword, device, campaign_name, cards)
        matched_rank = next(
            (int(card.get("rank") or 0) or None for card in cards if card.get("target")),
            None,
        )
        return {"rank": matched_rank, "ads": cards, "capture_path": capture_path}
    except Exception as e:
        print(f"  [ERR] 파워링크 오류 ({keyword}, {device}): {e}")
        return {"rank": "error", "ads": [], "capture_path": ""}

# =====================================================
# Supabase 업로드
# =====================================================
def push_to_supabase(today, slot, slot_data):
    if not _SUPABASE_OK:
        print("[Supabase] supabase 패키지 없음 → 건너뜀. pip install supabase")
        return
    try:
        client = _sb_create(SUPABASE_URL, SUPABASE_KEY)
        client.table("rank_data").upsert({
            "date":       today,
            "slot":       slot,
            "shopping":   slot_data.get("shopping", {}),
            "powerlink":  slot_data.get("powerlink", {}),
            "updated_at": datetime.now().isoformat(),
        }).execute()
        print(f"[Supabase] {today} [{slot}] 업로드 완료")
    except Exception as e:
        print(f"[Supabase] 업로드 실패 (로컬 저장은 완료): {e}")

# =====================================================
# 메인
# =====================================================
def parse_args():
    parser = argparse.ArgumentParser(description="네이버 순위 수집")
    parser.add_argument("--shopping-only", action="store_true", help="쇼핑검색 순위만 수집하고 종료")
    parser.add_argument("--powerlink-only", action="store_true", help="파워링크 순위만 수집")
    return parser.parse_args()


def save_rank_data(output_file, rank_data):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rank_data, f, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    slot  = "morning" if now.hour < MORNING_CUTOFF_HOUR else "afternoon"
    slot_label = "오전" if slot == "morning" else "오후"

    output_file = os.path.join(OUTPUT_DIR, "rank_data.json")

    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            rank_data = json.load(f)
    else:
        rank_data = {}

    if today not in rank_data:
        rank_data[today] = {}
    if slot not in rank_data[today]:
        rank_data[today][slot] = {"shopping": {}, "powerlink": {}}

    print(f"\n{'='*52}")
    print(f"  네이버 순위 수집 v7  |  {today} [{slot_label}]")
    print(f"{'='*52}\n")

    # ── 쇼핑검색 ──
    print(f"[쇼핑검색] 순위 수집 시작... ({slot_label})")
    shopping_results = rank_data[today][slot]["shopping"]
    product_image_cache = {}

    for item in ([] if args.powerlink_only else SHOPPING_KEYWORDS):
        kw  = item["keyword"]
        pid = item["product_id"]
        key = f"{kw}_{pid}"

        if key in shopping_results:
            print(f"  [{kw} / {pid}] 이미 수집됨 → SKIP")
            continue

        result = get_shopping_rank(kw, pid)
        image  = result["image"]
        if image and pid not in product_image_cache:
            product_image_cache[pid] = image

        shopping_results[key] = {
            "keyword":      kw,
            "product_id":   pid,
            "rank":         result["rank"],
            "image":        image or product_image_cache.get(pid, ""),
            "title":        result.get("title", ""),
            "collected_at": now.strftime("%H:%M:%S"),
        }

        rank_str = f"{result['rank']}위" if isinstance(result["rank"], int) else str(result["rank"])
        print(f"  [{kw} / {pid}] → {rank_str}")
        save_rank_data(output_file, rank_data)
        time.sleep(random.uniform(1.0, 2.0))

    if args.shopping_only:
        save_rank_data(output_file, rank_data)
        print(f"\n[완료] 쇼핑검색만 저장 완료 → {output_file}")
        push_to_supabase(today, slot, rank_data[today][slot])
        return

    # ── 파워링크 ──
    camp_keywords = fetch_powerlink_keywords()

    if not camp_keywords:
        print("[WARN] SA API에서 키워드를 가져오지 못했습니다.")
    else:
        powerlink_results = rank_data[today][slot]["powerlink"]

        # PC 수집
        pc_tasks = {camp: kws["pc"] for camp, kws in camp_keywords.items() if kws["pc"]}
        if pc_tasks:
            print(f"\n[파워링크 PC] 브라우저 순위 확인 시작...")
            driver_pc = None
            try:
                driver_pc = get_driver("pc")
                for camp_name, keywords in pc_tasks.items():
                    if camp_name not in powerlink_results:
                        powerlink_results[camp_name] = {}
                    if "pc" not in powerlink_results[camp_name]:
                        powerlink_results[camp_name]["pc"] = {}

                    target_domains = powerlink_targets_for_campaign(camp_name)
                    for kw in keywords:
                        observation = get_powerlink_rank(driver_pc, kw, "pc", target_domains, camp_name)
                        rank = observation["rank"]
                        powerlink_results[camp_name]["pc"][kw] = {
                            "rank": rank,
                            "collected_at": datetime.now().strftime("%H:%M:%S"),
                            "observed_ads": observation["ads"],
                            "capture_path": observation["capture_path"],
                        }
                        rank_str = f"{rank}위" if isinstance(rank, int) else ("미노출" if rank is None else str(rank))
                        print(f"  [{camp_name}][PC][{kw}] → {rank_str}")
                        time.sleep(random.uniform(2.0, 3.5))
            except Exception as exc:
                print(f"  [WARN] 파워링크 PC 순위 수집 실패. 쇼핑검색 데이터 저장은 계속 진행합니다: {exc}")
            finally:
                close_driver(driver_pc)

        # 모바일 수집
        mo_tasks = {camp: kws["mobile"] for camp, kws in camp_keywords.items() if kws["mobile"]}
        if mo_tasks:
            print(f"\n[파워링크 모바일] 브라우저 순위 확인 시작...")
            driver_mo = None
            try:
                driver_mo = get_driver("mobile")
                for camp_name, keywords in mo_tasks.items():
                    if camp_name not in powerlink_results:
                        powerlink_results[camp_name] = {}
                    if "mobile" not in powerlink_results[camp_name]:
                        powerlink_results[camp_name]["mobile"] = {}

                    target_domains = powerlink_targets_for_campaign(camp_name)
                    for kw in keywords:
                        observation = get_powerlink_rank(driver_mo, kw, "mobile", target_domains, camp_name)
                        rank = observation["rank"]
                        powerlink_results[camp_name]["mobile"][kw] = {
                            "rank": rank,
                            "collected_at": datetime.now().strftime("%H:%M:%S"),
                            "observed_ads": observation["ads"],
                            "capture_path": observation["capture_path"],
                        }
                        rank_str = f"{rank}위" if isinstance(rank, int) else ("미노출" if rank is None else str(rank))
                        print(f"  [{camp_name}][모바일][{kw}] → {rank_str}")
                        time.sleep(random.uniform(2.0, 3.5))
            except Exception as exc:
                print(f"  [WARN] 파워링크 모바일 순위 수집 실패. 쇼핑검색 데이터 저장은 계속 진행합니다: {exc}")
            finally:
                close_driver(driver_mo)

    save_rank_data(output_file, rank_data)
    print(f"\n[완료] {today} [{slot_label}] 저장 완료 → {output_file}")

    push_to_supabase(today, slot, rank_data[today][slot])

if __name__ == "__main__":
    main()


