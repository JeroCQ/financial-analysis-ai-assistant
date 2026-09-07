"""Independent stdlib reference calculations; intentionally does not import application code."""
import csv
from decimal import Decimal
from datetime import date
from collections import defaultdict
D=Decimal
gl=list(csv.DictReader(open('gl_transactions.csv'))); coa=list(csv.DictReader(open('chart_of_accounts.csv'))); fx={(r['period_month'],r['currency']):D(r['rate_to_usd']) for r in csv.DictReader(open('fx_rates.csv'))}; vendors={r['vendor_id']:r for r in csv.DictReader(open('vendors.csv'))}
def cls(r):
 d=date.fromisoformat(r['accrual_date'])
 return next(x for x in coa if x['account_code']==r['account_code'] and date.fromisoformat(x['valid_from'])<=d and (x['valid_to']=='9999-12-31' or d<=date.fromisoformat(x['valid_to'])))
def usd(r): return D(r['amount'])*fx.get((r['accrual_date'][:7],r['currency']),D(0))
# q2 by cc USD and local
x=[r for r in gl if '2024-04-01'<=r['accrual_date']<='2024-06-30' and cls(r)['statement_line']=='Operating Expenses']
a=defaultdict(D)
for r in x:a[(r['cost_centre'],r['currency'])]+=D(r['amount'])
print('Q2 local',dict(sorted(a.items())))
print('Q2 usd',sum(map(usd,x)))
# travel comparison
for y in [2023,2024]:
 x=[r for r in gl if r['accrual_date'].startswith(str(y)) and cls(r)['parent_name']=='Travel & Entertainment']
 print('travel',y,sum(map(usd,x)),len(x))
# q3 consolidated
x=[r for r in gl if '2024-07-01'<=r['accrual_date']<='2024-09-30' and cls(r)['statement_line']=='Operating Expenses']
print('q3',sum(map(usd,x)),len(x))
# vendor top
v=defaultdict(D)
for r in gl:
 if r['vendor_id']:v[r['vendor_id']]+=usd(r)
print('vendors')
for k,n in sorted(v.items(),key=lambda z:z[1],reverse=True)[:10]: print(k,vendors[k]['vendor_name'],n)
# budget q3 aggregate
bud=list(csv.DictReader(open('budget.csv'))); aa=defaultdict(D); bb=defaultdict(D); names={}
for r in gl:
 if '2024-07-01'<=r['accrual_date']<='2024-09-30':
  cc='OPS-AMER' if r['cost_centre']=='OPS-NA' else r['cost_centre']; aa[(cc,r['account_code'])]+=usd(r); names[r['account_code']]=cls(r)['account_name']
for r in bud:
 if '2024-07'<=r['period_month']<='2024-09':bb[(r['cost_centre'],r['account_code'])]+=D(r['budget_amount'])
ccs=defaultdict(lambda:[D(0),D(0)])
for k in set(aa)|set(bb):ccs[k[0]][0]+=aa[k];ccs[k[0]][1]+=bb[k]
for cc,(a,b) in sorted(ccs.items(),key=lambda x:x[1][0]-x[1][1],reverse=True):
 drivers=sorted(((aa[(cc,ac)]-bb[(cc,ac)],names.get(ac,ac)) for c,ac in set(aa)|set(bb) if c==cc),reverse=True)[:3]
 print('budget',cc,a,b,a-b,drivers)
# approval
x=[r for r in gl if r['account_code'] in ['6210','6220','6230','6240'] and usd(r)>=1000 and not r['approval_ref']]
print('approval count',len(x))
# dups
g=defaultdict(list)
for r in gl:
 if r['vendor_id'] and D(r['amount'])>0:g[(r['vendor_id'],r['amount'],r['currency'])].append(r)
c=[]
for _,rs in g.items():
 rs.sort(key=lambda r:r['accrual_date'])
 for l,r in zip(rs,rs[1:]):
  days=(date.fromisoformat(r['accrual_date'])-date.fromisoformat(l['accrual_date'])).days
  if days<=30 and l['doc_ref']!=r['doc_ref']:c.append((l['txn_id'],r['txn_id'],days))
print('dups',len(c),c[:20])
