import csv,sys,collections
p=sys.argv[1]
rows=list(csv.DictReader(open(p,newline='',encoding='utf-8-sig')))
print(f"transactions: {len(rows)}")
def f(x):
    try: return float(x) if x not in ('','None') else 0.0
    except: return 0.0
tot_obl=sum(f(r['federal_action_obligation']) for r in rows)
rows.sort(key=lambda r:r['action_date'])
last=rows[-1]
print("\n=== AWARD-LEVEL (latest transaction) ===")
for k in ['award_id_piid','action_date','total_dollars_obligated','base_and_exercised_options_value',
          'current_total_value_of_award','base_and_all_options_value','potential_total_value_of_award',
          'total_outlayed_amount_for_overall_award','period_of_performance_current_end_date',
          'period_of_performance_potential_end_date','awarding_office_name','funding_office_name',
          'recipient_name','recipient_uei','cage_code' if 'cage_code' in last else 'award_id_piid']:
    if k in last: print(f"  {k:<46} {last[k]}")
print(f"\n  SUM of federal_action_obligation across all transactions: {tot_obl:,.0f}")
print("\n=== OBLIGATION BY FISCAL YEAR ===")
byfy=collections.defaultdict(float); cnt=collections.Counter()
for r in rows:
    fy=r['action_date_fiscal_year']; byfy[fy]+=f(r['federal_action_obligation']); cnt[fy]+=1
run=0
print(f"  {'FY':<6}{'txns':>6}{'obligated $':>18}{'cumulative $':>18}")
for fy in sorted(byfy):
    run+=byfy[fy]; print(f"  {fy:<6}{cnt[fy]:>6}{byfy[fy]:>18,.0f}{run:>18,.0f}")
print("\n=== LARGEST 25 TRANSACTIONS ===")
big=sorted(rows,key=lambda r:-abs(f(r['federal_action_obligation'])))[:25]
print(f"  {'date':<12}{'mod':<10}{'obligation $':>16}  description")
for r in big:
    d=(r.get('transaction_description') or r.get('prime_award_base_transaction_description') or '')[:88]
    print(f"  {r['action_date']:<12}{r['modification_number'][:9]:<10}{f(r['federal_action_obligation']):>16,.0f}  {d}")
neg=[r for r in rows if f(r['federal_action_obligation'])<0]
print(f"\n  negative (deobligating) transactions: {len(neg)}  totalling {sum(f(r['federal_action_obligation']) for r in neg):,.0f}")
