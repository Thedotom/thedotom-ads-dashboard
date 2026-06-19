# Thedotom Ads Dashboard

네이버 광고비, 쇼핑검색 리워드 비용, 브랜드검색 계약, 검색 순위 트래픽 데이터를 통합해서 확인하는 더도톰 광고 운영 대시보드입니다.

## Files

- `index.html`: GitHub Pages에서 열리는 대시보드 화면
- `data/monthly-dashboard-latest.json`: 최신 월 데이터
- `data/monthly-dashboard-YYYY-MM.json`: 월별 대시보드 데이터

## Update Flow

1. 순위 수집 자동화가 `D:\자동화\rank_data.json`을 갱신합니다.
2. 광고 보고서 자동화가 대시보드 JSON을 다시 생성합니다.
3. `public_dashboard` 폴더 내용을 GitHub에 업로드하면 외부 링크에서 최신 데이터를 확인할 수 있습니다.
