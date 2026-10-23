"""Generate local vector design artefacts only. No application code or network I/O."""
from pathlib import Path
from html import escape
import json
import textwrap

ROOT=Path(__file__).parent
OUT=ROOT/'wireframes'
P={'paper':'#f6f5f0','card':'#ffffff','ink':'#172d27','muted':'#53675e','line':'#d6ded5','green':'#176b55','soft':'#e3efe7','ochre':'#84581e','rose':'#a64340','blue':'#3c6380','violet':'#655a9b'}
SCREENS=[
 ('discover','Discover','Start with a question','Available APIs · presets, registry, screener','Collection → exact filter → fund → brief. Preferences are optional; no invented popularity feed.'),
 ('screen','Screen','Turn a thesis into a shortlist','Available APIs · 160 fields, formulas, conditions','Every rule has units, coverage and an explanation. Empty results use server-returned relaxations.'),
 ('fund','Fund intelligence','Understand the whole picture','Available APIs · NAV, metrics, score, risk, peers','A high historical score stays beside recent losses. Cost, profile and holdings require enrichment.'),
 ('studio','Analytics studio','Put performance in perspective','Available APIs · rolling, ranks, frontier, regimes','Question-led modes expose samples and methods. Proxy regimes never masquerade as official benchmarks.'),
 ('compare','Compare','See the tradeoffs clearly','Available APIs · comparison and correlations','2–5 exact plan-options, common start and pair samples. Correlation is never called holdings overlap.'),
 ('simulate','Simulate','Test the investment habit','Available APIs · SIP, lump sum, SWP, STP','Historical schedules use real NAV services. Tax estimates and unavailable exit loads remain explicit.'),
 ('portfolio','Portfolio intelligence','Look through to what you own','Planned · Slice 6 ledger + E1 / E4','Local CAS preview, reconciliation, commit and undo precede portfolio outcomes. No personal data is used here.'),
 ('workspace','Research workspace','Give your research a memory','Planned · W1–W3 persistence and alerts','Dated briefs preserve original evidence and allow an explicit latest-revision copy. No silent overwrite.'),
 ('agent','Research agent','Ask. Inspect. Keep control.','Planned · Slice 5 runtime + validated tools','English, Hindi and Hinglish operate shared research tools. Every numerical claim needs a cited tool result.'),
 ('mobile','Mobile research loop','A workstation in your hand','Design · responsive shell and context continuity','Search, filter, inspect a loss, compare and resume. All chart help and actions work without hover.'),
]

class SVG:
 def __init__(self,w,h,title):
  self.w=w;self.h=h;self.e=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">Planning wireframe. Frozen v5 reference figures; schematic chart shapes. Planned services explicitly labelled.</desc><defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="#d6ded5" stroke-width="1"/></pattern></defs>']
 def rect(self,x,y,w,h,fill='card',r=12,stroke='line'):
  self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{P.get(fill,fill)}" stroke="{P.get(stroke,stroke)}"/>')
 def line(self,x,y,x2,y2,c='line',dash=''):
  self.e.append(f'<path d="M{x} {y}L{x2} {y2}" fill="none" stroke="{P.get(c,c)}" stroke-dasharray="{dash}"/>')
 def text(self,x,y,s,size=15,c='ink',weight=400,serif=False):
  font='Georgia,serif' if serif else 'Inter,Arial,sans-serif'
  self.e.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{P.get(c,c)}" font-weight="{weight}">{escape(str(s))}</text>')
 def para(self,x,y,s,width,size=14,c='muted',leading=23):
  for i,t in enumerate(textwrap.wrap(s,max(12,int(width/(size*.54))))):self.text(x,y+i*leading,t,size,c)
 def pill(self,x,y,s,w=None,active=False):
  w=w or len(s)*7+24;self.rect(x,y,w,30,'green' if active else 'card',6,'green' if active else 'line');self.text(x+12,y+20,s,12,'card' if active else 'muted',600)
 def button(self,x,y,s,w=170,primary=True):
  self.rect(x,y,w,42,'green' if primary else 'card',7,'green' if primary else 'line');self.text(x+16,y+27,s,13,'card' if primary else 'green',600)
 def panel(self,x,y,w,h,title,sub=None):
  self.rect(x,y,w,h);self.text(x+22,y+32,title,18,weight=600)
  if sub:self.text(x+22,y+55,sub,12,'muted')
 def metric(self,x,y,w,label,value,note='',tone='ink'):
  self.rect(x,y,w,118);self.text(x+18,y+27,label,12,'muted');self.text(x+18,y+65,value,27,tone,600);self.text(x+18,y+94,note,11,'muted')
 def badge(self,x,y,n):
  self.e.append(f'<circle cx="{x}" cy="{y}" r="12" fill="{P["green"]}"/>');self.text(x-4,y+4,str(n),11,'card',600)
 def chart(self,x,y,w,h,kind='growth',series=1):
  self.text(x,y+10,'SCHEMATIC · chart structure only',10,'muted',600)
  for i in range(4):self.line(x,y+32+i*(h-58)/3,x+w,y+32+i*(h-58)/3,dash='3 6')
  shapes={'growth':[.88,.83,.86,.71,.76,.68,.4,.62,.47,.52,.33,.4,.19,.27,.12], 'rolling':[.55,.4,.52,.18,.35,.7,.48,.62,.25,.4,.19,.52,.68,.4,.49], 'drawdown':[.12,.2,.17,.4,.25,.63,.9,.7,.3,.13,.23,.2,.56,.62,.38], 'rank':[.4,.25,.38,.54,.3,.2,.4,.3,.24,.15,.25,.3,.45,.22,.2]}
  colors=['green','ochre','violet']
  for n in range(series):
   vals=shapes.get(kind,shapes['growth']);points=[(x+i*w/(len(vals)-1),y+30+(v*.85+n*.05)*(h-55)) for i,v in enumerate(vals)]
   d='M'+' L'.join(f'{a:.1f},{b:.1f}' for a,b in points)
   if series==1:self.e.append(f'<path d="{d} L{x+w},{y+h-22} L{x},{y+h-22}Z" fill="{P["soft"]}" opacity=".8"/>')
   self.e.append(f'<path d="{d}" stroke="{P[colors[n%3]]}" stroke-width="2.5" fill="none" stroke-dasharray="{"6 4" if n else ""}"/>')
  self.text(x,y+h,'Earlier',11,'muted');self.text(x+w-65,y+h,'Later',11,'muted')
 def table(self,x,y,w,heads,rows,col=None,rowh=54):
  col=col or [w/len(heads)]*len(heads);self.rect(x,y,w,38,'soft',5,'soft')
  px=x
  for head,cw in zip(heads,col):self.text(px+12,y+25,head,11,'muted',600);px+=cw
  for j,row in enumerate(rows):
   yy=y+38+j*rowh;self.line(x,yy+rowh,x+w,yy+rowh);px=x
   for k,(value,cw) in enumerate(zip(row,col)):
    self.text(px+12,yy+31,value,12,'green' if k==0 else 'ink',600 if k==0 else 400);px+=cw
 def dependency(self,x,y,w,h,title,body):
  self.rect(x,y,w,h,'paper',10);self.text(x+18,y+26,'PLANNED SERVICE / DATA',10,'blue',600);self.text(x+18,y+53,title,17,weight=600);self.para(x+18,y+79,body,w-36,13)
 def save(self,path):Path(path).write_text(''.join(self.e)+'</svg>')

def desktop(i):
 key,name,title,cap,_=SCREENS[i];s=SVG(1440,1060,f'D{i+1:02} · {name} · desktop')
 s.rect(0,0,1440,1060,'paper',0,'paper');s.rect(0,0,208,1060,'card',0,'line')
 s.text(25,48,'wickstreet.',26,weight=700,serif=True);s.text(25,72,'THE RESEARCH NOTEBOOK',9,'muted',600)
 s.pill(20,99,'Mutual funds  ▾',168)
 nav=[('Discover','discover'),('Screen','screen'),('Studio','studio'),('Compare','compare'),('Simulate','simulate'),('Workspace','workspace')]
 for n,(label,k) in enumerate(nav):
  yy=164+n*51
  if k==key or key=='fund' and k=='discover':s.rect(14,yy-27,180,43,'soft',7,'soft')
  s.text(29,yy,label,15,'green' if k==key else 'muted',600 if k==key else 400)
 s.line(24,484,184,484);s.text(28,516,'COMPLETE VISION',9,'muted',600);s.text(28,551,'Portfolio   /  Slice 6',12,'blue');s.text(28,588,'Research agent / Slice 5',12,'blue')
 s.text(25,935,'↗ Momentum25 · Stocks',12,'green',600);s.text(25,963,'Local personal workspace',10,'muted');s.text(25,990,'Light  /  Dark',11,'muted')
 s.rect(208,0,1232,76,'paper',0,'line');s.rect(240,18,644,40,'card',8);s.text(257,44,'⌕  Search a fund or ask a research question…',14,'muted');s.pill(1112,24,'Personal · local',132);s.pill(1256,24,'Ask  ↗',104)
 s.text(240,110,f'WICKSTREET 2.0  /  {name.upper()}',10,'green',600);s.text(240,154,title,34,serif=True)
 s.text(240,184,cap,12,'muted');s.text(240,1026,'DESIGN WIREFRAME · not a running application',10,'muted',600);s.text(765,1026,'Reference: 22 Oct 2026 · v5 · r2801   |   Curves schematic',10,'muted')
 return s

def desk_content(s,i):
 if i==0:
  s.rect(240,218,1144,220,'soft',16,'soft');s.text(270,254,'RESEARCH WITH INTENTION',10,'green',600);s.text(270,301,'Make your next investment',31,serif=True);s.text(270,340,'a considered one.',31,serif=True);s.para(270,375,'Go beyond the last return. Understand consistency, risk and the journey.',580)
  s.button(1005,270,'Explore consistent funds',345);s.button(1005,325,'Build my own screen',345,False);s.text(1005,399,'01  Choose a question → inspect its evidence',11,'green')
  s.text(240,481,'A thoughtful starting point',22,serif=True);s.text(1170,479,'All collections  →',13,'green',600)
  cards=[('Consistency, first','Consistent large caps','Rolling 3Y returns above the category median in at least 70% of months.'),('A calmer equity journey','Calm equity','Above-median return, with volatility in the calmer half of its category.'),('Stay with the evidence','Ten-year compounders','Long-history funds screened on returns and positive calendar years.')]
  for n,(ey,title,body) in enumerate(cards):
   xx=240+n*389;s.panel(xx,503,366,205,title);s.text(xx+22,568,ey.upper(),10,'green',600);s.para(xx+22,598,body,320,14);s.text(xx+22,681,'Inspect this screen  →',13,'green',600)
  s.panel(240,736,555,233,'Explore by category','Select a category to open its exact universe')
  for n,t in enumerate(['Large cap','Flexi cap','Mid cap','Hybrid','Liquid','Index funds']):s.pill(262+(n%3)*170,815+(n//3)*53,t,155)
  s.panel(819,736,565,233,'Your research, ready to resume','Personal workspace service · planned M6');s.para(843,826,'Start with a saved screen or decision brief. Your reasoning and original evidence stay together.',500,16);s.button(843,893,'See workspace design',244,False)
 elif i==1:
  s.rect(240,214,244,750);s.text(260,247,'Find the right evidence',17,weight=600);s.rect(260,268,204,37,'paper',6);s.text(272,291,'Search 160 fields…',12,'muted')
  for n,label in enumerate(['Fund & category','Returns','Rolling outcomes','Risk & recovery','Peers & persistence','Scores','Custom formulas']):s.text(261,341+n*47,label,14,'green' if n==2 else 'muted',600 if n==2 else 400)
  s.dependency(258,721,208,213,'Cost & holdings','E1 / E4 will add coverage. No invented TER, AUM or holdings filters.');s.pill(508,216,'Flexi-cap research  ▾',240,True);s.button(1060,214,'Save screen',145,False);s.button(1217,214,'Export  ↓',167,False)
  for n,t in enumerate(['Active','Direct','Growth','Category: Flexi Cap']):s.pill(508+n*204,277,t,192)
  s.pill(508,318,'AND  3Y CAGR ≥ 0%',335);s.pill(855,318,'+ Add filter',150);s.text(508,387,'Coverage and missing exclusions appear here from the response.',13,'muted')
  s.table(508,414,876,['Fund / plan','3Y CAGR','Worst fall','Score'],[['Parag Parikh Flexi Cap','12.18%','−10.98%','97.78'],['Kotak Flexi Cap','10.00%','−16.30%','53.49'],['More matches from live API','—','—','—']],[380,150,170,176],68)
  s.panel(508,693,876,138,'Explain why a fund matches','Every row opens its tested values, missing states and exact condition paths.');s.pill(532,773,'Explain conditions',196);s.pill(740,773,'Columns  ▾',142)
  s.rect(508,861,876,91,'green',10,'green');s.text(531,897,'Compare selected plans',17,'card',600);s.text(531,926,'2–5 funds · exact plan and option preserved',12,'card');s.button(1163,884,'Open comparison',199,False)
 elif i==2:
  s.text(240,235,'Parag Parikh Flexi Cap Fund',28,weight=600);s.text(240,264,'PPFAS  ·  AMFI 122639  ·  Active  ·  Direct / Growth',13,'muted');s.button(1012,220,'+ Watch',140,False);s.button(1165,220,'+ Compare',219)
  for n,t in enumerate(['Overview','Performance','Risk','Peers','Holdings · E4','Profile · E1']):s.pill(240+n*189,293,t,176,n==0)
  vals=[('3Y yearly growth','12.18%','CAGR · trailing window'),('Worst 3Y fall','−10.98%','Not yet recovered'),('Category score','97.78 / 100','Rank 1 of 31 scored peers')]
  for n,(a,b,c) in enumerate(vals):s.metric(240+n*389,348,366,a,b,c,'rose' if n==1 else 'ink')
  s.panel(240,491,741,309,'The performance journey','NAV rebased to 100 · exact anchors in evidence');s.pill(740,510,'All stored',210);s.chart(266,560,685,204)
  s.panel(1005,491,379,309,'Read both sides','A score is historical, category-relative evidence.');s.text(1028,586,'100.0% consistency',22,'green',600);s.para(1028,617,'Above the category median in eligible month-end 3Y windows.',329,13);s.text(1028,701,'−5.69% in the last year',22,'rose',600);s.para(1028,732,'Recent losses remain visible beside the high score.',329,13)
  s.panel(240,824,741,150,'What supports the score?','Three equal-weight percentile parts; risk-free Sharpe and costs are not current parts.');s.pill(263,915,'Open score evidence  →',265)
  s.dependency(1005,824,379,150,'Costs and portfolio','E1 / E4 are required. Read the data coverage rather than a placeholder metric.')
 elif i==3:
  for n,t in enumerate(['Rolling outcomes','Rank persistence','Risk / return','Regimes','Backtest']):s.pill(240+n*231,217,t,215,n==0)
  s.pill(240,266,'Parag Parikh Direct Growth',335);s.pill(590,266,'Holding period: 3Y',240,True);s.pill(846,266,'Snapshot r2801',230)
  s.panel(240,319,749,356,'How much did the entry date matter?','Rolling 3Y return · every eligible stored date');s.chart(264,394,697,233,'rolling');s.text(264,653,'Min 0.74%   /   Median 21.69%   /   Max 37.67% · verified v5 summary',11,'green')
  s.panel(1013,319,371,356,'Evidence, not a forecast');s.para(1037,391,'1,731 overlapping observations. These are not independent investor outcomes.',320,16);s.para(1037,487,'Compare different holding periods before relying on a single trailing return.',320,14);s.button(1037,586,'Inspect distribution',320,False)
  s.panel(240,699,749,279,'Did relative performance persist?','Month-end percentile · changing peer counts remain visible');s.chart(266,772,693,161,'rank');s.text(266,957,'Current category labels applied to historical dates · disclose this limit',11,'muted')
  s.panel(1013,699,371,279,'Research modes');s.para(1037,775,'Frontier: non-dominated peers. Regimes: NAV-built proxy. Backtests: in-sample and hold-out kept separate.',318,15);s.button(1037,900,'Save this research view',320,False)
 elif i==4:
  s.panel(240,214,1144,131,'Compare exact alternatives','Common start: 17 Oct 2016 · verify per-pair coverage and trailing metric windows')
  s.pill(264,288,'Parag Parikh · Direct Growth',366,True);s.pill(646,288,'Kotak · Direct Growth',340);s.pill(1002,288,'+ Add / replace fund',354)
  s.panel(240,369,738,326,'Same starting point. Different journeys.','NAV indexed to 100 · common-start comparison');s.chart(264,444,688,209,series=2)
  s.panel(1002,369,382,326,'The difference that matters');s.text(1026,447,'Daily-return correlation',13,'muted');s.text(1026,488,'0.801',34,weight=600);s.text(1026,520,'2,469 paired returns · reference pair',12,'muted');s.para(1026,564,'They moved together often. This does not establish shared holdings or future diversification.',332,15)
  s.table(240,725,1144,['Evidence','Parag Parikh','Kotak Flexi Cap'],[['3Y CAGR','12.18%','10.00%'],['Worst 3Y fall','−10.98%','−16.30%'],['Holdings overlap','Needs E4','Needs E4']],[440,352,352],52)
  s.button(240,953,'Test an investment  →',278);s.button(539,953,'Add to decision brief',280,False)
 elif i==5:
  s.panel(240,214,338,747,'Build a historical scenario','Actual NAVs · not a future forecast')
  for n,t in enumerate(['SIP','Lump sum','SWP','STP']):s.pill(260+(n%2)*151,287+(n//2)*44,t,137,n==0)
  for y,label,value in [(408,'Monthly amount','₹10,000 · editable input'),(495,'Fund','Parag Parikh · Direct Growth'),(582,'Investment dates','01 Oct 2021 → 22 Oct 2026'),(669,'Schedule / tax','Day 1 · equity · step-up 0%')]:
   s.text(262,y,label,12,'muted');s.rect(260,y+14,296,44,'paper',6);s.text(272,y+42,value,12)
  s.button(260,838,'Run historical scenario',296);s.para(262,909,'First NAV on/after schedule. Stamp duty and tax rules come from the engine.',287,12)
  s.panel(602,214,782,215,'Result appears after a valid run','No outcome values are invented in this wireframe.');s.metric(626,289,228,'Invested','API value','Inputs saved with result');s.metric(872,289,228,'Ending value','API value','Valuation date shown');s.metric(1118,289,242,'Annualised XIRR','API value','Not an assumed rate')
  s.panel(602,453,782,284,'Contributions and value','Schematic result composition · cash-flow table always available');s.chart(628,525,728,169,series=2)
  s.panel(602,761,782,200,'Tax and what this leaves out');s.para(626,826,'Show tax class, rule version, gains by financial year, sales not modelled and all service cautions. Exit loads await E1. Tax not modelled is not zero tax.',730,15);s.pill(626,906,'Inspect cash flows',220);s.pill(864,906,'Save scenario to brief',270)
 elif i==6:
  s.rect(240,214,1144,98,'soft',12,'soft');s.text(264,250,'YOUR DATA STAYS ON YOUR MACHINE',11,'green',600);s.text(264,281,'Local CAS → preview → reconcile → commit → review',19,weight=600);s.pill(1120,245,'Planned Slice 6',235)
  s.panel(240,336,1144,214,'Start with your consolidated statement','Complete-vision design · no parser or portfolio response is simulated');s.button(266,418,'Choose local CAS file',290);s.button(577,418,'View import requirements',300,False);s.para(266,498,'One-use password. Raw file never goes to an AI provider. Only reviewed transactions enter the local ledger.',1050,14)
  s.panel(240,575,551,237,'Where your money is invested','Exposure view waits for a reconciled portfolio');s.rect(266,658,493,36,'paper',5);s.text(280,682,'Known exposure  |  Unresolved  |  Unreported',13,'muted');s.para(266,737,'Disclosure dates, publication dates and residual weights stay visible.',490,14)
  s.panel(815,575,569,237,'Allocation is a scenario','Proposed target versus current allocation');s.para(840,662,'Set constraints. Inspect costs and missing data. Review a proposed rebalance without placing an order.',515,15)
  s.dependency(240,836,1144,135,'Ledger + portfolio methods + E1 / E4','Import preview and reconciliation precede value, XIRR, overlap and look-through. No sample wealth or fund weights are shown.')
 elif i==7:
  s.pill(240,216,'Briefs',164,True);s.pill(419,216,'Watchlists',164);s.pill(598,216,'Screens',164);s.pill(777,216,'Notes',164);s.pill(956,216,'Alerts',164)
  s.panel(240,273,340,690,'Your research shelf','Planned W1–W3 · tenant-scoped persistence');s.rect(259,356,302,102,'soft',8,'soft');s.text(278,389,'Flexi-cap research',18,weight=600);s.text(278,423,'Decision brief · open evidence',12,'muted');s.text(278,505,'+ New brief',14,'green',600);s.text(278,552,'+ New watchlist',14,'green',600);s.text(278,599,'+ Save a screen',14,'green',600);s.para(278,752,'Saved · Unsaved · Saving · Error · Conflict are distinct states.',263,14)
  s.panel(604,273,780,690,'A reason you can return to','Notebook composition · no saved record is claimed');s.pill(1150,294,'Original / Latest',210)
  for n,(a,b) in enumerate([('01  The question','What am I selecting for, and over what horizon?'),('02  Evidence for and against','Attach a metric, chart, source or comparison.'),('03  Alternatives and scenario','Preserve exact plans, dates and assumptions.'),('04  Conclusion and review trigger','Write the reason, doubts and next review condition.')]):
   yy=385+n*130;s.text(630,yy,a,19,serif=True);s.text(630,yy+34,b,14,'muted');s.line(630,yy+74,1358,yy+74)
  s.text(630,931,'Alerts become active only after registration and evaluation.',12,'blue')
 elif i==8:
  s.pill(240,216,'English',150,True);s.pill(403,216,'हिन्दी',150);s.pill(566,216,'Hinglish',150);s.text(1005,238,'Local Ollama · planned Slice 5',12,'blue')
  s.panel(240,272,456,693,'Research in your language','Context: Parag Parikh · r2801 · Risk');s.rect(261,363,412,91,'soft',10,'soft');s.para(279,394,'Explain this fund’s fall and open its recovery chart.',375,16);s.text(263,495,'TOOL STAGES, NOT INVENTED ANSWERS',10,'green',600)
  for n,t in enumerate(['Read pinned fund metrics','Inspect drawdown and recovery','Validate figures and source citations','Open the editable Risk view']):s.text(266,535+n*57,f'{n+1:02}  {t}',13,'muted')
  s.rect(261,829,412,105,'paper',8);s.text(278,862,'Ask a follow-up…',14,'muted');s.text(278,902,'Stop  /  Retry  /  Inspect tools',12,'green')
  s.panel(720,272,664,382,'The evidence stays beside the answer','Proposed layout · result uses deterministic tool output');s.text(746,369,'Worst 3Y fall: −10.98%',27,weight=600);s.text(746,406,'Peak 27 Oct 2025 → trough 30 Mar 2026',14,'muted');s.text(746,441,'Not recovered at the reference snapshot',14,'rose',600);s.chart(746,468,610,143,'drawdown');s.text(746,637,'[1] /metrics  ·  22 Oct 2026 · v5 · r2801',12,'green')
  s.dependency(720,678,664,287,'Conversation and recommendations','Agent runtime, validated templates and tool actions are not built. Personal recommendations must expose criteria, alternatives and counter-evidence. Portfolio tools wait for Slice 6; raw CAS never enters prompts.');s.button(746,893,'Open evidence view',300,False)
 elif i==9:
  s.panel(240,214,1144,123,'One research context, every screen','Desktop, tablet and phone preserve the same selected funds, revision, view and return path.');s.text(265,300,'Search → fund → risk → compare → scenario → brief',23,serif=True)
  for n,(a,b) in enumerate([('1. Search','Exact plan-option and status'),('2. Inspect','One readable chart at a time'),('3. Act','Sticky actions, reserved safe area')]):
   x=240+n*389;s.panel(x,362,366,234,a);s.para(x+23,430,b,315,19);s.para(x+23,498,'No hover-only controls. Back restores context and focus.',315,14)
  s.panel(240,622,743,343,'Tablet adapts the layout, not the evidence','768–1279 px: collapsed rail, filter drawer and overlay research panel');s.rect(266,709,691,195,'paper',10);s.rect(280,724,48,164,'soft',7);s.rect(343,724,375,164,'card',7);s.rect(732,724,210,164,'soft',7);s.text(365,773,'Primary chart',17,weight=600);s.text(752,773,'Evidence',15);s.text(365,820,'One shared revision',13,'muted')
  s.panel(1007,622,377,343,'Phone interaction rules');s.para(1031,702,'Apply / Cancel in filters. Pin tooltips by tap. Compare two focus funds. Put More above the safe area. Keep keyboard and screen-reader access equal.',326,16);s.text(1031,927,'See the paired mobile artboard →',12,'green',600)


def mobile(i):
 key,name,title,cap,_=SCREENS[i];s=SVG(390,1120,f'M{i+1:02} · {name} · mobile')
 s.rect(0,0,390,1120,'paper',0,'paper');s.text(18,34,'wickstreet.',23,weight=700,serif=True);s.text(296,33,'MF  ▾',13,'green',600);s.line(0,53,390,53)
 s.rect(16,69,358,43,'card',8);s.text(30,96,'⌕  Search or ask about a fund…',13,'muted')
 s.text(16,140,f'{i+1:02}  {name.upper()}',10,'green',600);s.para(16,176,title,350,25,'ink',30)
 s.line(0,1034,390,1034);s.rect(0,1035,390,85,'card',0,'card')
 active = {'discover':0,'screen':1,'fund':0,'workspace':2,'portfolio':2,'mobile':1}.get(key,3)
 for n,t in enumerate(['Discover','Screen','Portfolio' if key=='portfolio' else 'Workspace','More']):s.text(15+n*96,1076,t,11,'green' if n==active else 'muted',600)
 s.text(16,1105,'PLANNING ONLY · 390 px · safe area reserved',9,'muted')
 return s

def mob_content(s,i):
 if i==0:
  s.rect(16,226,358,202,'soft',12,'soft');s.text(34,258,'RESEARCH WITH INTENTION',10,'green',600);s.text(34,297,'Consistency over noise.',24,serif=True);s.para(34,329,'Explore evidence beyond the last return.',310,14);s.button(34,366,'Explore consistent funds',322)
  s.text(16,470,'Start with a question',21,serif=True)
  for n,(a,b) in enumerate([('Calm equity','Return and risk, in category context.'),('Ten-year compounders','Study the long journey, with its losses.')]):
   y=494+n*143;s.panel(16,y,358,126,a);s.para(35,y+62,b,315,13);s.text(35,y+102,'Inspect the screen  →',12,'green',600)
  s.panel(16,798,358,173,'Explore a category');s.pill(34,855,'Flexi cap',151);s.pill(202,855,'Hybrid',151);s.text(34,933,'No invented trending or popularity feed.',11,'muted')
 elif i==1:
  s.pill(16,224,'Filters (5)',172,True);s.pill(202,224,'Sort / columns',172);s.text(16,286,'Active · Direct · Growth',12,'muted');s.text(16,312,'Show missing exclusions  →',12,'green',600)
  for n,(name,ret,dd) in enumerate([('Parag Parikh Flexi Cap','12.18%','−10.98%'),('Kotak Flexi Cap','10.00%','−16.30%')]):
   y=338+n*216;s.panel(16,y,358,195,name,'Direct Growth · reference v5');s.text(35,y+96,'3Y CAGR',12,'muted');s.text(209,y+96,'Worst 3Y fall',12,'muted');s.text(35,y+128,ret,24,weight=600);s.text(209,y+128,dd,24,'rose',600);s.text(35,y+170,'Explain match',12,'green',600);s.text(219,y+170,'+ Compare',12,'green',600)
  s.panel(16,790,358,155,'Filter edits use a sheet');s.para(35,855,'Draft changes stay separate. Apply updates results; Cancel leaves the prior screen intact.',310,14)
 elif i==2:
  s.text(16,236,'Parag Parikh Flexi Cap',22,weight=600);s.text(16,264,'122639 · Direct Growth · Active',12,'muted');s.pill(16,285,'Overview',108,True);s.pill(137,285,'Risk',85);s.pill(235,285,'Peers  →',139)
  s.metric(16,335,171,'3Y CAGR','12.18%','Yearly growth');s.metric(203,335,171,'Worst 3Y fall','−10.98%','Not recovered','rose')
  s.panel(16,475,358,265,'The performance journey','NAV rebased · source and anchors visible');s.chart(35,549,320,156)
  s.rect(16,760,358,122,'soft',10,'soft');s.text(34,790,'BOTH SIDES OF THE EVIDENCE',10,'green',600);s.text(34,825,'Score 97.78 / 100',21,weight=600);s.text(34,854,'1Y return −5.69% · keep losses visible',12,'rose')
  s.button(16,909,'+ Compare',172);s.button(202,909,'Test investment',172,False);s.text(16,992,'22 Oct 2026 · method 5 · r2801',11,'muted')
 elif i==3:
  s.pill(16,224,'Rolling outcomes  ▾',358,True);s.pill(16,268,'3Y holding period',211);s.pill(241,268,'r2801',133)
  s.panel(16,321,358,333,'Entry dates matter','Parag Parikh · all eligible stored dates');s.chart(36,395,318,196,'rolling');s.text(36,630,'1,731 overlapping observations',12,'green')
  s.panel(16,676,358,159,'Distribution summary');s.text(35,738,'Min 0.74%    Median 21.69%',17,weight=600);s.text(35,774,'Max 37.67% · annualised rolling return',12,'muted');s.text(35,806,'These are not independent samples.',11,'muted')
  s.panel(16,857,358,136,'Explore deeper');s.pill(33,912,'Ranks',94);s.pill(140,912,'Regimes',101);s.pill(254,912,'Frontier',103)
 elif i==4:
  s.pill(16,224,'A  Parag Parikh  ▾',172,True);s.pill(202,224,'B  Kotak  ▾',172);s.text(16,285,'Common start 17 Oct 2016',12,'muted');s.text(16,310,'Direct Growth · exact plans',12,'muted')
  s.panel(16,333,358,255,'Same start, different journey');s.chart(35,394,319,155,series=2)
  s.table(16,611,358,['Evidence','A','B'],[['3Y CAGR','12.18%','10.00%'],['3Y max fall','−10.98%','−16.30%']],[160,99,99],57)
  s.panel(16,806,358,136,'What moves together?');s.text(35,872,'Correlation 0.801',22,weight=600);s.text(35,906,'2,469 returns · not holdings overlap',12,'muted');s.button(16,965,'Test an investment',358)
 elif i==5:
  s.pill(16,224,'Historical SIP  ▾',358,True)
  for y,label,value in [(286,'Monthly amount','₹10,000 · editable input'),(380,'Fund','Parag Parikh · Direct Growth'),(474,'Dates','01 Oct 2021 → 22 Oct 2026'),(568,'Schedule / tax','Day 1 · equity · step-up 0%')]:
   s.text(16,y,label,12,'muted');s.rect(16,y+17,358,47,'card',7);s.text(30,y+47,value,14)
  s.button(16,676,'Run historical scenario',358);s.panel(16,744,358,240,'A result with its assumptions');s.para(35,809,'Invested, ending value, XIRR and tax arrive from the calculator. Show cash flows and rule versions. Exit loads await E1.',315,15);s.text(35,955,'No fabricated outcome values.',12,'blue',600)
 elif i==6:
  s.pill(16,224,'PLANNED · SLICE 6',358);s.panel(16,278,358,304,'Your CAS stays local');s.para(35,347,'Choose a statement. Enter a one-use password. Review parsed transactions before anything enters your portfolio.',315,16);s.button(35,461,'Choose local file',320);s.text(35,549,'Design only · parser not yet built',12,'blue')
  s.panel(16,604,358,255,'Preview before commit');s.text(35,675,'01  Parse and identify exact plans',14);s.text(35,724,'02  Review duplicates and issues',14);s.text(35,773,'03  Reconcile, then commit',14);s.text(35,823,'Undo import by batch',12,'green',600)
  s.dependency(16,881,358,124,'Ledger + E1 / E4','Value, XIRR and exposure wait for real reconciled inputs.')
 elif i==7:
  s.pill(16,224,'Briefs',111,True);s.pill(139,224,'Lists',105);s.pill(257,224,'More  ▾',117)
  s.panel(16,282,358,207,'Flexi-cap research','Planned workspace record');s.text(35,365,'The question',20,serif=True);s.para(35,398,'Select for consistency, understand the downside, record alternatives.',315,14);s.text(35,461,'Open decision brief  →',12,'green',600)
  s.panel(16,512,358,267,'Your reasoning, preserved');s.text(35,581,'Evidence for and against',17,weight=600);s.text(35,626,'Exact comparison and scenario',14,'muted');s.text(35,670,'Original / latest evidence',14,'muted');s.text(35,714,'Conclusion and review trigger',14,'muted');s.text(35,753,'Saved state must be explicit',12,'green')
  s.dependency(16,802,358,191,'W1–W3 persistence','Notes, named lists and alerts require tenant-scoped storage. An alert is not active until it is registered and evaluated.')
 elif i==8:
  s.pill(16,224,'English',112,True);s.pill(140,224,'हिन्दी',109);s.pill(261,224,'Hinglish',113)
  s.rect(16,280,358,123,'soft',10,'soft');s.para(35,315,'Explain this fund’s fall and open the recovery chart.',315,17);s.text(35,379,'Context: Parag Parikh · r2801',12,'green')
  s.panel(16,426,358,219,'Proposed evidence card','Slice 5 runtime + validator required');s.text(35,513,'Worst 3Y fall −10.98%',23,weight=600);s.text(35,552,'Not recovered at snapshot',14,'rose');s.text(35,591,'[1] Metrics · 22 Oct 2026 · v5',12,'green');s.text(35,621,'Reference evidence, not a chat response',10,'muted')
  s.button(16,669,'Open editable Risk view  ↗',358);s.panel(16,734,358,174,'You keep control');s.para(35,800,'Inspect citations, edit filters, stop tools or save a brief. Raw CAS never enters the model.',315,14);s.rect(16,934,358,65,'card',8);s.text(31,972,'Ask a follow-up…       Stop / Send',13,'muted')
 elif i==9:
  s.rect(16,224,358,731,'card',14);s.text(35,260,'FILTERS',11,'green',600);s.text(35,298,'Build your question',24,serif=True);s.text(35,339,'ALL of these conditions',13,'muted')
  for n,(a,b) in enumerate([('Plan and option','Direct · Growth'),('Status','Active'),('Category','Flexi Cap'),('Consistency','At least 70% of eligible months')]):
   yy=371+n*112;s.text(35,yy,a,12,'muted');s.rect(35,yy+17,320,58,'paper',7);s.text(48,yy+53,b,13)
  s.text(35,845,'Draft changes · original screen retained',11,'muted');s.button(35,883,'Cancel',145,False);s.button(194,883,'Apply filters',161)
  s.text(16,997,'Full-height sheet · focus trapped · Back closes',11,'muted')

for i,(key,*_) in enumerate(SCREENS):
 s=desktop(i);desk_content(s,i);s.save(OUT/f'D{i+1:02}-{key}.svg')
 s=mobile(i);mob_content(s,i);s.save(OUT/f'M{i+1:02}-{key}.svg')

# Detailed variants are intentionally separate from main happy-path artboards.
s=desktop(1);s.text(240,238,'STATE STUDY / EMPTY, NOT AN ERROR',12,'green',600);s.panel(240,274,1144,253,'No funds match every condition','Show this only after a successful screen response.');s.para(266,362,'Keep the exact rules visible. Offer only the relaxation paths and counts returned by the backend; this wireframe invents no result count.',1050,18);s.pill(266,449,'Edit condition',210);s.pill(492,449,'Apply returned relaxation',333);s.panel(240,552,550,359,'A failed request is different');s.para(266,634,'Research could not update. Preserve the prior screen, mark it as previous results, show the server reason and offer Retry.',495,18);s.button(266,802,'Retry research read',270);s.panel(814,552,570,359,'Missing is not zero');s.para(840,634,'NA: not available, with reason. NM: not meaningful, with reason. Every comparison on either fails, including != and not_in. Use is_missing to include it.',516,18);s.save(OUT/'S01-screen-empty.svg')
s=desktop(2);s.panel(240,221,709,721,'Why 97.78 / 100?','Parag Parikh Direct Growth · r2801 · equal-weight category percentiles');s.table(263,319,663,['Part','Percentile','Weight'],[['Consistency 3Y','93.33 / 100','1 / 3'],['Return per risk 3Y','100 / 100','1 / 3'],['Max drawdown 3Y','100 / 100','1 / 3']],[330,200,133],71);s.para(266,635,'The three parts use 31, 36 and 36 ranked peers respectively. A missing part makes the score unavailable. The score is not a personalised suitability assessment.',637,17);s.text(266,785,'Not included: TER, Sharpe, holdings quality',16,'ochre',600);s.para(266,823,'No penalties or data-quality notes were returned for this reference score. That is not a guarantee.',637,15);s.panel(973,221,411,721,'Evidence and limits');s.text(997,306,'1Y return −5.69%',25,'rose',600);s.text(997,356,'Score rank 1 of 31',23,weight=600);s.para(997,418,'Both are true at this snapshot. High historical rank does not eliminate recent loss or predict future performance.',358,17);s.para(997,570,'Sources AMFI / RBI / TigZig. Current category labels applied historically. First stored NAV is not inception.',358,15);s.pill(997,775,'Open source coverage',355);s.save(OUT/'S02-score-evidence.svg')
s=desktop(6);s.panel(240,221,1144,719,'CAS review before import','PLANNED · Slice 6 · no actual statement or private financial record');s.pill(267,296,'01 File ✓',237);s.pill(520,296,'02 Review issues',276,True);s.pill(812,296,'03 Commit',237);s.table(265,364,1091,['Record state','Required action','Ledger impact'],[['Exact identity matched','Review transaction / NAV','Preview only'],['Unresolved plan','Resolve by code / ISIN','Blocks commit'],['Potential duplicate','Exclude or inspect source','No automatic addition'],['Balance difference','Inspect missing transactions','Blocks reconciliation']],[350,425,316],69);s.para(266,747,'Password used once and discarded. Commit is disabled until blocking issues are resolved. Import twice must not duplicate transactions. Undo returns the ledger to the pre-batch state.',1058,17);s.button(266,840,'Back to file',255,False);s.rect(1077,840,280,42,'paper',7);s.text(1091,868,'Commit · awaiting reconciliation',12,'muted');s.save(OUT/'S03-cas-review.svg')

# The gallery is a documentation viewer, not the proposed application.
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wickstreet 2.0 · Design atlas</title><style>
:root{color-scheme:light;--paper:#f6f5f0;--ink:#172d27;--green:#176b55;--line:#d6ded5;--muted:#53675e}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,Arial,sans-serif}header{padding:24px 32px;border-bottom:1px solid var(--line);display:flex;gap:24px;justify-content:space-between;align-items:center;background:#fff}h1{font:32px/1.2 Georgia,serif;margin:5px 0 8px}p{margin:0;color:var(--muted)}.eyebrow{font-size:11px;font-weight:700;letter-spacing:.12em;color:var(--green)}a{color:var(--green)}button{font:inherit;color:var(--ink);background:white;border:1px solid var(--line);border-radius:7px;padding:9px 14px;cursor:pointer;min-height:44px}button[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:3px}.layout{display:grid;grid-template-columns:235px minmax(0,1fr)}nav{padding:22px 16px;border-right:1px solid var(--line)}nav button{display:block;width:100%;text-align:left;margin-bottom:7px;font-size:13px}main{min-width:0;padding:28px 30px}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:18px 0}.toolbar .spacer{flex:1}.stage{border:1px solid var(--line);padding:15px;background:#e9ede6;border-radius:12px;overflow:auto}figure{margin:0}img{display:block;width:100%;height:auto;background:white;box-shadow:0 5px 25px #172d2710}figure.mobile{max-width:390px;margin:0 auto}figcaption{font-size:12px;color:var(--muted);padding:10px 2px}#notes{border:1px solid var(--line);padding:18px;margin-top:18px;border-radius:10px;background:white}#notes h3{margin:0 0 8px;font-size:16px}.status{font-size:12px;font-weight:600;color:var(--green)}.small{font-size:12px}footer{padding:24px 32px;border-top:1px solid var(--line)}summary{cursor:pointer;color:var(--green);padding:10px 0;min-height:44px}.states{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.states a{padding:8px 10px;border:1px solid var(--line);border-radius:6px}.device{display:flex;gap:8px}#screen-title{font:27px Georgia,serif;margin:0 0 9px}.skip{position:absolute;left:-9999px}.skip:focus{left:12px;top:12px;background:white;padding:10px;z-index:10}@media(max-width:800px){header{padding:20px;display:block}header .small{margin-top:12px}.layout{display:block}nav{display:flex;gap:7px;overflow:auto;border-right:0;border-bottom:1px solid var(--line);padding:12px}nav button{white-space:nowrap;width:auto;margin:0;flex-shrink:0}main{padding:20px 12px}.stage{padding:6px}.toolbar{gap:8px}h1{font-size:27px}footer{padding:18px}.spacer{display:none}}
@media print{nav,.toolbar{display:none}.layout{display:block}main{padding:0}.stage{padding:0;border:0}header,footer{padding:10px}img{box-shadow:none}}
</style><a class="skip" href="#main">Skip to artboard</a><header><div><div class="eyebrow">DESIGN ATLAS / 23 OCTOBER 2026</div><h1>Wickstreet. The research notebook.</h1><p>A complete product vision, grounded in method v5.</p></div><div class="small"><strong>Planning and wireframes only</strong><br>No application controls or future service results are simulated.<br><a href="../README.md">Read the master plan</a> · <a href="contact-sheet.svg">All twenty artboards</a></div></header><div class="layout"><nav aria-label="Wireframe screens" id="screens"></nav><main id="main"><p class="eyebrow" id="screen-number"></p><h2 id="screen-title"></h2><p id="capability" class="status"></p><div class="toolbar"><div class="device" role="group" aria-label="Artboard device"><button id="desktop" aria-pressed="true">Desktop</button><button id="mobile" aria-pressed="false">Mobile</button></div><span class="spacer"></span><a id="open" target="_blank" rel="noopener">Open full SVG ↗</a><button id="toggle" aria-expanded="true" aria-controls="notes">Hide design notes</button></div><div class="stage"><figure id="figure"><img id="artboard" alt=""><figcaption id="caption"></figcaption></figure></div><section id="notes" aria-label="Design notes"><h3>Purpose and interaction</h3><p id="purpose"></p><p class="small" style="margin-top:10px">Available API describes backend capability, not a delivered frontend. Planned modules keep explicit dependencies. Chart shapes are schematic; reference figures are frozen v5 observations.</p><details><summary>State studies and implementation contracts</summary><div class="states"><a href="S01-screen-empty.svg">Empty / error / missing</a><a href="S02-score-evidence.svg">Score explanation</a><a href="S03-cas-review.svg">CAS review</a><a href="../03-screen-contracts.md">All screen contracts</a></div></details></section><p id="announcement" role="status" class="sr-only" style="position:absolute;left:-9999px"></p></main></div><footer><p>Local SVG + HTML documentation. No remote fonts, scripts, trackers, APIs or assets. <a href="../07-flows.md">Flow diagrams</a> · <a href="../04-api-capability-map.md">API map</a> · <a href="../05-slice-4-delivery-plan.md">Delivery plan</a></p></footer><script>
const screens=__DATA__; let selected=0, device='desktop';const $=id=>document.getElementById(id);const nav=$('screens');screens.forEach((s,i)=>{let b=document.createElement('button');b.textContent=String(i+1).padStart(2,'0')+'  '+s[1];b.onclick=()=>{selected=i;render()};nav.appendChild(b)});function render(){let s=screens[selected],n=String(selected+1).padStart(2,'0'),src=(device==='desktop'?'D':'M')+n+'-'+s[0]+'.svg';$('artboard').src=src;$('artboard').alt=s[1]+' '+device+' planning wireframe; read purpose and screen contract for interactions.';$('figure').className=device==='mobile'?'mobile':'';$('screen-title').textContent=s[2];$('screen-number').textContent='EXPERIENCE '+n+' / '+s[1].toUpperCase();$('capability').textContent=s[3];$('purpose').textContent=s[4];$('caption').textContent=(device==='desktop'?'1440 × 1060':'390 × 1120')+' · '+s[1]+' · vector artboard · drawn controls are design annotations';$('open').href=src;Array.from(nav.children).forEach((b,i)=>b.setAttribute('aria-pressed',String(i===selected)));['desktop','mobile'].forEach(d=>$(d).setAttribute('aria-pressed',String(d===device)));$('announcement').textContent=s[1]+' '+device+' artboard selected';history.replaceState(null,'','#'+s[0]+'/'+device)}['desktop','mobile'].forEach(d=>$(d).onclick=()=>{device=d;render()});$('toggle').onclick=()=>{let hidden=!$('notes').hidden;$('notes').hidden=hidden;$('toggle').setAttribute('aria-expanded',String(!hidden));$('toggle').textContent=hidden?'Show design notes':'Hide design notes'};let parts=location.hash.slice(1).split('/'),idx=screens.findIndex(s=>s[0]===parts[0]);if(idx>=0)selected=idx;if(parts[1]==='mobile')device='mobile';render();
</script></html>'''
(OUT/'index.html').write_text(html.replace('__DATA__',json.dumps(SCREENS,ensure_ascii=False)))
print('Generated 20 main SVGs, 3 state studies, contact sheet and local gallery.')

# Standalone contact sheet: embed vectors rather than reference external SVG images.
import re
c=SVG(1660,1600,'Wickstreet · ten desktop and mobile wireframe pairs');c.rect(0,0,1660,1600,'paper',0,'paper');c.text(32,47,'Wickstreet 2.0 · the research notebook',30,serif=True);c.text(32,77,'20 main artboards · frozen reference figures / schematic charts · planning only',14,'muted')
for i,(key,name,*_) in enumerate(SCREENS):
 x=32+(i%2)*815;y=111+(i//2)*292;c.text(x,y+19,f'{i+1:02}  {name}',17,weight=600)
 for prefix,xx,ww,hh in [('D',x,600,245),('M',x+614,160,245)]:
  raw=(OUT/f'{prefix}{i+1:02}-{key}.svg').read_text();raw=re.sub(r'<svg[^>]*>',f'<svg x="{xx}" y="{y+32}" width="{ww}" height="{hh}" viewBox="0 0 {1440 if prefix=="D" else 390} {1060 if prefix=="D" else 1120}" preserveAspectRatio="xMinYMin meet">',raw,count=1);raw=raw.replace('id="title"',f'id="title-{prefix}{i}"').replace('id="desc"',f'id="desc-{prefix}{i}"').replace('id="hatch"',f'id="hatch-{prefix}{i}"');c.e.append(raw)
c.save(OUT/'contact-sheet.svg')

FLOW=ROOT/'flows'
def node(s,x,y,w,h,title,body='',kind='card'):
 s.rect(x,y,w,h,kind,12);s.text(x+20,y+32,title,18,'green' if kind=='soft' else 'ink',600);s.para(x+20,y+61,body,w-40,13)
def arrow(s,x,y,xx,yy,label=''):
 s.line(x,y,xx,yy,'green');s.e.append(f'<path d="M{xx-5} {yy-8} L{xx} {yy} L{xx+5} {yy-8}" fill="none" stroke="{P["green"]}" stroke-width="2"/>')
 if label:s.text(x+10,(y+yy)/2,label,11,'muted')

a=SVG(1440,1080,'Navigation map · MF workspace beside preserved Momentum25');a.rect(0,0,1440,1080,'paper',0,'paper');a.text(40,54,'One notebook. Connected research.',36,serif=True);a.text(40,87,'PROPOSED INFORMATION ARCHITECTURE · existing stock URLs retain their meaning',12,'muted')
node(a,400,125,640,115,'Product switch / shared visual language','Mutual funds → /mf     |     Momentum25 → existing / and /chart','soft')
for x in [240,720,1200]:arrow(a,720,240,x,305)
node(a,40,305,400,145,'Explore','Discover /mf • Screen /mf/screen • Search exact plan-options')
node(a,520,305,400,145,'Understand','Fund /mf/funds/:code • Studio /mf/studio • Compare /mf/compare')
node(a,1000,305,400,145,'Test and keep','Simulate /mf/simulate • Workspace /mf/workspace • Decision brief')
for x in [240,720,1200]:arrow(a,x,450,x,524)
node(a,40,524,400,176,'Context travels with the investor','Fund ids, plan/option, revision/method, window, filters and return focus. Financial inputs stay out of URLs.','soft')
node(a,520,524,400,176,'Agent, integrated everywhere','Slice 5: ask → validated tools → cited evidence → editable view. Conventional controls always remain.','soft')
node(a,1000,524,400,176,'Portfolio joins when available','Slice 6 + enrichment: local CAS, ledger, exposures and allocation scenarios. No transaction placement.','soft')
node(a,40,772,650,210,'Desktop / tablet','Desktop: left rail + search/ask + content + one optional evidence rail. Tablet: collapsed rail, filter drawer, overlay evidence.')
node(a,720,772,680,210,'Mobile','Top search/ask; bottom Discover / Screen / Workspace / More. Portfolio replaces Workspace after launch. Studio, Compare and Simulate remain in More.')
a.text(40,1041,'CLIENT COMPOSITION + EXISTING ANALYTICS NOW     /     W1–W3, AGENT, PORTFOLIO AND E1–E7 TRACKED AS DEPENDENCIES',11,'muted',600);a.save(FLOW/'navigation.svg')
(FLOW/'navigation.mmd').write_text('''flowchart TD
  Switch[Product switch] --> MF[Mutual funds /mf]
  Switch --> Stocks[Momentum25 existing routes]
  MF --> Discover[Discover and search]
  Discover --> Screen[Screen and filter]
  Screen --> Fund[Fund intelligence]
  Fund --> Studio[Analytics studio]
  Fund --> Compare[Compare exact plans]
  Compare --> Sim[Historical simulation]
  Sim --> Brief[Saved decision brief]
  Brief --> Review[Review original or latest evidence]
  MF --> Agent[Slice 5 contextual research agent]
  Agent --> Fund
  Agent --> Screen
  MF --> Portfolio[Slice 6 local CAS and portfolio]
  Portfolio --> Brief
''')
a=SVG(1200,1320,'Research journey · evidence to a revisitable decision');a.rect(0,0,1200,1320,'paper',0,'paper');a.text(40,52,'From a question to a considered decision',34,serif=True);a.text(40,84,'J1 / J2 / J3 / J4 / J8 · revision and exact plan identity persist',13,'muted')
stages=[('01  Discover or ask','Choose a purpose-labelled collection or exact plan-option. No mandatory onboarding.'),('02  Screen with transparent rules','Edit filters, inspect missing exclusions and why a row matched. Zero results offer returned relaxations.'),('03  Investigate both sides','Performance, downside, recovery, peers, score breakdown and source/method. State what is unavailable.'),('04  Compare alternatives','2–5 plans; common-start curve, distinct trailing windows and paired correlation observations.'),('05  Test the investment habit','Historical dates and cash flows; tax class, rule version, stamp duty, omissions and previous-result state.'),('06  Record a decision brief','Keep objective, alternatives, evidence for/against, scenario, doubts and review trigger. W1–W3 required.'),('07  Revisit without rewriting history','Replay original revision or refresh an explicit copy. Compare changes; persist conflict-safe edits.')]
for i,(title,body) in enumerate(stages):
 y=121+i*157;node(a,65,y,725,127,title,body,'soft' if i in (2,5) else 'card')
 if i<6:arrow(a,426,y+127,426,y+157)
node(a,840,121,310,260,'A failure keeps context','Service error: retain previous view with its old label and retry. Missing: show NA/NM with reason. No snapshot: explain availability.')
node(a,840,419,310,260,'Back returns to research','Restore filter draft semantics, result cursor, scroll, focus row, compare selection and open disclosure state.')
node(a,840,717,310,260,'Explainability at every step','Value → window → peer/sample → formula → source/date/revision → limitation. Claims never outrun data coverage.')
a.text(65,1274,'Saving a conclusion or scenario does not execute an investment transaction.',13,'green',600);a.save(FLOW/'research-loop.svg')
(FLOW/'research-loop.mmd').write_text('''flowchart TD
  Q[Question or collection] --> S[Screen exact criteria]
  S --> Result{Successful response?}
  Result -->|Error| Retry[Keep prior result and retry]
  Retry --> S
  Result -->|No matches| Relax[Inspect returned relaxations]
  Relax --> S
  Result -->|Matches| F[Fund evidence and limitations]
  F --> C[Compare exact alternatives]
  C --> Sim[Historical scenario]
  Sim --> B[Save dated decision brief]
  B --> R{Later review}
  R -->|Original| Replay[Replay pinned evidence]
  R -->|Refresh copy| Diff[Inspect changes and annotate]
  Diff --> B
''')
a=SVG(1440,1150,'CAS import and agent evidence boundaries');a.rect(0,0,1440,1150,'paper',0,'paper');a.text(40,52,'Trust is a visible workflow',36,serif=True);a.text(40,85,'COMPLETE VISION · proposed interactions · Slice 5 / 6 services remain unbuilt',13,'muted')
node(a,40,122,640,100,'CAS / portfolio lane · Slice 6','Raw file and password stay local. No file enters agent context.','soft');node(a,760,122,640,100,'Research agent lane · Slice 5','Local model; typed tools and response validation under ADR-022.','soft')
left=[('1  Choose file and one-use password','Wrong password or unsupported format → retry, no ledger changes.'),('2  Parse-only preview','Resolve exact plans; inspect duplicates, missing records and balance reconciliation.'),('3  Explicit idempotent commit','Blocking issues resolved; tenant-owned ledger; undo import batch.'),('4  Portfolio views and scenarios','Value/XIRR/unknowns; E4 dated look-through; proposed allocation, no order.')]
right=[('1  Question + public research context','Language, selected plans, window, revision. No raw CAS or credentials.'),('2  Rights-checked deterministic tools','Read facts or build a view. Missing capability returns a named dependency.'),('3  Validate before displaying claims','Unsupported number/entity/date → authoritative template fallback.'),('4  Open evidence or save previewed change','Shared view spec opens editable research. Persist exact answer and tool evidence.')]
for i,(l,r) in enumerate(zip(left,right)):
 y=263+i*187;node(a,40,y,640,145,*l);node(a,760,y,640,145,*r)
 if i<3:arrow(a,360,y+145,360,y+187);arrow(a,1080,y+145,1080,y+187)
a.text(42,1072,'Portfolio tools require a later permitted derived-data boundary; they are not enabled merely because the agent UI exists.',13,'green',600);a.save(FLOW/'cas-agent-boundaries.svg')
(FLOW/'cas-agent-boundaries.mmd').write_text('''flowchart TD
  subgraph LocalCAS[Local CAS and portfolio - Slice 6]
    File[File and one-use password] --> Preview[Parse-only preview]
    Preview --> Issues{Reconciled?}
    Issues -->|No| Resolve[Resolve exact plans and duplicates]
    Resolve --> Preview
    Issues -->|Yes| Commit[Explicit idempotent commit]
    Commit --> Ledger[Tenant-owned ledger]
    Commit --> Undo[Undo batch]
    Ledger --> Portfolio[Portfolio views and scenarios]
  end
  subgraph Agent[Research agent - Slice 5]
    Question[Question and research context] --> Tools[Rights-checked deterministic tools]
    Tools --> Validate{Validated claims?}
    Validate -->|Yes| Answer[Cited answer and editable view]
    Validate -->|No| Template[Reviewed template fallback]
    Answer --> Save[Preview then save exact evidence]
  end
  Portfolio -. Later derived data boundary only .-> Tools
''')
print('Generated three local flow SVGs and editable Mermaid sources.')

# Additional complete-vision analytical states, without fictional portfolio results.
s=desktop(3);s.panel(240,218,739,363,'The risk–return frontier','SCHEMATIC · relative plot positions only, not measured peer values');s.line(287,515,930,515,'muted');s.line(287,515,287,305,'muted');s.text(307,553,'Lower  ←  3Y volatility  →  Higher',12,'muted');s.text(307,295,'3Y yearly growth ↑',12,'muted')
for j,(xx,yy) in enumerate([(337,470),(399,434),(480,458),(524,386),(600,421),(684,331),(753,360),(836,313),(902,371)]):
 s.e.append(f'<circle cx="{xx}" cy="{yy}" r="6" fill="{P["green" if j in (0,1,3,5,7) else "muted"]}"/>')
s.e.append(f'<path d="M337 470L399 434L524 386L684 331L836 313" stroke="{P["green"]}" stroke-width="2" stroke-dasharray="6 5" fill="none"/>')
s.panel(1003,218,381,363,'Select a point, see its evidence');s.para(1026,291,'Fund identity, exact CAGR, volatility, peer key and revision arrive from /peers/frontier. The marked set is non-dominated historically; it is not a personal optimum.',330,16);s.pill(1026,494,'Open fund / data table',330)
s.panel(240,607,554,360,'Did leaders stay leaders?','SCHEMATIC · 12-month transition shares, labels supplied by API')
for y in range(4):
 for x in range(4):s.rect(323+x*78,698+y*54,69,43,['soft','#c6ddcd','#9dc3ad','#689c82'][(x+y)%4],4,'card')
 s.text(268,726+y*54,'Q'+str(y+1),12,'muted')

for j in range(4):s.text(344+j*78,679,'Q'+str(j+1),11,'muted')
s.text(266,952,'Every cell exposes count and row denominator.',12,'muted')
s.panel(818,607,566,360,'How did monthly outcomes vary?','SCHEMATIC · return heatmap; no fabricated return labels')
for y in range(3):
 for x in range(8):s.rect(842+x*64,701+y*58,54,47,['soft','#dec9bd','#a5c6b3','#eeded6'][(x*3+y)%4],4,'card')
s.para(842,918,'Keyboard grid + signed values. Partial periods labelled; NA cells hatched.',510,13);s.save(OUT/'S04-studio-visuals.svg')
s=desktop(6);s.text(240,234,'POST-IMPORT STRUCTURE · PLANNED SLICE 6 + E4',11,'blue',600)
for n,(a,b) in enumerate([('Portfolio value','Reconciled value'),('Investor return','Ledger XIRR'),('Data coverage','Resolved / unknown')]):s.metric(240+n*389,257,366,a,b,'No personal figures in this design')
s.panel(240,400,741,275,'Your exposure, through the fund wrappers','SCHEMATIC · labels and lengths are layout, not proposed allocation weights')
for n,label in enumerate(['Domestic equity','Debt / cash','Foreign / other','Unresolved / unreported']):
 yy=485+n*43;s.text(264,yy,label,12,'muted');s.rect(460,yy-15,[450,305,200,145][n],20,'soft' if n<3 else 'url(#hatch)',3)
s.panel(1005,400,379,275,'What needs attention?');s.para(1028,477,'Disclosure age. Unmatched plans. Residual weights. Drift from your own target. Each links to the supporting records.',330,16)
s.panel(240,700,741,269,'Holdings overlap, with dates','Requires E4 · correlation is a separate NAV view');s.table(264,771,693,['Fund pair','Overlap','Disclosure context'],[['Selected plan A / B','Await E4','Date / publication'],['Selected plan A / C','Await E4','Unknown weight shown']],[295,150,248],54)
s.panel(1005,700,379,269,'Explore a target allocation');s.para(1028,778,'Set constraints and review a proposed scenario. Costs, tax and unavailable inputs stay visible.',330,15);s.button(1028,893,'Inspect scenario design',330,False);s.save(OUT/'S05-portfolio-overview.svg')
s=mobile(6);s.pill(16,224,'POST-IMPORT · PLANNED',358);s.panel(16,282,358,192,'Your portfolio, reconciled','Field labels only · no personal values');s.text(35,363,'Value  /  Investor XIRR',20,weight=600);s.para(35,401,'Dated NAVs and ledger cash flows are the source of every outcome.',312,14)
s.panel(16,496,358,279,'Look through the wrappers','SCHEMATIC · not allocation advice')
for n,label in enumerate(['Equity','Debt / cash','Other','Unknown']):
 yy=588+n*41;s.text(35,yy,label,12,'muted');s.rect(137,yy-14,[207,160,118,75][n],19,'soft' if n<3 else 'url(#hatch)',3)
s.panel(16,797,358,197,'Review the evidence');s.para(35,861,'Inspect disclosure age, unresolved exposure and overlap before exploring a target allocation.',312,15);s.text(35,959,'Open ledger / disclosures / scenario  →',12,'green',600);s.save(OUT/'S06-mobile-portfolio.svg')
# Add state-study links to the gallery without expanding its ten experience destinations.
p=OUT/'index.html';html=p.read_text();html=html.replace('<a href="../03-screen-contracts.md">All screen contracts</a>','<a href="S04-studio-visuals.svg">Frontier / matrices</a><a href="S05-portfolio-overview.svg">Portfolio overview</a><a href="S06-mobile-portfolio.svg">Mobile portfolio</a><a href="../03-screen-contracts.md">All screen contracts</a>');p.write_text(html)
print('Generated frontier/matrix and post-import portfolio state studies.')
