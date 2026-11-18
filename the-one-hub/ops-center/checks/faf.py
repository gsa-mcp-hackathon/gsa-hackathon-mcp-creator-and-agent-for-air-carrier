import csv,sys,collections
p=sys.argv[1]
rows=list(csv.DictReader(open(p,newline='',encoding='utf-8-sig')))
def f(x):
    try: return float(x) if x not in ('','None') else 0.0
    except: return 0.0
print(f"rows: {len(rows)}")
tas=collections.defaultdict(float); fed=collections.defaultdict(float)
oc=collections.defaultdict(float); pa=collections.defaultdict(float)
boa=collections.defaultdict(float); dr=collections.defaultdict(float)
for r in rows:
    a=f(r['transaction_obligated_amount'])
    tas[(r['treasury_account_symbol'],r['treasury_account_name'])]+=a
    fed[(r['federal_account_symbol'],r['federal_account_name'])]+=a
    oc[(r['object_class_code'],r['object_class_name'])]+=a
    pa[(r['program_activity_code'],r['program_activity_name'])]+=a
    boa[(r['beginning_period_of_availability'],r['ending_period_of_availability'],r['availability_type_code'])]+=a
    dr[r['direct_or_reimbursable_funding_source']]+=a
tot=sum(tas.values())
print(f"total transaction_obligated_amount: {tot:,.0f}\n")
def dump(t,d,n=40):
    print(f"=== {t} ===")
    for k,v in sorted(d.items(), key=lambda x:-abs(x[1]))[:n]:
        key=" | ".join(str(x) for x in k) if isinstance(k,tuple) else str(k)
        print(f"  {v:>18,.0f}  {v/tot*100:>6.2f}%  {key}")
    print()
dump("FEDERAL ACCOUNT", fed)
dump("TREASURY ACCOUNT SYMBOL (TAS)", tas)
dump("PERIOD OF AVAILABILITY  (BPOA | EPOA | avail type)", boa)
dump("PROGRAM ACTIVITY", pa)
dump("OBJECT CLASS", oc)
dump("DIRECT vs REIMBURSABLE", dr)
