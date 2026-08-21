from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
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
 c.data=[[float(r.get('observedCostCoverage') or 0)*100 for r in rows]]
 c.categoryAxis.categoryNames=[r['month'][5:]+'월' for r in rows]; c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0
 c.lines[0].strokeColor=BLUE;c.lines[0].strokeWidth=2;c.lines[1].strokeColor=AMBER;c.lines[1].strokeWidth=2;d.add(c)
 d.add(String(180,8,'전환성과 확인 광고비 비율 (%)',fontName='Malgun',fontSize=8,fillColor=BLUE));return d
def slot_chart(periods):
 sums={}
 for r in periods:
  if r.get('isComplete'): sums[r.get('product','기타')]=sums.get(r.get('product','기타'),0)+float((r.get('during') or {}).get('sales') or 0)/100000000
 d=Drawing(470,205);c=VerticalBarChart();c.x=55;c.y=40;c.width=370;c.height=135;c.data=[list(sums.values())];c.categoryAxis.categoryNames=list(sums);c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0;c.bars[0].fillColor=BLUE;c.bars[0].strokeColor=BLUE;d.add(c);d.add(String(210,8,'완료 구간 집계 매출 (억원)',fontName='Malgun',fontSize=8,fillColor=SLATE));return d
def footer(canvas,doc):
 canvas.saveState();canvas.setStrokeColor(LINE);canvas.line(18*mm,14*mm,192*mm,14*mm);canvas.setFont('Malgun',7);canvas.setFillColor(SLATE);canvas.drawString(18*mm,9*mm,'더도톰 2026년 1~7월 네이버 광고·슬롯 비용 보고서');canvas.drawRightString(192*mm,9*mm,str(doc.page));canvas.restoreState()
def build():
 OUT.parent.mkdir(parents=True,exist_ok=True); periods=sorted(dash['slotEfficiency']['periods'],key=lambda x:x.get('startDate','')); ss=dash['slotEfficiency']['summary']; groups=power.get('groups',[]); kws=[k for g in groups for k in g.get('keywords',[])]; off=[k for k in kws if k.get('status')!='운영 가능']; goff=[g for g in groups if g.get('campaignStatus')!='운영 가능' or g.get('adgroupStatus')!='운영 가능']
 slot_start=min((r.get('startDate','') for r in periods),default=''); slot_end=max((r.get('endDate','') for r in periods),default=''); complete_count=sum(1 for r in periods if r.get('isComplete')); active_count=len(periods)-complete_count
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
  linked=[r for r in map_rows if str(r.get('productId'))==pid]; adgroup_names={str(r.get('adgroup') or '') for r in linked}
  ads=[r for r in ad_rows if str(r.get('광고그룹명') or '') in adgroup_names]
  cost=sum(float(r.get('총비용') or 0) for r in ads); revenue=sum(float(r.get('전환매출') or 0) for r in ads); actual=product_sales.get(pid,{'sales':0,'orders':0,'refunds':0})
  map_summary.append({'productName':linked[0].get('productName',''),'productId':pid,'groups':', '.join(sorted(adgroup_names-{''})),'cost':cost,'revenue':revenue,'roas':revenue/cost if cost else 0,'sales':actual['sales'],'orders':actual['orders'],'refunds':actual['refunds']})
 map_summary=[{'productName':r.get('productName',''),'productId':str(r.get('productId','')),'groups':', '.join(r.get('adgroups',[]) or []),'cost':float(r.get('adCost') or 0),'revenue':float(r.get('attributedRevenue') or 0),'roas':float(r.get('adRoas') or 0),'sales':float(r.get('actualSales') or 0),'orders':float(r.get('orders') or 0),'refunds':float(r.get('refundAmount') or 0)} for r in channels.get('shoppingProductSummary',[])]
 map_summary.sort(key=lambda x:x['sales'],reverse=True)
 slot_by_month={}
 for r in periods: slot_by_month[r['startDate'][:7]]=slot_by_month.get(r['startDate'][:7],0)+float(r.get('slotCost') or 0)
 monthly=[]
 for r in report['monthly']:
  row=dict(r);row['slotCost']=slot_by_month.get(row['month'],0);row['confirmedAdCost']=float(row.get('confirmedAdCost') or 0);row['observedAdCost']=float(row.get('observedAdCost') or row.get('searchAdCost') or 0);row['unobservedAdCost']=max(0,row['confirmedAdCost']-row['observedAdCost']);row['observedCostCoverage']=row['observedAdCost']/row['confirmedAdCost'] if row['confirmedAdCost'] else 0;monthly.append(row)
 report_slot_cost=float(ss.get('totalSlotCost') or 0);marketing_cost=float(report['confirmedAdCost']);observed_cost=float(report['observedAdCost']);unobserved_cost=float(report['unobservedAdCost']);coverage=float(report['observedCostCoverage']);direct_cost=marketing_cost+report_slot_cost
 ch={r['channel']:r for r in channels['operational']}; pl=ch['파워링크']; sh=ch['쇼핑검색']; sh['adRoas']=sh['platformAttributedSales']/sh['adCost'] if sh['adCost'] else 0; cg=channels['ga4']
 doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=19*mm,title='더도톰 2026년 1~7월 네이버 광고·슬롯 비용 보고서',author='더도톰'); story=[]
 cover=Table([[P('2026년 1~7월<br/>네이버 광고·슬롯 비용 보고서','title')],[P('네이버 파워링크·쇼핑검색 광고비와 검색 슬롯 결과만 정리했습니다.<br/>다른 마케팅 활동은 이 보고서에 포함하지 않았습니다.','sub')]],colWidths=[174*mm],rowHeights=[72*mm,52*mm]);cover.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#172554')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),15*mm)]));story += [Spacer(1,28*mm),cover,Spacer(1,13*mm),P('보고 기간  2026.01.01 - 2026.07.31','h2'),P(f'슬롯 운영 일정  {slot_start} - {slot_end}  |  2026.08.10 - 2026.08.19 무상 AS(0원)'),PageBreak()]
 story += [P('1. 요약','h1')]
 kd=[[P(x,'klabel') for x in ['확정 네이버 광고비','슬롯비','성과 확인 광고비','성과 미확인 광고비']],[P(money(marketing_cost),'kpi'),P(money(report_slot_cost),'kpi'),P(money(observed_cost),'kpi'),P(money(unobserved_cost),'kpi')]];kt=Table(kd,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);kt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE')]));story += [kt,Spacer(1,8*mm),P('먼저 확인할 사항','h2')]
 cautions=[('광고비',f"엑셀 수기 확정값과 조회값 중 높은 금액을 적용한 네이버 광고비는 {money(marketing_cost)}입니다."),('전환성과','1~5월을 중심으로 일부 광고계정이 삭제되어 전환수·전환매출이 모두 남아 있지 않습니다.'),('확인 범위',f"성과가 확인되는 광고비는 {money(observed_cost)}으로 확정 광고비의 {pct(coverage)}이며, {money(unobserved_cost)}은 전환성과를 확인할 수 없습니다."),('전체 ROAS','광고비 전체와 전환성과의 데이터 범위가 달라 전체 ROAS는 산출하지 않습니다.')]
 story += [styled_table([[P(a,'smallb'),P(b)] for a,b in cautions],[36*mm,138*mm],False),Spacer(1,7*mm),P('보고 범위','h2')]
 scope=[('포함','네이버 파워링크·쇼핑검색 광고와 검색 슬롯'),('제외','라이브 방송, 체험단, 맘카페, CRM 및 기타 마케팅 활동'),('부분 전환매출',f"현재 조회 가능한 계정에서 {money(report['platformAttributedSales'])}이 확인됐습니다. 전체 광고의 성과가 아닙니다."),('광고유형별 자료','파워링크·쇼핑검색 구분도 삭제되지 않은 계정만 포함하므로 전체 정산 내역으로 보지 않습니다.')]
 story += [styled_table([[P(a,'smallb'),P(b)] for a,b in scope],[36*mm,138*mm],False),PageBreak()]
 story += [P('2. 월별 확정 광고비와 성과 확인 범위','h1'),line_chart(monthly)]
 md=[[P(x,'smallw') for x in ['월','확정 광고비','성과 확인 광고비','확인률','성과 미확인 광고비','부분 전환매출']]]
 for r in monthly: md.append([P(r['month'][5:]+'월','small'),P(money(r['confirmedAdCost']),'smallb'),P(money(r['observedAdCost']),'small'),P(pct(r['observedCostCoverage']),'small'),P(money(r['unobservedAdCost']),'small'),P(money(r['platformAttributedSales']),'small')])
 story += [styled_table(md,[16*mm,32*mm,32*mm,22*mm,34*mm,38*mm]),Spacer(1,7*mm),P('표 읽는 방법','h2'),P('확정 광고비는 엑셀 수기값과 조회값 중 높은 금액을 적용했습니다. 성과 확인 광고비와 부분 전환매출은 현재 조회 가능한 계정만 포함합니다. 특히 1~5월은 삭제 계정의 영향이 커서 확인률이 낮으며, 부분 전환매출만으로 월별 전체 효율을 비교하면 실제보다 좋아 보일 수 있습니다.'),PageBreak()]
 story += [P('3. 조회 가능한 계정의 광고유형별 성과','h1'),P('주의  삭제되지 않은 계정에서 조회되는 일부 데이터이며 전체 광고비 정산 내역이 아닙니다.'),Spacer(1,5*mm)]
 ch={r['channel']:r for r in channels['operational']}; pl=ch['파워링크']; sh=ch['쇼핑검색']; sh['adRoas']=sh['platformAttributedSales']/sh['adCost'] if sh['adCost'] else 0; cg=channels['ga4']
 cd=[[P(x,'smallw') for x in ['월','광고 유형','광고비','노출','클릭','CTR','CPC','구매 연결 기준']]]
 for r in channels['monthly']:
  ga4_text=f"{int(r['ga4Sessions']):,}세션 · {int(r['ga4Transactions']):,}건 · {money(r['ga4PurchaseRevenue'])}" if r['channel']=='파워링크' else f"네이버 광고 전환매출 {money(r.get('platformAttributedSales',0))}<br/>스마트스토어 실제 매출 {money(r.get('smartstoreSales',0))}"
  cd.append([P(r['month'][5:]+'월','small'),P(r['channel'],'smallb'),P(money(r['adCost']),'small'),P(f"{int(r['impressions']):,}",'small'),P(f"{int(r['clicks']):,}",'small'),P(pct(r['ctr']),'small'),P(money(r['cpc']),'small'),P(ga4_text+('<br/>'+r['ga4Status'] if r['channel']=='파워링크' else ''),'small')])
 for r in channels['operational']:
  ga=cg['powerlink'] if r['channel']=='파워링크' else None
  ga4_text=f"{int(ga['sessions']):,}세션 · {int(ga['transactions']):,}건 · {money(ga['purchaseRevenue'])}" if ga else f"네이버 광고 전환매출 {money(cg['shopping']['platformAttributedSales'])}<br/>스마트스토어 실제 매출 {money(cg['shopping']['smartstoreSales'])}"
  cd.append([P('합계','smallb'),P(r['channel'],'smallb'),P(money(r['adCost']),'smallb'),P(f"{int(r['impressions']):,}",'small'),P(f"{int(r['clicks']):,}",'small'),P(pct(r['ctr']),'small'),P(money(r['cpc']),'small'),P(ga4_text,'small')])
 story += [styled_table(cd,[12*mm,21*mm,27*mm,23*mm,18*mm,15*mm,22*mm,36*mm]),Spacer(1,7*mm)]
 channel_notes=[('부분 데이터',f"유형별 광고비 합계 {money(observed_cost)}은 확정 광고비 {money(marketing_cost)}의 {pct(coverage)}만 설명합니다."),('쇼핑검색',f"조회 가능한 계정에서 광고비 {money(sh['adCost'])}와 전환매출 {money(sh['platformAttributedSales'])}이 확인됐습니다."),('파워링크',f"조회 가능한 계정의 광고비는 {money(pl['adCost'])}이며 GA4 광고 유입 후 구매매출은 {money(cg['powerlink']['purchaseRevenue'])}입니다."),('해석 주의','유형별 비중과 ROAS는 삭제 계정이 제외된 관측값이므로 전체 광고 운영 성과로 확대 해석하지 않습니다.')]
 story += [KeepTogether([P('부분 데이터 설명','h2'),styled_table([[P(a,'smallb'),P(b)] for a,b in channel_notes],[38*mm,136*mm],False),Spacer(1,6*mm)])]
 mapping_table=[[P(x,'smallw') for x in ['연결 본상품','상품 ID','광고그룹','광고비','광고 전환매출 (참고)','관측 ROAS (부분)','상품 실제 매출 (환불 반영)','주문수']]]
 for r in map_summary: mapping_table.append([P(r['productName'],'small'),P(r['productId'],'small'),P(r['groups'],'small'),P(money(r['cost']),'small'),P(money(r['revenue']),'small'),P(mult(r['roas']),'small'),P(money(r['sales']),'small'),P(str(int(r['orders'])),'small')])
 story += [styled_table(mapping_table,[42*mm,24*mm,34*mm,22*mm,27*mm,20*mm,27*mm,18*mm]),Spacer(1,7*mm),P('관측 범위','h2'),P('상품별 광고비·전환매출·ROAS도 현재 조회 가능한 쇼핑검색 계정만 포함합니다. 삭제 계정의 비용과 전환성과는 포함되지 않았습니다.'),PageBreak()]
 story += [P('4. 자사몰에서 확인된 네이버 광고 유입','h1'),P('관측 기간  2026.06.19 - 2026.07.31  |  태그가 설치된 자사몰 기준'),Spacer(1,5*mm)]
 gs=ga4e['summary']; gj=ga4e['july']
 gk=[[P(x,'klabel') for x in ['검색광고 유입','검색광고 유입 구매','유입 후 구매 매출','7월 매출 비중']],[P(f"{int(gs['paidSearchSessions']):,}세션",'kpi'),P(f"{int(gs['paidSearchTransactions']):,}건",'kpi'),P(money(gs['paidSearchRevenue']),'kpi'),P(pct(gj['paidSearchRevenueShare']),'kpi')]]
 gt=Table(gk,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);gt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
 story += [gt,Spacer(1,7*mm)]
 evidence=[('확인된 매출',f"7월 GA4 자사몰 구매매출 {money(gj['purchaseRevenue'])} 중 검색광고 유입 후 구매매출은 {money(gj['paidSearchRevenue'])}으로 {pct(gj['paidSearchRevenueShare'])}입니다."),('확인된 유입',f"검색광고 유입 {int(gj['paidSearchSessions']):,}세션과 구매 {int(gj['paidSearchTransactions']):,}건이 관측됐습니다.")]
 story += [KeepTogether([P('광고 유입 관측 결과','h2'),styled_table([[P(a,'smallb'),P(b)] for a,b in evidence],[36*mm,138*mm],False)]),Spacer(1,7*mm)]
 limits=[('자사몰 한정','GA4 값에는 스마트스토어·무라 매출이 포함되지 않습니다.'),('관측값','검색광고 유입 후 구매 매출이며 광고가 없었을 때의 순증매출을 직접 증명하지는 않습니다.'),('6월 부분 집계','구매 추적이 확인되는 6월 19일부터만 포함했습니다.'),('UTM 신뢰도',f"7월 UTM 분류율은 {pct(gj['utmMappingCoverage'])}로 집계됐습니다.")]
 story += [KeepTogether([P('데이터 해석 범위','h2'),styled_table([[P(a,'smallb'),P(b)] for a,b in limits],[36*mm,138*mm],False)]),PageBreak()]
 story += [P('5. 네이버 검색 슬롯 운영 결과','h1'),P(f'실제 진행 기간 {slot_start} - {slot_end}  |  8월 10~19일 무상 AS(슬롯비 0원)'),Spacer(1,4*mm)]
 sk=[[P(x,'klabel') for x in ['전체 슬롯비','집계 매출','슬롯비/매출','평균 검색순위']],[P(money(ss['totalSlotCost']),'kpi'),P(money(ss['totalSales']),'kpi'),P(pct(ss['slotCostRate']),'kpi'),P(f"{ss['rankAverage']:.1f}위",'kpi')]];st=Table(sk,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);st.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE)]));story += [st,slot_chart(periods),P('상품별 요약','h2')]
 products=[]
 for name in sorted(set(r['product'] for r in periods if r.get('isComplete'))):
  rr=[r for r in periods if r['product']==name and r.get('isComplete')];cost=sum(r.get('slotCost',0) for r in rr);sales=sum((r.get('during') or {}).get('sales',0) for r in rr);ranks=[r['rankAverage'] for r in rr if r.get('rankAverage') is not None];products.append([P(name,'smallb'),P(str(len(rr))+'회','small'),P(money(cost),'small'),P(money(sales),'small'),P(pct(cost/sales) if sales else '-','small'),P(f'{sum(ranks)/len(ranks):.1f}위' if ranks else '-','small')])
 story += [styled_table([[P(x,'smallw') for x in ['상품','구간','슬롯비','집계 매출','비용률','평균 순위']]]+products,[36*mm,18*mm,31*mm,38*mm,24*mm,27*mm]),Spacer(1,7*mm),P('슬롯 결과 해석','h2')]
 decisions=[('전체 비교','수건단품 매출 +2.9%·주문 +10.6%, 세트모음전 매출 +6.2%·주문 +15.1%, 조구만고리수건 매출 +94.3%·주문 +81.9%가 관측됐습니다.'),('수건단품','비용률 약 1.0%, 평균 검색 순위 3.6위로 세 상품 중 비용 부담이 가장 낮았습니다.'),('세트모음전','비용률 약 3.8%, 평균 검색 순위 8.2위이며 최근 매출은 초기 구간보다 낮았습니다.'),('조구만고리수건','비용률 약 24.0%, 평균 검색 순위 2.7위로 비용 부담이 가장 높았습니다.')]
 story += [styled_table([[P(a,'smallb'),P(b)] for a,b in decisions],[42*mm,132*mm],False),Spacer(1,7*mm),P('해석 한계','h2'),P('집계 매출에는 광고와 프로모션 영향이 함께 포함되어 있어 슬롯의 순수 증분 효과를 분리할 수 없습니다.')]
 doc.build(story,onFirstPage=footer,onLaterPages=footer);print(OUT)
if __name__=='__main__': build()
