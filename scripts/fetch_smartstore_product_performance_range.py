from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from fetch_smartstore_product_performance_browser import (
    STORES,
    build_driver,
    download_file,
    enter_report_frame,
    open_product_performance,
    select_date,
    select_product_dimension,
    switch_store,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--store", choices=["studio", "mura", "all"], default="all")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end date must not be earlier than start date")
    targets = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    store_keys = list(STORES) if args.store == "all" else [args.store]

    driver = build_driver(args.headless)
    outputs = []
    try:
        open_product_performance(driver)
        for store_key in store_keys:
            switch_store(driver, store_key)
            enter_report_frame(driver)
            for index, target in enumerate(targets):
                print(f"Collecting {store_key} {target}", flush=True)
                select_date(driver, target)
                if index == 0:
                    select_product_dimension(driver)
                outputs.append(str(download_file(driver, store_key, target)))
    finally:
        driver.quit()

    print(json.dumps({
        "startDate": str(start),
        "endDate": str(end),
        "files": outputs,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
