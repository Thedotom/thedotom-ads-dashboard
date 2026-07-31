from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import apply_naver_ads_month as ads


def prepare(raw_path: Path) -> pd.DataFrame:
    frame = pd.read_excel(raw_path)
    brand_creative = (
        frame["캠페인명"].astype(str).str.contains("브랜드", na=False)
        & frame["소재 ID"].fillna("").astype(str).str.strip().ne("")
    )
    frame = frame.loc[~brand_creative].copy()
    for column in ads.METRICS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["날짜"] = frame["날짜"].astype(str).str[:10]
    frame["광고유형"] = frame["캠페인명"].map(ads.campaign_type)
    frame["키워드"] = frame["키워드"].where(frame["키워드"].notna(), None)
    frame["상품명"] = frame["상품명"].where(
        frame["상품명"].notna(), frame["소재명"]
    )
    shopping = frame["광고유형"] == "쇼핑검색"
    shop_frame = frame.loc[shopping]
    product_names = shop_frame.apply(
        lambda row: ads.product_label(row["상품명"])
        or ads.product_label(row["소재명"])
        or ads.clean(row["광고그룹명"]),
        axis=1,
    )
    frame.loc[shopping, "상품명"] = product_names
    for column in ["키워드", "소재명"]:
        labels = shop_frame[column].map(ads.product_label)
        frame.loc[shopping, column] = labels.where(labels.ne(""), product_names)
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args()

    frame = prepare(args.raw)
    target = args.data_dir / f"monthly-dashboard-{args.month}.json"
    data = json.loads(target.read_text(encoding="utf-8-sig"))

    account_rows = ads.aggregate(frame, ["광고계정명"])
    campaigns = ads.aggregate(frame, ["광고계정명", "광고유형", "캠페인명"])
    adgroups = ads.aggregate(
        frame, ["광고계정명", "광고유형", "캠페인명", "광고그룹명"]
    )
    details = ads.aggregate(
        frame,
        ["광고계정명", "광고유형", "캠페인명", "광고그룹명", "키워드", "상품명"],
    )
    for row in details:
        row.update(
            검색기기="공통",
            실제검색순위=None,
            순위확인시각="",
            순위메모="",
        )
        row["판단"] = (
            "확대후보"
            if ads.number(row.get("ROAS")) >= 5
            and ads.number(row.get("총비용")) >= 10000
            else "유지"
        )
        row["권장조치"] = (
            "효율 유지 시 예산 또는 입찰 소폭 확대"
            if row["판단"] == "확대후보"
            else "성과 추적"
        )

    account_cost_rows = []
    for account_name, account_frame in frame.groupby("광고계정명", dropna=False):
        weeks = [0, 0, 0, 0, 0]
        for date_text, value in account_frame.groupby("날짜")["총비용"].sum().items():
            weeks[ads.week_index(str(date_text))] += int(
                round(ads.number(value))
            )
        clean_name = ads.clean(account_name) or "계정 미상"
        account_cost_rows.append(
            {
                "name": f"네이버 광고 · {clean_name}",
                "accountName": clean_name,
                "weeks": weeks,
                "total": sum(weeks),
            }
        )
    account_cost_rows.sort(key=lambda row: row["total"], reverse=True)

    metrics = data.setdefault("totalSalesMetrics", {})
    existing = [
        row
        for row in metrics.get("autoAdCosts", [])
        if row.get("name") != "네이버 광고 자동수집"
        and not str(row.get("name", "")).startswith("네이버 광고 · ")
    ]
    metrics["autoAdCosts"] = account_cost_rows + existing
    combined = [
        sum(ads.number(row.get("weeks", [0] * 5)[index]) for row in metrics["autoAdCosts"])
        for index in range(5)
    ]
    metrics["autoAdCostTotal"] = {
        "name": "광고비 합계",
        "weeks": [ads.whole(value) for value in combined],
        "total": ads.whole(sum(combined)),
    }

    data["accountPerformance"] = account_rows
    data["campaigns"] = campaigns
    data["adgroups"] = adgroups
    data["keywordPerformance"] = details
    data["inspection"] = ads.build_inspection(details)
    data["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "accounts": [
                    {
                        "name": row["광고계정명"],
                        "cost": row["총비용"],
                        "revenue": row["전환매출"],
                    }
                    for row in account_rows
                ],
                "campaigns": len(campaigns),
                "adgroups": len(adgroups),
                "details": len(details),
                "totalCost": metrics["autoAdCostTotal"]["total"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
