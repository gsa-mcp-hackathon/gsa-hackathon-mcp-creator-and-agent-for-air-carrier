# Databricks notebook source
# DBTITLE 1,About
# MAGIC %md
# MAGIC Lossless load of every `route: table` artifact in the manifest into `users.xiaobing_shang1_civ.aircarrier_src_*`.
# MAGIC
# MAGIC Every value is the verbatim source string, with no casting and no trimming. `_row_num` is the 1-based data row (for XLSX, the true sheet row). `_row_sha` hashes the row's values. Original column names are kept in `aircarrier_src_registry.column_map`.
# MAGIC
# MAGIC Never sum `total_dollars_obligated`: it is a per-row award running total. Obligations come from `federal_action_obligation` only (D33).

# COMMAND ----------

# DBTITLE 1,Install
# MAGIC %pip install -q openpyxl

# COMMAND ----------

# DBTITLE 1,Load
import re, json, os, csv, hashlib, datetime, openpyxl
V='/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts'; SCH='users.xiaobing_shang1_civ'; P='aircarrier_src_'
NAMES={'bb04f07db2b9930e':'funding_history','a6adf9a91a288732':'2116_assistance_award_summaries','820f6518a106420a':'2116_assistance_transactions',
 '569615b89ef0d871':'2116_contract_award_summaries','cf1037ec4fc2cbbd':'2116_contract_transactions','4eba38f4679fdc88':'2114_federal_account_funding',
 '5fcab4f92d1a9c3c':'2114_subawards','5e11a9f653f60044':'2114_contract_transactions','d9d9b42747d1e8ac':'2114_data_dictionary'}
BUILT=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
def safe(c,seen):
    s=re.sub(r'[^0-9a-zA-Z_]','_',c.strip()).strip('_').lower() or 'col'
    if s[0].isdigit(): s='c_'+s
    b=s; k=2
    while s in seen: s=f'{b}_{k}'; k+=1
    seen.add(s); return s
reg=[]
def write(aid,tname,header,data,src_locator):
    seen={'_artifact_id','_row_num','_row_sha','_source_locator'}; cols=[safe(h,seen) for h in header]
    schema=', '.join(f'`{c}` string' for c in cols)+', _artifact_id string, _row_num int, _row_sha string, _source_locator string'
    rows=[]
    for i,r in data:
        vals=[None if v is None else str(v) for v in r]+[None]*(len(cols)-len(r))
        rows.append(tuple(vals)+(aid,i,hashlib.sha256(json.dumps(vals,ensure_ascii=False).encode()).hexdigest(),src_locator))
    full=f'{SCH}.{P}{tname}'
    spark.createDataFrame(rows,schema).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(full)
    spark.sql(f"COMMENT ON TABLE {full} IS 'Lossless load of artifact {aid} ({src_locator}). Every value is the verbatim source string; no casting, no trimming. _row_num is the 1-based data row in the source. Column names sanitized; originals in aircarrier_src_registry.column_map.'")
    reg.append(dict(table_name=full,artifact_id=aid,source_locator=src_locator,rows_in_source=len(data),ncols=len(cols),column_map=json.dumps(dict(zip(cols,header))),built_at=BUILT))
m=json.load(open(V+'/MANIFEST.json'))
for r in [x for x in m['rows'] if x['route']=='table']:
    aid=r['artifact_id']; d=f'{V}/{aid}'; p=f'{d}/{os.listdir(d)[0]}'
    assert hashlib.sha256(open(p,'rb').read()).hexdigest()==r['sha256'], f'sha mismatch {aid}'
    assert aid in NAMES, f'new table artifact {aid} {r["path"]}: add a table name to NAMES'
    if r['suffix']=='csv':
        with open(p,newline='',encoding='utf-8-sig') as fh: allrows=list(csv.reader(fh))
        assert all(len(x)==len(allrows[0]) for x in allrows), f'ragged rows in {aid}'
        write(aid,NAMES[aid],allrows[0],list(enumerate(allrows[1:],1)),r['path'])
    else:
        wb=openpyxl.load_workbook(p,data_only=False,read_only=True)
        for ws in wb.worksheets:
            nonempty=[(i,list(x)) for i,x in enumerate(ws.iter_rows(values_only=True),1) if any(c is not None for c in x)]
            if not nonempty: continue
            hi,h=nonempty[0]; width=max(len(v) for _,v in nonempty)
            hdr=[str(x) if x is not None else f'col{j+1}' for j,x in enumerate(h+[None]*(width-len(h)))]
            write(aid,NAMES[aid]+'_'+re.sub(r'[^0-9a-z]+','_',ws.title.lower()).strip('_'),hdr,nonempty[1:],f"{r['path']}#{ws.title} (header row {hi}; _row_num = sheet row)")
spark.createDataFrame(reg).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{SCH}.{P}registry')
for x in reg: print(x['table_name'],x['rows_in_source'],x['ncols'])

# COMMAND ----------

# DBTITLE 1,Known-answer gate (fails the run)
import decimal
for t,n,s in (('2116_contract_transactions',948,'4519300323.83'),('2114_contract_transactions',927,'4578603345.77')):
    r=spark.sql(f"SELECT count(*) n, sum(cast(federal_action_obligation as decimal(20,2))) s, count(distinct _row_sha) u FROM {SCH}.{P}{t}").first()
    assert r.n==n and r.u==n and r.s==decimal.Decimal(s), f'{t}: {r}'
    print(t,'PASSED',r.n,r.s)

# COMMAND ----------

