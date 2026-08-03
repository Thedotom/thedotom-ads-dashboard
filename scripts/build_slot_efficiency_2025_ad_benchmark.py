from __future__ import annotations
import json, re
from pathlib import Path
import pandas as pd

ROOT=Path(r"D:\광고보고서\public_dashboard")
RAW=Path(r"D:\광고보고서\raw")
OUT=ROOT/"data"/"slot_efficiency_2025_ad_benchmark.json"
FILES=sorted(RAW.glob("naver_ads_2025_0?_01_*_daily_raw.xlsx"))

def num(s): return pd.to_numeric(s,errors="coerce").fillna(0)
def metrics(df):
    impressions=float(num(df["노출수"]).sum()); clicks=float(num(df["클릭수"]).sum())
    cost=float(num(df["총비용"]).sum()); conv=float(num(df["전환수"]).sum()); sales=float(num(df["전환매출"]).sum())
    return {"impressions":round(impressions),"clicks":round(clicks),"adCost":round(cost),"conversions":round(conv,2),"adSales":round(sales),
            "ctr":clicks/impressions if impressions else 0,"cpc":cost/clicks if clicks else 0,"cvr":conv/clicks if clicks else 0,
            "cpa":cost/conv if conv else 0,"roas":sales/cost if cost else 0}
frames=[]
for path in FILES:
    match=re.search(r"naver_ads_(2025)_(0[1-7])_",path.name)
    if not match: continue
    df=pd.read_excel(path); df["month"]=f"{match.group(1)}-{match.group(2)}"; frames.append(df)
all_df=pd.concat(frames,ignore_index=True)
monthly=[]
for month,df in all_df.groupby("month",sort=True): monthly.append({"month":month,**metrics(df)})
groups=[]
for key,label,mask,note,product_id in [
    ("all","전체 계정",pd.Series(True,index=all_df.index),"네이버 검색광고 전체 계정 기준",""),
    ("towel","수건 상품군",all_df["캠페인명"].astype(str).str.contains("쇼핑검색_더도톰_수건",na=False),"수건단품 슬롯의 비교 기준. 2025 원본에 상품 ID가 없어 캠페인명으로 매핑","4624494637"),
    ("joguman","조구만 광고군",all_df["캠페인명"].astype(str).str.contains("쇼핑검색_더도톰_조구만",na=False),"조구만 계열 참고치. 조구만고리수건 상품번호와 직접 일치하지 않음","12924495111"),
]:
    subset=all_df[mask]
    by_month=[]
    for month,df in subset.groupby("month",sort=True): by_month.append({"month":month,**metrics(df)})
    groups.append({"key":key,"label":label,"productId":product_id,"mappingNote":note,"totals":metrics(subset),"monthly":by_month})
payload={"period":{"start":"2025-01-01","end":"2025-07-31","months":7},"source":"Naver Search Ads API monthly raw exports","sourceFiles":[p.name for p in FILES],"updatedAt":pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),"mappingBasis":"2025 raw exports contain no product IDs; product-family comparisons use campaign-name mapping.","monthly":monthly,"groups":groups,"unmappedProducts":[{"productId":"4843121925","label":"세트모음전","reason":"2025 원본에서 직접 식별 가능한 전용 캠페인/상품 ID 없음"}]}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"files":len(FILES),"months":len(monthly),"total":groups[0]["totals"],"output":str(OUT)},ensure_ascii=False))
