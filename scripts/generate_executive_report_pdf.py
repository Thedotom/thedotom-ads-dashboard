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
dash=json.loads((ROOT/'data'/'monthly-dashboard-2026-08.json').read_text(encoding='utf-8-sig'))
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
 c.data=[[float(r.get('mer') or 0) for r in rows],[float(r.get('platformRoas') or 0) for r in rows]]
 c.categoryAxis.categoryNames=[r['month'][5:]+'월' for r in rows]; c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0
 c.lines[0].strokeColor=BLUE;c.lines[0].strokeWidth=2;c.lines[1].strokeColor=AMBER;c.lines[1].strokeWidth=2;d.add(c)
 d.add(String(155,8,'실제 MER',fontName='Malgun',fontSize=8,fillColor=BLUE));d.add(String(250,8,'플랫폼 ROAS',fontName='Malgun',fontSize=8,fillColor=AMBER));return d
def slot_chart(periods):
 sums={}
 for r in periods:
  if r.get('isComplete'): sums[r.get('product','기타')]=sums.get(r.get('product','기타'),0)+float((r.get('during') or {}).get('sales') or 0)/100000000
 d=Drawing(470,205);c=VerticalBarChart();c.x=55;c.y=40;c.width=370;c.height=135;c.data=[list(sums.values())];c.categoryAxis.categoryNames=list(sums);c.categoryAxis.labels.fontName='Malgun';c.categoryAxis.labels.fontSize=8;c.valueAxis.labels.fontName='Malgun';c.valueAxis.labels.fontSize=8;c.valueAxis.valueMin=0;c.bars[0].fillColor=BLUE;c.bars[0].strokeColor=BLUE;d.add(c);d.add(String(210,8,'완료 구간 집계 매출 (억원)',fontName='Malgun',fontSize=8,fillColor=SLATE));return d
def footer(canvas,doc):
 canvas.saveState();canvas.setStrokeColor(LINE);canvas.line(18*mm,14*mm,192*mm,14*mm);canvas.setFont('Malgun',7);canvas.setFillColor(SLATE);canvas.drawString(18*mm,9*mm,'더도톰 2026년 1~7월 광고·슬롯 대표 보고서');canvas.drawRightString(192*mm,9*mm,str(doc.page));canvas.restoreState()
def build():
 OUT.parent.mkdir(parents=True,exist_ok=True); periods=sorted(dash['slotEfficiency']['periods'],key=lambda x:x.get('startDate','')); ss=dash['slotEfficiency']['summary']; groups=power.get('groups',[]); kws=[k for g in groups for k in g.get('keywords',[])]; off=[k for k in kws if k.get('status')!='운영 가능']; goff=[g for g in groups if g.get('campaignStatus')!='운영 가능' or g.get('adgroupStatus')!='운영 가능']
 doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=19*mm,title='더도톰 2026년 1~7월 광고·슬롯 대표 보고서',author='더도톰'); story=[]
 cover=Table([[P('2026년 1~7월<br/>광고·슬롯 대표 보고서','title')],[P('실제 매출과 전체 마케팅비를 중심으로 광고 효율을 재정리하고,<br/>5월 22일부터 시작된 슬롯 운영의 성과와 하반기 실행 기준을 함께 제시합니다.','sub')]],colWidths=[174*mm],rowHeights=[72*mm,52*mm]);cover.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#172554')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),15*mm)]));story += [Spacer(1,28*mm),cover,Spacer(1,13*mm),P('보고 기간  2026.01.01 - 2026.07.31','h2'),P('슬롯 운영 일정  2026.05.22 - 2026.08.09'),PageBreak()]
 story += [P('1. 경영 요약','h1')]
 kd=[[P(x,'klabel') for x in ['실제 전체 매출','전체 마케팅비','마케팅비율','실제 매출 MER']],[P(money(report['actualSales']),'kpi'),P(money(report['totalMarketingCost']),'kpi'),P(pct(report['marketingCostRate']),'kpi'),P(mult(report['mer']),'kpi')]];kt=Table(kd,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);kt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE')]));story += [kt,Spacer(1,8*mm),P('대표 보고 결론','h2')]
 conclusions=[('실제 효율 중심',f"누적 실제 MER {mult(report['mer'])}, 매출 대비 마케팅비율 {pct(report['marketingCostRate'])}"),('플랫폼 지표 분리',f"플랫폼 귀속매출이 실제 매출의 {pct(report['attributedSalesShare'])}로 100% 초과"),('슬롯 상품별 판단',f"총 {ss['periodCount']}개 구간, 완료 {ss['completedCount']}개, 진행·관찰 {ss['activeCount']}개"),('하반기 실행','저효율 광고 조정과 슬롯 유지·축소·중단 기준을 월 1회 점검')];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in conclusions],[36*mm,138*mm],False),PageBreak()]
 story += [P('2. 1~7월 월별 성과','h1'),line_chart(report['monthly'])]
 md=[[P(x,'smallw') for x in ['월','실제 매출','마케팅비','비용률','실제 MER','플랫폼 ROAS','귀속/실매출']]]
 for r in report['monthly']: md.append([P(r['month'][5:]+'월','small'),P(money(r['actualSales']),'small'),P(money(r['totalMarketingCost']),'small'),P(pct(r['marketingCostRate']),'small'),P(mult(r['mer']),'small'),P(mult(r['platformRoas']),'small'),P(pct(r['attributedSalesShare']),'small')])
 story += [styled_table(md,[14*mm,34*mm,31*mm,20*mm,22*mm,24*mm,29*mm]),Spacer(1,7*mm),P('해석','h2'),P('3월부터 플랫폼 귀속매출이 실제 매출을 넘기 시작했고 4~7월에는 차이가 더 커졌습니다. 하반기 예산 판단은 플랫폼 ROAS 단독이 아니라 실제 매출 MER와 비용률을 우선 기준으로 삼습니다.'),PageBreak()]
 story += [P('3. 슬롯 효율','h1'),P('실제 진행 기간 2026.05.22 - 2026.08.09'),Spacer(1,4*mm)]
 sk=[[P(x,'klabel') for x in ['전체 슬롯비','집계 매출','슬롯비/매출','평균 검색순위']],[P(money(ss['totalSlotCost']),'kpi'),P(money(ss['totalSales']),'kpi'),P(pct(ss['slotCostRate']),'kpi'),P(f"{ss['rankAverage']:.1f}위",'kpi')]];st=Table(sk,colWidths=[43.5*mm]*4,rowHeights=[12*mm,18*mm]);st.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('GRID',(0,0),(-1,-1),.5,LINE)]));story += [st,slot_chart(periods),P('상품별 요약','h2')]
 products=[]
 for name in sorted(set(r['product'] for r in periods)):
  rr=[r for r in periods if r['product']==name];cost=sum(r.get('slotCost',0) for r in rr);sales=sum((r.get('during') or {}).get('sales',0) for r in rr);ranks=[r['rankAverage'] for r in rr if r.get('rankAverage') is not None];products.append([P(name,'smallb'),P(str(len(rr))+'회','small'),P(money(cost),'small'),P(money(sales),'small'),P(pct(cost/sales) if sales else '-','small'),P(f'{sum(ranks)/len(ranks):.1f}위' if ranks else '-','small')])
 story += [styled_table([[P(x,'smallw') for x in ['상품','구간','슬롯비','집계 매출','비용률','평균 순위']]]+products,[36*mm,18*mm,31*mm,38*mm,24*mm,27*mm]),PageBreak(),P('4. 슬롯 진행 상세','h1')]
 sd=[[P(x,'smallw') for x in ['상품·키워드','진행 기간','슬롯비','매출','주문','비용률','순위','판정']]]
 for r in periods:
  du=r.get('during') or {};sd.append([P(r['product']+'<br/><font color="#64748B">'+r.get('keyword','')+'</font>','small'),P(r['startDate']+'<br/>~ '+r['endDate'],'small'),P(money(r.get('slotCost')),'small'),P(money(du.get('sales')),'small'),P(int(du.get('orders') or 0),'small'),P(pct(r['slotCostRate']) if r.get('slotCostRate') is not None else '-','small'),P(f"{r['rankAverage']:.1f}위" if r.get('rankAverage') is not None else '-','small'),P(r.get('decision','관찰중'),'small')])
 story += [styled_table(sd,[32*mm,29*mm,22*mm,26*mm,12*mm,17*mm,13*mm,23*mm]),PageBreak(),P('5. 현재 운영 상태와 하반기 실행안','h1')]
 ops=[('파워링크',f'광고그룹 {len(groups)}개 · 키워드 {len(kws)}개 · 키워드 OFF {len(off)}개 · 그룹 OFF {len(goff)}개'),('순위 수집',f"{dash['rankTraffic'].get('updatedAt','-')} 기준 · 실제 그룹과 PC/모바일 분리"),('슬롯 일정',f"2026.05.22 - 2026.08.09 · 전체 {len(periods)}개 구간")];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in ops],[36*mm,138*mm],False),Spacer(1,9*mm),P('하반기 실행 우선순위','h2')]
 actions=[('1. 측정 기준 고정','실제 매출 MER와 마케팅비율을 경영 판단 기준으로 고정합니다.'),('2. 저효율 광고 조정','전환매출이 낮거나 OFF 전환된 키워드의 입찰·검색어·상품 연결을 재검토합니다.'),('3. 슬롯 재배분','비용률, 평균 순위, 종료 후 7일 잔존효과로 유지·축소·중단을 결정합니다.'),('4. 월 1회 보고','누적 성과와 현재 운영 변경을 분리해 같은 형식으로 업데이트합니다.')];story += [styled_table([[P(a,'smallb'),P(b)] for a,b in actions],[40*mm,134*mm],False),Spacer(1,9*mm),P('유의사항','h2'),P('슬롯 집계 매출은 광고·프로모션 효과가 함께 포함된 관찰값입니다. 최종 증분효과는 운영 전 동기간 및 종료 후 7일 데이터를 확보한 뒤 확정해야 합니다.')]
 doc.build(story,onFirstPage=footer,onLaterPages=footer);print(OUT)
if __name__=='__main__': build()