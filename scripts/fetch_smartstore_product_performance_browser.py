from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


REPORT_ROOT = Path(r"D:\광고보고서")
PROFILE_DIR = REPORT_ROOT / "browser_profiles" / "smartstore_thedotom"
DOWNLOAD_DIR = REPORT_ROOT / "data" / "smartstore_sales"
DEBUG_DIR = REPORT_ROOT / "debug"
START_URL = "https://sell.smartstore.naver.com/"
ANALYTICS_URL = START_URL + "#/insight/store-analytics/sales"
STORES = {
    "studio": {"label": "더도톰스튜디오", "file": "thedotom"},
    "mura": {"label": "무라 MURA", "file": "mura"},
}


def wait(driver, seconds=30):
    return WebDriverWait(driver, seconds)


def click_text(driver, text_value, timeout=15):
    xpath = f"//*[self::a or self::button or self::span][normalize-space()='{text_value}']"
    element = wait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].click()", element)
    return element


def save_debug(driver, name):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = DEBUG_DIR / f"smartstore_{name}_{stamp}.html"
    png_path = DEBUG_DIR / f"smartstore_{name}_{stamp}.png"
    html_path.write_text(driver.page_source, encoding="utf-8")
    driver.save_screenshot(str(png_path))
    return str(html_path), str(png_path)


def complete_saved_login(driver):
    """Use the Naver account already saved in the dedicated Chrome profile."""
    is_quick_login = "네이버 아이디로 간편 로그인" in driver.page_source
    if urlparse(driver.current_url).hostname == "sell.smartstore.naver.com" and not is_quick_login:
        return
    try:
        quick_login = wait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(normalize-space(), '네이버 아이디로 간편 로그인')]")
            )
        )
        driver.execute_script("arguments[0].click()", quick_login)
    except TimeoutException:
        pass
    print("Waiting for the saved Naver account to enter SmartStore...")
    wait(driver, 300).until(
        lambda d: (urlparse(d.current_url).hostname == "sell.smartstore.naver.com"
                   and "네이버 아이디로 간편 로그인" not in d.page_source)
    )
    wait(driver, 40).until(lambda d: d.execute_script("return document.readyState") == "complete")
def open_product_performance(driver):
    driver.get(START_URL)
    wait(driver, 40).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(5)
    complete_saved_login(driver)
    for _ in range(3):
        driver.get(ANALYTICS_URL)
        wait(driver, 40).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(5)
        complete_saved_login(driver)
        if driver.find_elements(By.CSS_SELECTOR, "iframe[src*='/mg/insight/store-analytics/sales']"):
            return
    raise RuntimeError("sales analytics iframe did not load after login")

def enter_report_frame(driver):
    driver.switch_to.default_content()
    frame = wait(driver, 40).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='/mg/insight/store-analytics/sales']"))
    )
    driver.switch_to.frame(frame)
    wait(driver, 40).until(lambda d: "판매 리포트" in d.page_source)


def switch_store(driver, store_key):
    driver.switch_to.default_content()
    label = STORES[store_key]["label"]
    status = wait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".store")))
    if label in status.text:
        return
    click_text(driver, "스토어 이동", timeout=20)
    option = wait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, f"//*[contains(normalize-space(), '{label}') and not(.//*[contains(normalize-space(), '{label}')])]"))
    )
    driver.execute_script("arguments[0].click()", option)
    wait(driver, 40).until(lambda d: label in d.find_element(By.CSS_SELECTOR, ".store").text)
    time.sleep(3)
    driver.get(ANALYTICS_URL)
    wait(driver, 40).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(5)
    complete_saved_login(driver)

def calendar_months(driver):
    captions = driver.find_elements(By.CSS_SELECTOR, ".DayPicker-Caption")
    result = []
    for caption in captions:
        text_value = caption.text.strip().replace(" ", "")
        try:
            result.append((datetime.strptime(text_value, "%Y.%m.").date().replace(day=1), caption))
        except ValueError:
            continue
    return result


def select_date(driver, target):
    if target == date.today() - timedelta(days=1):
        click_text(driver, "1일", timeout=20)
    else:
        click_text(driver, "직접 선택", timeout=20)
        inputs = wait(driver, 20).until(lambda d: d.find_elements(By.CSS_SELECTOR, "input.date-picker-input"))
        if len(inputs) < 2:
            raise RuntimeError("date inputs not found")
        for index in (0, 1):
            inputs = driver.find_elements(By.CSS_SELECTOR, "input.date-picker-input")
            current = datetime.strptime(inputs[index].get_attribute("value").replace("(자동)", ""), "%Y.%m.%d").date()
            driver.execute_script("arguments[0].click()", inputs[index])
            wait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".react-datepicker")))
            delta = (target.year - current.year) * 12 + target.month - current.month
            selector = "[data-testid='DatePickerHeader__btnNextMonth']" if delta > 0 else "[data-testid='DatePickerHeader__btnPrevMonth']"
            for _ in range(abs(delta)):
                driver.execute_script("arguments[0].click()", driver.find_element(By.CSS_SELECTOR, selector))
                time.sleep(0.15)
            aria_prefix = f"Choose {target.year}년 {target.month}월 {target.day}일"
            day = wait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//div[contains(@class,'react-datepicker__day') and starts-with(@aria-label, '{aria_prefix}')]") )
            )
            driver.execute_script("arguments[0].click()", day)
            time.sleep(0.5)
    click_text(driver, "조회", timeout=20)
    wait(driver, 40).until(lambda d: (target.strftime("%Y-%m-%d") in d.page_source
                                     or target.strftime("%Y.%m.%d") in d.page_source))

def select_product_dimension(driver):
    click_text(driver, "상품", timeout=20)
    click_text(driver, "조회", timeout=20)
    wait(driver, 40).until(lambda d: "상품명" in d.page_source or "상품번호" in d.page_source)

def download_file(driver, store_key, target):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    before = {path.name for path in DOWNLOAD_DIR.glob("*.xlsx")}
    button = wait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(), '엑셀 만들기') or contains(normalize-space(), '파일 다운로드')]")))
    initial_label = button.text.strip()
    driver.execute_script("arguments[0].click()", button)
    if "엑셀 만들기" in initial_label:
        time.sleep(3)
        for label in ("파일 다운로드", "엑셀 다운로드", "다운로드"):
            try:
                click_text(driver, label, timeout=10)
                break
            except TimeoutException:
                continue
    deadline = time.time() + 180
    next_retry = time.time() + 30
    downloaded = None
    while time.time() < deadline:
        candidates = [
            path
            for path in DOWNLOAD_DIR.glob("*.xlsx")
            if path.name not in before and not path.with_suffix(path.suffix + ".crdownload").exists()
        ]
        if candidates:
            downloaded = max(candidates, key=lambda path: path.stat().st_mtime)
            break
        if time.time() >= next_retry:
            retry_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(normalize-space(), '엑셀 만들기') or contains(normalize-space(), '파일 다운로드')]",
            )
            if retry_buttons:
                driver.execute_script("arguments[0].click()", retry_buttons[0])
            next_retry = time.time() + 30
        time.sleep(1)
    if downloaded is None:
        raise RuntimeError("download did not complete within 90 seconds")
    target_path = DOWNLOAD_DIR / (
        f"smartstore_product_sales_{STORES[store_key]['file']}_{target:%Y-%m-%d}.xlsx"
    )
    if target_path.exists():
        target_path.unlink()
    downloaded.replace(target_path)
    return target_path


def build_driver(headless):
    options = Options()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--window-size=1600,1000")
    if headless:
        options.add_argument("--headless=new")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(DOWNLOAD_DIR),
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True,
        },
    )
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(DOWNLOAD_DIR)},
    )
    return driver


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=(date.today() - timedelta(days=1)).isoformat())
    parser.add_argument("--store", choices=["studio", "mura", "all"], default="all")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    target = datetime.strptime(args.date, "%Y-%m-%d").date()
    store_keys = list(STORES) if args.store == "all" else [args.store]
    driver = build_driver(args.headless)
    outputs = []
    try:
        open_product_performance(driver)
        for store_key in store_keys:
            switch_store(driver, store_key)
            enter_report_frame(driver)
            select_date(driver, target)
            select_product_dimension(driver)
            outputs.append(str(download_file(driver, store_key, target)))
    except Exception:
        print(json.dumps({"debug": save_debug(driver, "failure")}, ensure_ascii=False))
        raise
    finally:
        driver.quit()
    print(json.dumps({"date": str(target), "files": outputs}, ensure_ascii=False))


if __name__ == "__main__":
    main()

























