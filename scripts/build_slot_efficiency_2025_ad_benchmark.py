from __future__ import annotations
import json,re
from pathlib import Path
import pandas as pd
ROOT=Path(r"D:\광고보고서\public_dashboard"); RAW=Path(r"D:\광고보고서\raw"); OUT=ROOT/"data"/"slot_efficiency_2025_ad_benchmark.json"
CONFIG=Path(r"D:\광고보고서\state\naver_ads_api_accounts.json")

def num(s): return pd.to_numeric(s,errors="coerce").fillna(0)
def metrics(df):
    if df.empty: return {k:0 for k in ["impressions","clicks","adCost","conversions","adSales","ctr","cpc","cvr","cpa","roas"]}
    imp=float(num(df["노출수"]).sum()); clicks=float(num(df["클릭수"]).sum()); cost=float(num(df["총비용"]).sum()); conv=float(num(df["전환수"]).sum()); sales=float(num(df["전환매출"]).sum())
    return {"impressions":round(imp),"clicks":round(clicks),"adCost":round(cost),"conversions":round(conv,2),"adSales":round(sales),"ctr":clicks/imp if imp else 0,"cpc":cost/clicks if clicks else 0,"cvr":conv/clicks if clicks else 0,"cpa":cost/conv if conv else 0,"roas":sales/cost if cost else 0}
def latest_file(year,month):
    files=list(RAW.glob(f"naver_ads_{year}_{month:02d}_01_*_daily_raw.xlsx")); return max(files,key=lambda p:p.stat().st_mtime) if files else None
def build_year(year,account_names):
    frames=[]; source=[]
    for month in range(1,8):
        path=latest_file(year,month)
        if not path: continue
        df=pd.read_excel(path); df["month"]=f"{year}-{month:02d}"; frames.append(df); source.append(path.name)
    data=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    monthly=[{"month":m,**metrics(g)} for m,g in data.groupby("month",sort=True)] if not data.empty else []
    accounts=[]
    for name in account_names:
        subset=data[data["광고계정명"].astype(str)==name] if not data.empty else data
        accounts.append({"account":name,"totals":metrics(subset),"monthly":[{"month":m,**metrics(g)} for m,g in subset.groupby("month",sort=True)] if not subset.empty else []})
    groups=[]
    for key,label,token,note,pid in [("towel","수건 상품군","쇼핑검색_더도톰_수건","수건단품 슬롯 비교 기준. 상품 ID가 없어 캠페인명으로 매핑","4624494637"),("joguman","조구만 광고군","쇼핑검색_더도톰_조구만","조구만 계열 참고치. 조구만고리수건 상품번호와 직접 일치하지 않음","12924495111")]:
        subset=data[data["캠페인명"].astype(str).str.contains(token,na=False)] if not data.empty else data
        groups.append({"key":key,"label":label,"productId":pid,"mappingNote":note,"totals":metrics(subset),"monthly":[{"month":m,**metrics(g)} for m,g in subset.groupby("month",sort=True)] if not subset.empty else []})
    return {"year":year,"period":{"start":f"{year}-01-01","end":f"{year}-07-31","months":7},"sourceFiles":source,"totals":metrics(data),"monthly":monthly,"accounts":accounts,"groups":groups}
config=json.loads(CONFIG.read_text(encoding="utf-8-sig")); account_names=[a.get("name") for a in config.get("accounts",[]) if a.get("enabled")]
r2025=build_year(2025,account_names); r2026=build_year(2026,account_names)
def change(key):
    old=r2025["totals"][key]; new=r2026["totals"][key]
    return {"absolute":new-old,"rate":(new-old)/old if old else None}
comparison={k:change(k) for k in ["adCost","adSales","impressions","clicks","conversions","roas"]}
payload={"period":r2025["period"],"source":"Naver Search Ads API monthly raw exports","sourceFiles":r2025["sourceFiles"],"updatedAt":pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),"mappingBasis":"2025/2026 raw exports contain no product IDs; product-family comparisons use campaign-name mapping.","monthly":r2025["monthly"],"groups":[{"key":"all","label":"전체 계정","productId":"","mappingNote":"네이버 검색광고 전체 계정 기준","totals":r2025["totals"],"monthly":r2025["monthly"]},*r2025["groups"]],"unmappedProducts":[{"productId":"4843121925","label":"세트모음전","reason":"원본에서 직접 식별 가능한 전용 캠페인/상품 ID 없음"}],"reports":{"2025":r2025,"2026":r2026},"comparison2026vs2025":comparison,"accountNames":account_names}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"accounts":account_names,"2025":r2025["totals"],"2026":r2026["totals"],"comparison":comparison,"output":str(OUT)},ensure_ascii=False))
