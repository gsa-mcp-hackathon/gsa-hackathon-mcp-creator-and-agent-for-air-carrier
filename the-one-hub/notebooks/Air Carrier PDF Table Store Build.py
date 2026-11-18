# Databricks notebook source
# DBTITLE 1,About
# MAGIC %md
# MAGIC Builds the lossless PDF store. Tables are never chunked.
# MAGIC
# MAGIC * `aircarrier_pdf_pages`: full page text, page legends and exhibit ids for every page of every PDF in the manifest.
# MAGIC * `aircarrier_pdf_tables`: every detected table as one row. Holds the full grid (JSON plus markdown), header rows, column headers, title block, page legends, a grid sha256, and `continuation_of` for tables that run across pages.
# MAGIC * `aircarrier_pdf_cells`: one row per cell. Carries the verbatim `value`, `value_kind` (number, dash, text or empty), `value_num` as a decimal string, `row_header`, `col_header` and the page legends.
# MAGIC
# MAGIC Extractor: pdfplumber 0.11.4 `find_tables()` with default settings. Header rule hdr/v1: header rows are the rows above the first row with a number in any column of index 1 or higher. Only rows with at least 2 non-empty cells beyond column 0 contribute column headers, forward-filled to the right. Cell coordinates are the truth; headers are derived and named by their rule.

# COMMAND ----------

# DBTITLE 1,Install
# MAGIC %pip install -q pdfplumber==0.11.4

# COMMAND ----------

# DBTITLE 1,Extract
import re, json, hashlib, os, decimal, datetime
import pdfplumber
V='/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts'; SCH='users.xiaobing_shang1_civ'
BUILT=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
LEGEND=re.compile(r"^\s*(?:\(\s*[\*†‡§¶#]+\s*\)\s*\w|[\*†‡§¶#]+\s*[-–—:]?\s*\w|notes?\s*\d*\s*[:\-]|footnotes?\s*[:\-]|legend\s*[:\-]|source\s*[:\-]|[A-Z]{2,8}\s*[=–—-]\s*[A-Z])",re.I)
INLINE_LEGEND=re.compile(r"\(\s*[\*†‡§¶#]+\s*\)\s*indicates[^.\n]*",re.I)
EXHIBIT=re.compile(r"\b(P-\d+[a-z]?|R-\d+[a-z]?|O-\d+[a-z]?|Exhibit\s+[A-Z]-\d+[a-z]?)\b")
NUM=re.compile(r"^\(?-?\$?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?%?$|^\(?-?\$?\s?\d+(?:\.\d+)?\)?%?$")
def norm(c): return '' if c is None else str(c)
def legends_of(text):
    out=[s.strip() for s in text.splitlines() if 3<len(s.strip())<300 and LEGEND.match(s.strip())]
    out+=[m.group(0).strip() for m in INLINE_LEGEND.finditer(text)]
    seen=set(); return [x for x in out if not (x in seen or seen.add(x))]
def kind(v):
    s=v.strip()
    if s=='': return 'empty',None
    if s in ('-','–','—','--'): return 'dash',None
    if NUM.match(s.replace(' ','')):
        t=s.replace('$','').replace(',','').replace('%','').replace(' ','')
        neg=t.startswith('(') and t.endswith(')'); t=t.strip('()')
        try: d=decimal.Decimal(t); return 'number', str(-d if neg else d)
        except Exception: pass
    return 'text',None
def header_split(g):
    for i,r in enumerate(g):
        if any(kind(norm(c))[0]=='number' for c in r[1:]): return i
    return len(g)
def col_headers(g,first):
    ncol=max(len(r) for r in g); hdr=[[] for _ in range(ncol)]
    for i in range(first):
        r=[norm(c).replace('\n',' ').strip() for c in g[i]]+['']*(ncol-len(g[i]))
        if sum(1 for c in r[1:] if c)<2: continue
        cur=''
        for j in range(1,ncol):
            if r[j]: cur=r[j]
            if cur and (not hdr[j] or hdr[j][-1]!=cur): hdr[j].append(cur)
    return [' > '.join(h) for h in hdr]
def md(g):
    ncol=max(len(r) for r in g); rows=[[norm(c).replace('\n',' ').replace('|','\\|') for c in r]+['']*(ncol-len(r)) for r in g]
    return '\n'.join(['| '+' | '.join(rows[0])+' |','|'+'---|'*ncol]+['| '+' | '.join(r)+' |' for r in rows[1:]])
# Two extractors, tagged on every table and cell so a reviewer knows how a figure was reconstructed (BLUEPRINT s13):
#   pdfplumber-lines/v1  ruled tables (default find_tables). Grid and headers are reliable.
#   pdfplumber-text/v1   fallback on pages whose figures fell outside every ruled table: whitespace-aligned
#                        columns. Cell VALUES are verbatim; col_header is a best effort, because the text
#                        strategy splits header words across columns. Key fallback lookups on row_header + col_idx.
LINES='pdfplumber-lines/v1'; TEXT='pdfplumber-text/v1'
TS={'vertical_strategy':'text','horizontal_strategy':'text','snap_tolerance':3,'join_tolerance':3,'intersection_tolerance':5,'text_x_tolerance':2}
COMMA_NUM=re.compile(r'[0-9]{1,3},[0-9]{3}')
def extract_pdf(aid,fname,path):
    P,T,C=[],[],[]; prev={}
    with pdfplumber.open(path) as pdf:
        for pn,pg in enumerate(pdf.pages,1):
            text=pg.extract_text() or ''
            leg=legends_of(text); exh=sorted(set(m.group(1) for m in EXHIBIT.finditer(text)))
            try: tabs=pg.find_tables()
            except Exception as e: tabs=[]; leg=leg+[f'[table detection failed: {type(e).__name__}]']
            cur={}; nnum={'n':0}
            def take(t,ti,ext):
                g=[[norm(c) for c in r] for r in t.extract()]
                if not g or not any(any(c.strip() for c in r) for r in g): return
                ncol=max(len(r) for r in g); first=header_split(g); ch=col_headers(g,first)
                tleg=leg+[x for x in legends_of('\n'.join(c for r in g for c in r)) if x not in leg]
                tid=f'{aid}:{pn:04d}:{ti:02d}'
                title=[norm(c).replace('\n',' ').strip() for r in g[:first] for c in r if norm(c).strip() and sum(1 for x in r[1:] if norm(x).strip())<2][:6]
                sig=(ncol,tuple(tuple(r) for r in g[:first]))
                pv=prev.get(ext)
                cont=pv[0] if pv and pv[1]==pn-1 and pv[2]==sig and first>0 else None
                gj=json.dumps(g,ensure_ascii=False)
                T.append(dict(table_id=tid,artifact_id=aid,filename=fname,page=pn,table_idx=ti,extractor=ext,bbox=json.dumps([round(x,1) for x in t.bbox]),n_rows=len(g),n_cols=ncol,
                    header_rows=first,col_headers=json.dumps(ch,ensure_ascii=False),title_block=json.dumps(title,ensure_ascii=False),legends=tleg,exhibits=exh,
                    continuation_of=cont,grid_json=gj,grid_sha=hashlib.sha256(gj.encode()).hexdigest(),markdown=md(g)))
                for i,r in enumerate(g):
                    rh=r[0].replace('\n',' ').strip() if r else ''
                    for j in range(ncol):
                        v=r[j] if j<len(r) else ''
                        k,num=kind(v); nnum['n']+= k=='number'
                        C.append(dict(table_id=tid,artifact_id=aid,page=pn,row_idx=i,col_idx=j,value=v,value_kind=k,value_num=num,is_header=i<first,
                            row_header=rh if j>0 else None,col_header=ch[j] if j>0 and i>=first else None,legends=tleg,extractor=ext))
                cur[ext]=(tid,pn,sig)
            for ti,t in enumerate(tabs): take(t,ti,LINES)
            fallback=[]
            if len(COMMA_NUM.findall(text))>=5 and nnum['n']<5:
                try: fallback=pg.find_tables(table_settings=TS)
                except Exception as e: leg=leg+[f'[text-table detection failed: {type(e).__name__}]']
                for k,t in enumerate(fallback): take(t,50+k,TEXT)
            P.append(dict(artifact_id=aid,filename=fname,page=pn,text=text,chars=len(text),n_tables=len(tabs),n_text_tables=len(fallback),legends=leg,exhibits=exh))
            prev=cur
    return P,T,C

m=json.load(open(V+'/MANIFEST.json'))
AP,AT,AC=[],[],[]
for r in m['rows']:
    if r['suffix']!='pdf': continue
    d=f"{V}/{r['artifact_id']}"; p=f"{d}/{os.listdir(d)[0]}"
    assert hashlib.sha256(open(p,'rb').read()).hexdigest()==r['sha256'], f"sha mismatch {r['artifact_id']}"
    P,T,C=extract_pdf(r['artifact_id'],r['filename'],p)
    for x in P: x.update(grade=r['grade'],zone=r['zone'])
    AP+=P; AT+=T; AC+=C
    print(r['artifact_id'],r['filename'][:50],'pages',len(P),'tables',len(T),'cells',len(C))

# COMMAND ----------

# DBTITLE 1,Write tables
def save(rows,name,schema,comment):
    full=f'{SCH}.aircarrier_pdf_{name}'
    cols=[c.split()[0] for c in schema.split(', ')]
    spark.createDataFrame([tuple(BUILT if c=='built_at' else x.get(c) for c in cols) for x in rows],schema).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(full)
    spark.sql(f"COMMENT ON TABLE {full} IS '{comment}'")
    print(full, len(rows))
save(AP,'pages','artifact_id string, filename string, page int, text string, chars int, n_tables int, n_text_tables int, legends array<string>, exhibits array<string>, grade string, zone string, built_at string',
     'Full page text of every PDF page (pdfplumber), with legends and exhibit ids. Retained so re-reading costs inference only.')
save(AT,'tables','table_id string, artifact_id string, filename string, page int, table_idx int, extractor string, bbox string, n_rows int, n_cols int, header_rows int, col_headers string, title_block string, legends array<string>, exhibits array<string>, continuation_of string, grid_json string, grid_sha string, markdown string, built_at string',
     'One row per PDF table, whole and never chunked. grid_json is the verbatim pdfplumber grid. continuation_of links a table to the same table on the previous page.')
save(AC,'cells','table_id string, artifact_id string, page int, row_idx int, col_idx int, value string, value_kind string, value_num string, is_header boolean, row_header string, col_header string, legends array<string>, extractor string, built_at string',
     'One row per PDF table cell. value is verbatim; value_num is an exact decimal string. Every cell carries its page legends. Headers derived by rule hdr/v1.')

# COMMAND ----------

# DBTITLE 1,Validate P-5c against RING0 N.1
# MAGIC %sql
# MAGIC -- Known answers: RING0 N.1, PB27 SCN P-5c, FY2013 column (CVN-79). Every row must say MATCH, and the categories must sum to the total.
# MAGIC WITH expected(row_header, usd_m) AS (VALUES
# MAGIC  ('Plan Costs','898.865'),('Basic Construction/Conversion','8463.156'),('Change Orders','432.065'),('Electronics (†)','263.359'),
# MAGIC  ('Propulsion Equipment','2041.582'),('Hull, Mechanical, and Electrical (HM&E) (†)','30.302'),('Ordnance (†)','1149.651'),('Other Cost','130.990'),('Total Ship Estimate','13409.970')),
# MAGIC got AS (
# MAGIC  SELECT c.row_header, c.value_num, c.value, c.table_id, c.page, c.legends FROM users.xiaobing_shang1_civ.aircarrier_pdf_cells c
# MAGIC  JOIN users.xiaobing_shang1_civ.aircarrier_pdf_tables t USING (table_id)
# MAGIC  WHERE t.artifact_id='bb2e90fd1d91a0bc' AND exists(t.exhibits, x -> x RLIKE 'P-5c$') AND c.col_header='FY 2013 > Total Cost ($ M)' AND c.value_kind='number')
# MAGIC SELECT e.row_header, e.usd_m expected, g.value_num got, g.page, g.table_id,
# MAGIC  CASE WHEN CAST(g.value_num AS DECIMAL(20,3))=CAST(e.usd_m AS DECIMAL(20,3)) THEN 'MATCH' ELSE 'MISMATCH' END verdict,
# MAGIC  exists(g.legends, x -> x LIKE '%indicates the presence of a P-8a%') dagger_legend_attached
# MAGIC FROM expected e LEFT JOIN got g ON g.row_header=e.row_header
# MAGIC UNION ALL
# MAGIC SELECT 'SUM of 8 categories', '13409.970', CAST(SUM(CAST(g.value_num AS DECIMAL(20,3))) AS STRING), NULL, NULL,
# MAGIC  CASE WHEN SUM(CAST(g.value_num AS DECIMAL(20,3)))=13409.970 THEN 'MATCH' ELSE 'MISMATCH' END, NULL
# MAGIC FROM got g WHERE g.row_header IN (SELECT row_header FROM expected WHERE row_header<>'Total Ship Estimate')

# COMMAND ----------

# DBTITLE 1,Known-answer gate (fails the run)
# Fails the job if the store stops reproducing RING0 N.1. Negative-tested 2026-11-08: one changed value is caught.
import decimal
rows=spark.sql("""SELECT c.row_header, c.value_num, c.legends FROM users.xiaobing_shang1_civ.aircarrier_pdf_cells c
 JOIN users.xiaobing_shang1_civ.aircarrier_pdf_tables t USING (table_id)
 WHERE t.artifact_id='bb2e90fd1d91a0bc' AND exists(t.exhibits, x -> x RLIKE 'P-5c$')
 AND c.col_header='FY 2013 > Total Cost ($ M)' AND c.value_kind='number'""").collect()
exp={'Plan Costs':'898.865','Basic Construction/Conversion':'8463.156','Change Orders':'432.065','Electronics (†)':'263.359','Propulsion Equipment':'2041.582',
     'Hull, Mechanical, and Electrical (HM&E) (†)':'30.302','Ordnance (†)':'1149.651','Other Cost':'130.990','Total Ship Estimate':'13409.970'}
got={}
for r in rows:
    if r.row_header in exp: got.setdefault(r.row_header,[]).append(r)
bad=[k for k,v in exp.items() if len(got.get(k,[]))!=1 or decimal.Decimal(got[k][0].value_num)!=decimal.Decimal(v)
     or not any('indicates the presence of a P-8a' in x for x in got[k][0].legends)]
cats=sum(decimal.Decimal(got[k][0].value_num) for k in exp if k!='Total Ship Estimate' and k in got)
assert not bad and cats==decimal.Decimal('13409.970'), f'P-5c known-answer gate FAILED: {bad}, category sum {cats}'
print('P-5c known-answer gate PASSED: 9/9 cells, categories sum to 13409.970, dagger legend attached')

# COMMAND ----------

# DBTITLE 1,Fallback known-answer gate (fails the run)
# CRS RS20643 Table 2, p.14 (no ruled table, so only the text fallback recovers it). CVN-79 estimated procurement
# cost is grid column 3. Known answers from the record: E-2 (FY19 budget 11,341.4) and N.1 (FY26 figure 13,196.0).
rows=spark.sql("""SELECT row_header, col_idx, value, extractor FROM users.xiaobing_shang1_civ.aircarrier_pdf_cells
 WHERE artifact_id='91d338a069b1b0c9' AND page=14 AND extractor='pdfplumber-text/v1' AND col_idx=3 AND row_header IN ('FY19','FY26')""").collect()
got={r.row_header:[x.value for x in rows if x.row_header==r.row_header] for r in rows}
assert got=={'FY19':['11,341.4'],'FY26':['13,196.0']}, f'CRS fallback gate FAILED: {got}'
lines=spark.sql("SELECT count(*) n FROM users.xiaobing_shang1_civ.aircarrier_pdf_tables WHERE extractor='pdfplumber-lines/v1'").first().n
assert lines==700, f'ruled-table count moved: {lines} (was 700). The fallback must not change ruled extraction.'
print('Fallback gate PASSED: FY19 11,341.4 and FY26 13,196.0 recovered; ruled tables unchanged at 700')

# COMMAND ----------

