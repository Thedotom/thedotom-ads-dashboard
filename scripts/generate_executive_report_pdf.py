from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'/'pdf'/'더도톰_2026_1-7월_광고_슬롯_대표보고서.pdf'
report=json.loads((ROOT/'data'/'executive-report-2026-01-07.json').read_text(encoding='utf-8-sig'))
ga4e=json.loads((ROOT/'data'/'executive-ga4-evidence-2026-06-07.json').read_text(encoding='utf-8-sig'))
channels=json.loads((ROOT/'data'/'executive-channel-efficiency-2026-06-07.json').read_text(encoding='utf-8-sig'))
dash=json.loads((ROOT/'data'/'monthly-dashboard-2026-08.json').read_text(encoding='utf-8-sig'))
dash_month=json.loads((ROOT/'data'/'monthly-dashboard-2026-07.json').read_text(encoding='utf-8-sig'))
mapping=json.loads((ROOT/'data'/'shopping-product-mapping.json').read_text(encoding='utf-8-sig'))
power=json.loads((ROOT/'data'/'powerlink-creative-config.json').read_text(encoding='utf-8-sig'))
pdfmetrics.registerFont(TTFont('Malgun',r'C:\Windows\Fonts\malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunB',r'C:\Windows\Fonts\malgunbd.ttf'))
NAVY=colors.HexColor('#0F172A'); BLUE=colors.HexColor('#4865F4'); AMBER=colors.HexColor('#F59E0B'); PALE=colors.HexColor('#F8FAFC'); LINE=colors.HexColor('#E2E8F0'); SLATE=colors.HexColor('#64748B')
S={
 'title':ParagraphStyle('title',fontName='MalgunB',fontSize=25,leading=34,textColor=colors.white),
 'sub':ParagraphStyle('sub',fontName='Malgun',fontSize=10,leading=17,textColor=colors.HexColor('#CBD5E1')),
 'h1':ParagraphStyle('h1',fontName='MalgunB',fontSize=19,leading=25,textColor=NAVY,spaceAfter=10),
 'h2':ParagraphStyle('h2',fontName='MalgunB',fontSize=13,leading=18,textColor=NAVY,spaceBefore=7,spaceAfter=7),
 'body':ParagraphStyle('body',fontName='Malgun',fontSize=8.7,leading=14,textColor=colors.HexColor('#334155')),
 'small':ParagraphStyle('small',fontName='Malgun',fontSize=7,leading=9,textColor=NAVY),
 'smallb':ParagraphStyle('smallb',fontName='MalgunB',fontSize=7,leading=9,textColor=NAVY),
 'smallw':ParagraphStyle('smallw',fontName='MalgunB',fontSize=7,leading=9,textColor=colors.white),
 'klabel':ParagraphStyle('klabel',fontName='MalgunB',fontSize=8,leading=11,textColor=SLATE,alignment=1),
 'kpi':ParagraphStyle('kpi',fontName='MalgunB',fontSize=14,leading=19,textColor=NAVY,alignment=1),
}
def P(x,s='body'): return Paragraph(str(x),S[s])
def money(x): return f'{int(round(float(x or 0))):,}원'
def pct(x): return f'{float(x or 0)*100:,.1f}%'
def mult(x): return f'{float(x or 0):,.1f}배'
def styled_table(data,widths,header=True):
 t=Table(data,colWidths=widths,repeatRows=1 if header else 0)
 rules=[('GRID',(0,0),(-1,-1),.4,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE])]
 if header: rules += [('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white)]
 t.setStyle(TableStyle(rules)); return t
def line_chart(rows):
 d=Drawing(470,205); c=HorizontalLineChart(); c.x=45;c.y=35;c.width=395;c.height=135
 c.data=[[float(r.get('mer') or 0) for r in rows]]
 c.categoryAxis.categoryNames=[r['month'][5:]+'월' for r in rows]; c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0
 c.lines[0].strokeColor=BLUE;c.lines[0].strokeWidth=2;c.lines[1].strokeColor=AMBER;c.lines[1].strokeWidth=2;d.add(c)
 d.add(String(205,8,'실제 매출 MER',fontName='Malgun',fontSize=8,fillColor=BLUE));return d
def slot_chart(periods):
 sums={}
 for r in periods:
  if r.get('isComplete'): sums[r.get('product','기타')]=sums.get(r.get('product','기타'),0)+float((r.get('during') or {}).get('sales') or 0)/100000000
 d=Drawing(470,205);c=VerticalBarChart();c.x=55;c.y=40;c.width=370;c.height=135;c.data=[list(sums.values())];c.categoryAxis.categoryNames=list(sums);c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0;c.bars[0].fillColor=BLUE;c.bars[0].strokeColor=BLUE;d.add(c);d.add(String(210,8,'완료 구간 집계 매출 (억원)',fontName='Malgun',fontSize=8,fillColor=SLATE));return d
def footer(canvas,doc):
 canvas.saveState();canvas.setStrokeColor(LINE);canvas.line(18*mm,14*mm,192*mm,14*mm);canvas.setFont('Malgun',7);canvas.setFillColor(SLATE);canvas.drawString(18*mm,9*mm,'더도톰 2026년 1~7월 광고·슬롯 보고서');canvas.drawRightString(192*mm,9*mm,str(doc.page));canvas.restoreState()
def build():
 OUT.parent.mkdir(parents=True,exist_ok=True); periods=sorted(dash['slotEfficiency']['periods'],key=lambda x:x.get('startDate','')); ss=dash['slotEfficiency']['summary']; groups=power.get('groups',[]); kws=[k for g in groups for k in g.get('keywords',[])]; off=[k for k in kws if k.get('status')!='운영 가능']; goff=[g for g in groups if g.get('campaignStatus')!='운영 가능' or g.get('adgroupStatus')!='운영 가능']
 map_rows=[r for r in mapping.get('rows',[]) if r.get('status') == 'ON' and str(r.get('productId')) != '6052815173']
 product_sales={}
 for row in (dash_month.get('dailyProductPerformance',{}).get('rows',[]) or []):
  pid=str(row.get('productId') or '')
  if not pid: continue
  item=product_sales.setdefault(pid,{'sales':0,'orders':0,'refunds':0})
  item['sales']+=float(row.get('dailySales') or 0); item['orders']+=float(row.get('orders') or 0); item['refunds']+=float(row.get('refundAmount') or 0)
 ad_rows=dash_month.get('keywordPerformance',[]) or []
 map_summary=[]
 for pid in sorted({str(r.get('productId')) for r in map_rows}):
  linked=[r for r in map_rows if str(r.get('productId'))==pid]; groups={str(r.get('adgroup') or '') for r in linked}
  ads=[r for r in ad_rows if str(r.get('광고그룹명') or '') in groups]
  cost=sum(float(r.get('총비용') or 0) for r in ads); revenue=sum(float(r.get('전환매출') or 0) for r in ads); actual=product_sales.get(pid,{'sales':0,'orders':0,'refunds':0})
  map_summary.append({'productName':linked[0].get('productName',''),'productId':pid,'groups':', '.join(sorted(groups-{''})),'cost':cost,'revenue':revenue,'roas':revenue/cost if cost else 0,'sales':actual['sales'],'orders':actual['orders'],'refunds':actual['refunds']})
 map_summary.sort(key=lambda x:x['sales'],reverse=True)
 slot_by_month={}
 for r in periods: slot_by_month[r['startDate'][:7]]=slot_by_month.get(r['startDate'][:7],0)+float(r.get('slotCost') or 0)
 monthly=[]
 for r in report['monthly']:
  row=dict(r);row['slotCost']=slot_by_month.get(row['month'],0);row['marketingCost']=max(0,float(row['totalMarketingCost'])-row['slotCost']);row['marketingCostRate']=row['marketingCost']/row['actualSales'] if row['actualSales'] else 0;row['mer']=row['actualSales']/row['marketingCost'] if row['marketingCost'] else 0;monthly.append(row)
 report_slot_cost=sum(r['slotCost'] for r in monthly);marketing_cost=float(report['totalMarketingCost'])-report_slot_cost;marketing_rate=marketing_cost/report['actualSales'];report_mer=report['actualSales']/marketing_cost
 doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=19*mm,title='더도톰 2026년 1~7월 광고·슬롯 보고서',author='더도톰'); story=[]
 cover=Table([[P('2026년 1~7월<br/>광고·슬롯 보고서','title')],[P('실제 매출·광고비·GA4 광고 유입 후 구매를 연결해 광고 중단 위험을 점검하고,<br/>유지·축소·중단 판단에 필요한 지표와 비교 기준을 제시합니다.','sub')]],colWidths=[174*mm],rowHeights=[72*mm,52*mm]);cover.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#172554')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),15*mm)]));story += [Spacer(1,28*mm),cover,Spacer(1,13*mm),P('보고 기간  2026.01.01 - 2026.07.31','h2'),P('슬롯 운영 일정  2026.05.22 - 2026.08.09'),PageBreak()]
 story += [P('1. 경영 요약','h1')]
 kd=[[P(x,'klabel') for x in ['실제 전체 매출','광고·마케팅비','마케팅비율','실제 매출 MER']],[P(money(report['actualSales']),'kpi'),P(money(marketing_cost),'kpi'),P(pct(marketing_rate),'kpi'),P(mult(report_mer),'kpi')]];kt=Table(kd,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);kt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE')]));story += [kt,Spacer(1,8*mm),P('보고서 결론','h2')]
 conclusions=[('광고 판단','검색광고 유지·확대·축소 여부는 키워드별 실제 상품매출·비용·GA4 구매 연결을 기준으로 대표님 결정'),('7월 GA4 근거',f"검색광고 유입 후 구매 매출 {money(ga4e['july']['paidSearchRevenue'])} · 자사몰 구매 매출의 {pct(ga4e['july']['paidSearchRevenueShare'])}"),('실제 효율 중심',f"슬롯 제외 누적 실제 MER {mult(report_mer)}, 마케팅비율 {pct(marketing_rate)}"),('중단 검증','7일 단위 축소 후 광고비 절감액과 실제 매출 감소액을 비교 · 손실이 크면 복원')];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in conclusions],[36*mm,138*mm],False),PageBreak()]
 story += [P('2. 1~7월 월별 성과','h1'),line_chart(monthly)]
 md=[[P(x,'smallw') for x in ['월','실제 매출','광고·마케팅비','슬롯비','비용률','실제 MER']]]
 for r in monthly: md.append([P(r['month'][5:]+'월','small'),P(money(r['actualSales']),'small'),P(money(r['marketingCost']),'small'),P(money(r['slotCost']),'small'),P(pct(r['marketingCostRate']),'small'),P(mult(r['mer']),'small')])
 story += [styled_table(md,[16*mm,38*mm,34*mm,26*mm,28*mm,32*mm]),Spacer(1,7*mm),P('해석','h2'),P('월별 성과는 실제 전체 매출과 실제 집행비만 사용했습니다. 마케팅비와 실제 매출 MER에서는 슬롯비를 제외했으며, 하반기 예산 판단은 실제 매출 MER와 비용률, GA4 광고 유입 구매를 우선 기준으로 삼습니다.'),PageBreak()]
 story += [P('3. 파워링크·쇼핑검색 운영 효율','h1'),P('비교 기간  2026.06.01 - 2026.07.31  |  실제 광고비·노출·클릭 기준'),Spacer(1,5*mm)]
 ch={r['channel']:r for r in channels['operational']}; pl=ch['파워링크']; sh=ch['쇼핑검색']; sh['adRoas']=sh['platformAttributedSales']/sh['adCost'] if sh['adCost'] else 0; cg=channels['ga4']
 cd=[[P(x,'smallw') for x in ['월','광고 유형','광고비','노출','클릭','CTR','CPC','GA4 구매 연결']]]
 for r in channels['monthly']:
  ga4_text=f"{int(r['ga4Sessions']):,}세션 · {int(r['ga4Transactions']):,}건 · {money(r['ga4PurchaseRevenue'])}" if r['channel']=='파워링크' else r['ga4Status']
  cd.append([P(r['month'][5:]+'월','small'),P(r['channel'],'smallb'),P(money(r['adCost']),'small'),P(f"{int(r['impressions']):,}",'small'),P(f"{int(r['clicks']):,}",'small'),P(pct(r['ctr']),'small'),P(money(r['cpc']),'small'),P(ga4_text+('<br/>'+r['ga4Status'] if r['channel']=='파워링크' else ''),'small')])
 for r in channels['operational']:
  ga=cg['powerlink'] if r['channel']=='파워링크' else None
  ga4_text=f"{int(ga['sessions']):,}세션 · {int(ga['transactions']):,}건 · {money(ga['purchaseRevenue'])}" if ga else '분리 측정 미확인'
  cd.append([P('합계','smallb'),P(r['channel'],'smallb'),P(money(r['adCost']),'smallb'),P(f"{int(r['impressions']):,}",'small'),P(f"{int(r['clicks']):,}",'small'),P(pct(r['ctr']),'small'),P(money(r['cpc']),'small'),P(ga4_text,'small')])
 story += [styled_table(cd,[12*mm,21*mm,27*mm,23*mm,18*mm,15*mm,22*mm,36*mm]),Spacer(1,7*mm),P('채널별 해석','h2')]
 channel_notes=[('1. 네이버 쇼핑검색 광고 지표',f"1~7월 광고비 {money(sh['adCost'])} · 클릭 {int(sh['clicks']):,}회 · 네이버 전환매출 {money(sh['platformAttributedSales'])} · 광고 ROAS {mult(sh['adRoas'])}."),('2. 연결상품 실제 성과',"매핑된 스마트스토어 상품별 7월 실제 매출·주문수는 아래 표에 표시했습니다. 광고그룹이 여러 개면 광고비는 합산하고 상품매출은 한 번만 집계했습니다."),('3. 대표님 판단 지표','네이버 전환매출과 스마트스토어 실제 매출은 합산하지 않습니다. 광고비/실매출, 주문수 추이, 환불액, GA4 구매 연결을 함께 보고 예산 유지·조정 여부를 대표님이 결정합니다.'),('4. 데이터 범위','네이버 전환매출은 플랫폼 귀속 기준이고 스마트스토어 실제 매출은 상품 판매 기준입니다. 두 수치의 차이는 측정 기준 차이로 해석합니다.')]
 mapping_table=[[P(x,'smallw') for x in ['연결 본상품','상품 ID','광고그룹','광고비','네이버 전환매출','광고 ROAS','1~7월 실제 매출','주문수']]]
 for r in map_summary: mapping_table.append([P(r['productName'],'small'),P(r['productId'],'small'),P(r['groups'],'small'),P(money(r['cost']),'small'),P(money(r['revenue']),'small'),P(mult(r['roas']),'small'),P(money(r['sales']),'small'),P(str(int(r['orders'])),'small')])
 story += [styled_table(mapping_table,[42*mm,24*mm,34*mm,22*mm,27*mm,20*mm,27*mm,18*mm]),Spacer(1,4*mm),P('상품 연결 기준','h2'),P('쇼핑검색 광고그룹을 스마트스토어 상품 ID로 연결해 광고 성과와 7월 실제 상품매출을 함께 표시했습니다. 동일 상품에 여러 광고그룹이 연결된 경우 광고비는 합산하고 상품매출은 중복 집계하지 않았습니다.'),Spacer(1,7*mm),P('현재 결론','h2'),P('<b>대표님은 네이버 광고 지표와 연결상품 실제 성과를 함께 확인한 뒤 예산 유지·조정 여부를 결정합니다.</b>'),PageBreak()]
 story += [P('4. GA4 기반 광고 유입·구매 효과','h1'),P('관측 기간  2026.06.19 - 2026.07.31  |  태그가 설치된 자사몰 기준'),Spacer(1,5*mm)]
 gs=ga4e['summary']; gj=ga4e['july']
 gk=[[P(x,'klabel') for x in ['검색광고 유입','검색광고 유입 구매','유입 후 구매 매출','7월 매출 비중']],[P(f"{int(gs['paidSearchSessions']):,}세션",'kpi'),P(f"{int(gs['paidSearchTransactions']):,}건",'kpi'),P(money(gs['paidSearchRevenue']),'kpi'),P(pct(gj['paidSearchRevenueShare']),'kpi')]]
 gt=Table(gk,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);gt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
 story += [gt,Spacer(1,7*mm),P('7월 광고 중단 판단','h2')]
 evidence=[('확인된 효과',f"7월 자사몰 GA4 구매 매출 {money(gj['purchaseRevenue'])} 중 검색광고 유입 후 구매 매출은 {money(gj['paidSearchRevenue'])}으로 {pct(gj['paidSearchRevenueShare'])}입니다."),('전면 중단 위험',f"검색광고 유입 {int(gj['paidSearchSessions']):,}세션과 구매 {int(gj['paidSearchTransactions']):,}건의 접점이 동시에 사라질 수 있습니다."),('대표 결정 사항','광고 유지·확대·축소 여부는 고효율 키워드의 실제 상품매출과 비용 지표를 확인한 뒤 대표님이 결정할 사안입니다.'),('검증 방법','7일 단위로 예산을 줄인 뒤 광고비 절감액과 실제 매출 감소액을 비교하고, 매출 손실이 더 큰 경우 복원 여부를 대표님이 결정합니다.')]
 story += [styled_table([[P(a,'smallb'),P(b)] for a,b in evidence],[36*mm,138*mm],False),Spacer(1,7*mm),P('수치 해석 범위','h2')]
 limits=[('자사몰 한정','GA4 값에는 스마트스토어·무라 매출이 포함되지 않습니다.'),('관측값','검색광고 유입 후 구매 매출이며 광고가 없었을 때의 순증매출을 직접 증명하지는 않습니다.'),('6월 부분 집계','구매 추적이 확인되는 6월 19일부터만 포함했습니다.'),('UTM 신뢰도',f"7월 UTM 분류율은 {pct(gj['utmMappingCoverage'])}로 유입 구분의 누락은 제한적입니다.")]
 story += [styled_table([[P(a,'smallb'),P(b)] for a,b in limits],[36*mm,138*mm],False),Spacer(1,7*mm),P('의사결정 문장','h2'),P('<b>광고를 전부 또는 일부 조정할지는 대표님 결정 사항이며, 실제 매출·주문·광고비 변화가 판단 지표입니다.</b>'),PageBreak()]
 story += [P('5. 슬롯 효율','h1'),P('실제 진행 기간 2026.05.22 - 2026.08.09'),Spacer(1,4*mm)]
 sk=[[P(x,'klabel') for x in ['전체 슬롯비','집계 매출','슬롯비/매출','평균 검색순위']],[P(money(ss['totalSlotCost']),'kpi'),P(money(ss['totalSales']),'kpi'),P(pct(ss['slotCostRate']),'kpi'),P(f"{ss['rankAverage']:.1f}위",'kpi')]];st=Table(sk,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);st.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE)]));story += [st,slot_chart(periods),P('상품별 요약','h2')]
 products=[]
 for name in sorted(set(r['product'] for r in periods if r.get('isComplete'))):
  rr=[r for r in periods if r['product']==name and r.get('isComplete')];cost=sum(r.get('slotCost',0) for r in rr);sales=sum((r.get('during') or {}).get('sales',0) for r in rr);ranks=[r['rankAverage'] for r in rr if r.get('rankAverage') is not None];products.append([P(name,'smallb'),P(str(len(rr))+'회','small'),P(money(cost),'small'),P(money(sales),'small'),P(pct(cost/sales) if sales else '-','small'),P(f'{sum(ranks)/len(ranks):.1f}위' if ranks else '-','small')])
 story += [styled_table([[P(x,'smallw') for x in ['상품','구간','슬롯비','집계 매출','비용률','평균 순위']]]+products,[36*mm,18*mm,31*mm,38*mm,24*mm,27*mm]),Spacer(1,7*mm),P('지속 운영 판단','h2')]
 decisions=[('전체','전면 지속 보류','슬롯 시작 전 30일과 운영 후 첫 30일을 비교하면 수건단품은 매출 +2.9%·주문 +10.6%, 세트모음전은 매출 +6.2%·주문 +15.1%, 조구만고리수건은 매출 +94.3%·주문 +81.9%입니다. 광고·프로모션 영향을 분리할 수 없어 증가분 전체를 슬롯 효과로 확정하지 않고 상품별 비용률·순위와 함께 판단합니다.'),('수건단품','지속 검증','비용률 약 1.0%, 평균 3.6위로 가장 양호합니다. 종료 후 7~10일간 매출·순위를 관찰해 비교 지표를 확보하고, 이후에는 순위 하락 시 재가동하고 회복 후 멈추는 간헐 운영 방식도 조심스럽게 검토합니다.'),('세트모음전','축소 검증','비용률 약 3.8%, 평균 8.2위이며 최근 매출이 초기보다 낮습니다. 종료 후 7~10일간 매출·순위를 비교한 뒤 결과에 따라 예산과 운영 기간을 다시 설정해 보정합니다.'),('조구만고리수건','중단 대조','평균 2.7위지만 비용률 약 24.0%로 매출 대비 부담이 있습니다. 중단 후 7~10일간 매출 유지 여부와 순위 하락 폭을 비교해 재운영 여부를 판단합니다.')]
 story += [styled_table([[P(a,'smallb'),P(b,'smallb'),P(c)] for a,b,c in decisions],[30*mm,28*mm,116*mm],False),Spacer(1,6*mm),P('판단 한계','h2'),P('집계 매출은 광고와 프로모션이 함께 반영된 관찰값입니다. 현재 데이터만으로 슬롯이 매출을 늘렸다고 단정할 수 없으며, 다음 운영부터는 시작 전 10일·운영 10일·종료 후 7~10일을 같은 상품 기준으로 비교해야 합니다.'),PageBreak(),P('6. 현재 운영 상태와 하반기 실행안','h1')]
 ops=[('파워링크',f'광고그룹 {len(groups)}개 · 키워드 {len(kws)}개 · 키워드 OFF {len(off)}개 · 그룹 OFF {len(goff)}개'),('순위 수집',f"{dash['rankTraffic'].get('updatedAt','-')} 기준 · 실제 그룹과 PC/모바일 분리"),('슬롯 일정',f"2026.05.22 - 2026.08.09 · 전체 {len(periods)}개 구간")];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in ops],[36*mm,138*mm],False),Spacer(1,9*mm),P('하반기 실행 우선순위','h2')]
 actions=[('1. 측정 기준 고정','실제 매출 MER와 마케팅비율을 경영 판단 기준으로 고정합니다.'),('2. 저효율 광고 조정','실제 매출 기여와 GA4 구매 연결이 낮거나 OFF 전환된 키워드의 입찰·검색어·상품 연결을 재검토합니다.'),('3. 슬롯 재배분','비용률, 평균 순위, 종료 후 7~10일 잔존효과로 유지·축소·중단을 결정합니다.'),('4. 월 1회 보고','누적 성과와 현재 운영 변경을 분리해 같은 형식으로 업데이트합니다.')];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in actions],[40*mm,134*mm],False),Spacer(1,9*mm),P('유의사항','h2'),P('슬롯 집계 매출은 광고·프로모션 효과가 함께 포함된 관찰값입니다. 최종 증분효과는 운영 전 동기간 및 종료 후 7~10일 데이터를 확보한 뒤 확정해야 합니다.')]
 doc.build(story,onFirstPage=footer,onLaterPages=footer);print(OUT)
if __name__=='__main__': build()
