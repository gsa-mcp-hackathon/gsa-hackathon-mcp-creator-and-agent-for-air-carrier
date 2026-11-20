# Databricks notebook source
# DBTITLE 1,About
# MAGIC %md
# MAGIC Builds `users.xiaobing_shang1_civ.aircarrier_kg_nodes` and `aircarrier_kg_edges`. Deterministic, with no model involved.
# MAGIC
# MAGIC Sources: the seed YAMLs, `MANIFEST.json` and the KB chunks. Every mention edge carries its artifact, page, chunk_id and a verbatim snippet. The graph is for navigation and never supplies a figure (D27).
# MAGIC
# MAGIC Rules:
# MAGIC * `variances.index.yaml` and `decisions.index.yaml` are parsed line by line, because yaml.safe_load truncates their topics at unquoted commas.
# MAGIC * E-/G-/D- ids are matched only in WORKING (project) documents.
# MAGIC * PIIDs are matched only on their full form (D34). PIIDs that aren't in the keyset become unregistered lead nodes.

# COMMAND ----------

# DBTITLE 1,Seed graph
import re, json, yaml, hashlib, datetime
from collections import Counter
BUNDLE='/Workspace/Users/xiaobing.shang1.civ@mail.mil/gsa-hackathon-mcp-creator-and-agent-for-cvn/the-one-hub/ops-center'
S=BUNDLE+'/seed'; V='/Volumes/users/xiaobing_shang1_civ/aircarrier_artifacts'
KB='/Volumes/users/xiaobing_shang1_civ/aircarrier_extracted/kb/chunks.json'
T='users.xiaobing_shang1_civ.aircarrier_kg_'
BUILT=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
nodes={}; edges={}
def node(nid,ntype,label,props=None,src_art=None,loc=None,rule='seed',grade=None,zone=None):
    if nid in nodes:
        nodes[nid]['props'].update(props or {}); return nid
    nodes[nid]=dict(node_id=nid,node_type=ntype,label=str(label)[:500],props=dict(props or {}),source_artifact_id=src_art,source_locator=loc,source_rule=rule,grade=grade,zone=zone)
    return nid
def edge(src,rel,dst,rule,ev_art=None,ev_page=None,ev_chunk=None,ev_text=None,props=None):
    eid=hashlib.sha256(f'{src}|{rel}|{dst}|{ev_chunk or ""}|{rule}'.encode()).hexdigest()[:20]
    edges[eid]=dict(edge_id=eid,src=src,rel=rel,dst=dst,rule=rule,evidence_artifact_id=ev_art,evidence_page=ev_page,evidence_chunk_id=ev_chunk,evidence_text=(ev_text or None) and ev_text[:400],props=dict(props or {}))

# The seed files quote topic and enforced (fixed 2026-11-08). The guard fails loudly if an
# unquoted comma ever returns: yaml.safe_load would split the topic into stray keys.
ALLOWED={'id','status','topic','flag','enforced'}
def flow(path):
    key=path.rsplit('/',1)[1].split('.')[0]
    lines=open(path).read().splitlines()
    rows=yaml.safe_load('\n'.join(lines))[key]
    idx=[i for i,l in enumerate(lines,1) if l.strip().startswith('- {')]
    assert len(idx)==len(rows), f'{path}: {len(rows)} rows vs {len(idx)} lines'
    out=[]
    for d,i in zip(rows,idx):
        stray=set(map(str,d))-ALLOWED
        assert not stray, f'{path}:{i} stray keys {stray}: quote the topic'
        out.append(dict(id=d['id'],status=d.get('status'),topic=str(d['topic']).strip(),flag=d.get('flag'),enforced=d.get('enforced'),line=i))
    return out
for v in flow(S+'/variances.index.yaml'):
    n=node(f"variance:{v['id']}",'variance',v['id'],{'status':v['status'],'topic':v['topic'],'flag':v['flag']},loc=f"seed/variances.index.yaml:{v['line']}")
    if v['flag']: edge(n,'flagged',node(f"risk_flag:{v['flag']}",'risk_flag',v['flag']),'seed:variances.flag')
for d in flow(S+'/decisions.index.yaml'):
    n=node(f"decision:{d['id']}",'decision',d['id'],{'topic':d['topic'],'enforced':d['enforced']},loc=f"seed/decisions.index.yaml:{d['line']}")
    for p in re.findall(r'[\w./-]+\.(?:py|yaml)',d['enforced'] or ''):
        edge(n,'enforced_in',node(f'code:{p}','code_path',p),'seed:decisions.enforced')
for g in yaml.safe_load(open(S+'/gaps.index.yaml'))['gaps']:
    n=node(f"gap:{g['id']}",'gap',g['id'],{k:g.get(k) for k in g if k!='id'},loc='seed/gaps.index.yaml')
    edge(n,'has_type',node(f"gap_type:{g['type']}",'gap_type',g['type']),'seed:gaps.type')
    if g.get('executor'): edge(n,'executed_by',node('org:'+g['executor'],'executor',g['executor']),'seed:gaps.executor')
    if g.get('yielded'): edge(n,'yielded',f"variance:{g['yielded']}",'seed:gaps.yielded')
    for txt in (g.get('note') or '',g.get('resolution') or ''):
        for e in re.findall(r'\bE-(\d{1,2})\b',txt): edge(n,'references',f'variance:E-{e}','seed:gaps.text',ev_text=txt.strip())
        for gg in re.findall(r'\bG(\d{1,2})\b',txt):
            if f'G{gg}'!=g['id']: edge(n,'references',f'gap:G{gg}','seed:gaps.text',ev_text=txt.strip())

ks=yaml.safe_load(open(S+'/keyset.yaml'))
hull=node('hull:CVN-79','hull','CVN-79',ks['ship'],loc='seed/keyset.yaml')
def piid_norm(s):
    m=re.fullmatch(r'([A-Z]\d{5})-?(\d{2})-?([A-Z])-?(\d{4})',s.replace(' ','').upper()); return f'{m[1]}-{m[2]}-{m[3]}-{m[4]}' if m else None
for p in ks['contracts']['primes']:
    edge(node('contract:'+piid_norm(p['piid']),'contract',p['piid'],{k:v for k,v in p.items() if k!='piid'},loc='seed/keyset.yaml'),'prime_contract_for',hull,'seed:keyset.primes')
for p in ks['contracts']['other']:
    c=node('contract:'+piid_norm(p['piid']),'contract',p['piid'],{k:v for k,v in p.items() if k!='piid'},loc='seed/keyset.yaml')
    edge(c,'partial_scope_for',hull,'seed:keyset.other',props={'cvn79_share_usd_m':p.get('cvn79_share_usd_m'),'warning':p.get('warning')})
    if p.get('cage'): edge(c,'awarded_to',node('vendor:CAGE-'+p['cage'],'vendor',p['vendor'],{'cage':p['cage']}),'seed:keyset.other')
for x in ks['collisions']['hard_exclusions']:
    bad=node('contract:'+piid_norm(x['not_ours']),'contract',x['not_ours'],{'excluded':True,'why':x['why']},loc='seed/keyset.yaml')
    edge(bad,'excluded_from',hull,'seed:keyset.hard_exclusions',ev_text=x['why'],props={'rule':x.get('rule')})
    if x.get('ours'): edge(bad,'collides_with','contract:'+piid_norm(x['ours']),'seed:keyset.hard_exclusions',props={'rule':x.get('rule')})
    for r in x.get('refs',[]): edge(bad,'references',{'D':'decision:','G':'gap:','E':'variance:'}[r[0]]+r,'seed:keyset.refs')
for x in ks['collisions']['resolved_not_this_hull']:
    c=node('contract:'+piid_norm(x['piid']),'contract',x['piid'],{k:v for k,v in x.items() if k!='piid'},loc='seed/keyset.yaml')
    edge(c,'resolved_not_this_hull',hull,'seed:keyset.resolved_not_this_hull',ev_text=x['verdict'])
    edge(c,'resolved_by','gap:'+x['ref'],'seed:keyset.resolved_not_this_hull')
nc=ks['collisions']['name_collision']
edge(node('hull:CV-67','hull','CV-67',{'why':nc['why']}),'name_collides_with',hull,'seed:keyset.name_collision',ev_text=nc['rule'])
b=ks['budget']
appn=node('appropriation:1611N','appropriation','1611N Shipbuilding and Conversion, Navy',{'tafs_form':b['tafs_form'],'legacy':b['legacy_symbol_form']},loc='seed/keyset.yaml')
edge(appn,'funds',hull,'seed:keyset.budget')
for li,name in b['line_items'].items(): edge(node(f'bli:{li}','budget_line_item',f'BLI {li} {name}'),'line_of',appn,'seed:keyset.line_items')
edge(node('program_element:'+b['program_element'],'program_element',b['program_element']),'funds',hull,'seed:keyset.pe')
edge(node('program_element:'+b['shared_rdte_element'],'program_element',b['shared_rdte_element'],{'shared':True}),'allocation_open_in','gap:G4','seed:keyset.shared_rdte_element')
for o in b['other_appropriations']:
    edge(node('appropriation:'+o['appn'],'appropriation',o['appn'],{k:v for k,v in o.items() if k!='appn'}),'funds',hull,'seed:keyset.other_appropriations')
vd=ks['vendor']; ven=node('vendor:CAGE-'+vd['cage'],'vendor',vd['name'],vd,loc='seed/keyset.yaml')
for p in ks['contracts']['primes']: edge('contract:'+piid_norm(p['piid']),'awarded_to',ven,'seed:keyset.vendor')
for ek,ev in yaml.safe_load(open(S+'/exhibits.yaml'))['exhibits'].items():
    e=node('exhibit:'+ek,'exhibit_type',ek,{'name':ev.get('name'),'family':ev.get('document_family'),'aliases':ev.get('aliases')},loc='seed/exhibits.yaml')
    for al in ev.get('aliases') or []: edge(node('exhibit:'+al,'exhibit_type',al),'alias_of',e,'seed:exhibits.aliases')
    for h in ev.get('hazards') or []:
        hz=node('hazard:'+h['id'],'hazard',h['id'],{'hazard':(h.get('hazard') or '').strip(),'defence':(h.get('defence') or '').strip(),'flag':h.get('flag')})
        edge(e,'has_hazard',hz,'seed:exhibits.hazards')
        if h.get('flag'): node('risk_flag:'+h['flag'],'risk_flag',h['flag']); edge(hz,'flagged','risk_flag:'+h['flag'],'seed:exhibits.flag')
for t in yaml.safe_load(open(S+'/negative_vocabulary.yaml'))['CVN-79']:
    edge(node('neg_term:'+t['term'],'negative_term',t['term'],{'why':t['why']},loc='seed/negative_vocabulary.yaml'),'flagged',node('risk_flag:'+t['flag'],'risk_flag',t['flag']),'seed:negative_vocabulary')
for k,f in yaml.safe_load(open(S+'/gate.yaml'))['violation_to_flag'].items():
    tgt='decision:'+k if k.startswith('D') else 'variance:'+re.sub(r'^E(\d+)$',r'E-\1',k)
    edge(tgt,'violation_raises',node('risk_flag:'+f,'risk_flag',f),'seed:gate.violation_to_flag')
print(len(nodes),len(edges))

# COMMAND ----------

# DBTITLE 1,Document graph
m=json.load(open(V+'/MANIFEST.json'))
for r in m['rows']:
    node('artifact:'+r['artifact_id'],'artifact',r['filename'],{k:r.get(k) for k in ('path','bucket','route','bytes','suffix','establishes','pages','sha256')},src_art=r['artifact_id'],rule='manifest',grade=r['grade'],zone=r['zone'])
for s in m.get('superseded',[]):
    node('artifact:'+s['artifact_id'],'artifact',s['filename'],{'superseded':True,'why':s['why']},src_art=s['artifact_id'],rule='manifest.superseded')
    edge('artifact:'+s['artifact_id'],'superseded_by','artifact:'+s['superseded_by'],'manifest.superseded',props={'on':s['on']})
ch=json.load(open(KB))
PROJECT_IDS={r['artifact_id'] for r in m['rows'] if r['grade']=='WORKING'}
PIID=re.compile(r'\b([A-Z]\d{5})-?(\d{2})-?([A-Z])-?(\d{4})\b')
HULL=re.compile(r'\bCVNs?[\s-]?(\d{2})\b')
EXH=re.compile(r'\b(P-1|P-5c|P-5a|P-5|P-8a|P-10|P-21|P-35|P-40)\b')
IDS=[(re.compile(r'\bE-(\d{1,2})\b'),'variance:E-'),(re.compile(r'\bG(\d{1,2})\b'),'gap:G'),(re.compile(r'\bD(\d{1,2})\b'),'decision:D')]
KEYTERMS={'1611N':'appropriation:1611N','0204112N':'program_element:0204112N','0604112N':'program_element:0604112N','43689':'vendor:CAGE-43689','4V360':'vendor:CAGE-4V360'}
NEG={n['label']:nid for nid,n in nodes.items() if n['node_type']=='negative_term'}
def snip(t,a,b,w=140): return t[max(0,a-w):b+w].replace('\n',' ')
pages=set(); stats=Counter()
for cid,c in ch.items():
    aid=c['artifact_id']; pg=int(c['page']); t=c['text']; pid=f'page:{aid}:{pg:04d}'
    if pid not in pages:
        pages.add(pid); node(pid,'page',f"{c['filename']} p.{pg}",{'page':pg},src_art=aid,loc=f'p.{pg}',rule='kb.chunks',grade=c['grade'],zone=c['zone'])
        edge(pid,'part_of','artifact:'+aid,'kb.chunks')
    def mention(dst,mm,rule):
        edge(pid,'mentions',dst,rule,ev_art=aid,ev_page=pg,ev_chunk=cid,ev_text=snip(t,mm.start(),mm.end())); stats[rule]+=1
    for mm in PIID.finditer(t):
        p=f'{mm[1]}-{mm[2]}-{mm[3]}-{mm[4]}'
        if 'contract:'+p not in nodes or nodes['contract:'+p]['source_rule']=='regex:piid_unregistered':
            node('contract:'+p,'contract',p,{'registered':False,'instrument_letter':mm[3],'note':'seen in corpus, not in seed/keyset.yaml. A lead for the Investigator, not a CVN-79 contract.'},rule='regex:piid_unregistered',zone='L')
            mention('contract:'+p,mm,'regex:piid_unregistered')
        else: mention('contract:'+p,mm,'regex:piid_full')
    for mm in HULL.finditer(t):
        h=f'hull:CVN-{mm[1]}'; node(h,'hull',f'CVN-{mm[1]}',rule='regex:hull'); mention(h,mm,'regex:hull')
    for mm in EXH.finditer(t):
        e='exhibit:'+mm[1]; node(e,'exhibit_type',mm[1],rule='regex:exhibit'); mention(e,mm,'regex:exhibit')
    for term,dst in KEYTERMS.items():
        for mm in re.finditer(r'\b'+re.escape(term)+r'\b',t): mention(dst,mm,'dict:keyset')
    for term,dst in NEG.items():
        for mm in re.finditer(r'\b'+re.escape(term)+r'\b',t,re.I): mention(dst,mm,'dict:negative_vocabulary')
    if aid in PROJECT_IDS:
        for rx,pref in IDS:
            for mm in rx.finditer(t):
                if pref+mm[1] in nodes: mention(pref+mm[1],mm,'regex:project_id')
dangling=[e for e in edges.values() if e['src'] not in nodes or e['dst'] not in nodes]
assert not dangling, dangling[:5]
print(len(nodes),len(edges),stats.most_common())

# COMMAND ----------

# DBTITLE 1,Table-store graph
# Links the lossless table stores into the graph. Run after the PDF and Source Table Store Build notebooks.
# Only facts printed in the table are asserted: exhibit, BLI and appropriation come from the table's title block,
# and PIIDs come from the award's own PIID column. Column-to-hull mapping (e.g. P-5c FY 2013 = CVN-79) is NOT
# asserted here; that is an Attributor crosswalk and must stay DERIVED.
SCH='users.xiaobing_shang1_civ'
TEXH=re.compile(r'Exhibit\s+(P-\d+[a-z]?)\b'); TBLI=re.compile(r'Line Item Number / Title:\s*(\d{4})\b'); TAPP=re.compile(r'Sub Activity:\s*(\d{4}[A-Z])\b')
art={nid[9:]:n for nid,n in nodes.items() if n['node_type']=='artifact'}
ts=Counter()
for t in spark.sql(f'SELECT table_id, artifact_id, filename, page, table_idx, extractor, n_rows, n_cols, header_rows, title_block, continuation_of, grid_sha FROM {SCH}.aircarrier_pdf_tables ORDER BY table_id').collect():
    a=art.get(t.artifact_id,{}); g,z=a.get('grade'),a.get('zone')
    title=json.loads(t.title_block); tid='table:'+t.table_id
    node(tid,'pdf_table',(title[0] if title else f'table {t.table_idx}')+f' ({t.filename} p.{t.page})',
         {'page':t.page,'table_idx':t.table_idx,'extractor':t.extractor,'n_rows':t.n_rows,'n_cols':t.n_cols,'header_rows':t.header_rows,'grid_sha':t.grid_sha,
          'grid':f'{SCH}.aircarrier_pdf_tables','cells':f'{SCH}.aircarrier_pdf_cells'},src_art=t.artifact_id,loc=f'p.{t.page} table {t.table_idx}',rule='store:pdf_tables',grade=g,zone=z)
    ts['table']+=1
    pid=f'page:{t.artifact_id}:{t.page:04d}'
    if pid not in nodes:
        node(pid,'page',f'{t.filename} p.{t.page}',{'page':t.page},src_art=t.artifact_id,loc=f'p.{t.page}',rule='store:pdf_pages',grade=g,zone=z)
        edge(pid,'part_of','artifact:'+t.artifact_id,'store:pdf_pages'); ts['page_added']+=1
    edge(pid,'has_table',tid,'store:pdf_tables',ev_art=t.artifact_id,ev_page=t.page,props={'extractor':t.extractor})
    if t.continuation_of: edge(tid,'continues','table:'+t.continuation_of,'store:pdf_tables.continuation_of',ev_art=t.artifact_id,ev_page=t.page); ts['continues']+=1
    for line in title:
        for rx,pref,rel in ((TEXH,'exhibit:','instance_of'),(TBLI,'bli:','line_item'),(TAPP,'appropriation:','appropriation')):
            mm=rx.search(line)
            if not mm: continue
            dst=pref+mm[1]
            if pref=='exhibit:': node(dst,'exhibit_type',mm[1],rule='store:pdf_tables')
            if dst in nodes: edge(tid,rel,dst,'store:pdf_tables.title_block',ev_art=t.artifact_id,ev_page=t.page,ev_text=line); ts[rel]+=1
            else: ts[rel+'_target_missing']+=1
reg=spark.table(f'{SCH}.aircarrier_src_registry').collect()
for r in reg:
    sid='src_table:'+r.table_name; a=art.get(r.artifact_id,{})
    node(sid,'source_table',r.table_name.split('.')[-1],{'table':r.table_name,'rows':r.rows_in_source,'ncols':r.ncols,'source_locator':r.source_locator},
         src_art=r.artifact_id,loc=r.source_locator,rule='store:src_registry',grade=a.get('grade'),zone=a.get('zone'))
    edge('artifact:'+r.artifact_id,'has_table',sid,'store:src_registry'); ts['source_table']+=1
    for c in [c for c in json.loads(r.column_map) if c in ('award_id_piid','prime_award_piid')]:
        for x in spark.sql(f'SELECT `{c}` v, count(*) n FROM {r.table_name} GROUP BY 1').collect():
            mm=re.fullmatch(r'([A-Z]\d{5})(\d{2})([A-Z])(\d{4})',x.v or '')
            if not mm: ts['piid_unparsed']+=1; continue
            p=f'contract:{mm[1]}-{mm[2]}-{mm[3]}-{mm[4]}'
            if p not in nodes: node(p,'contract',p[9:],{'registered':False,'note':'seen in a source table, not in seed/keyset.yaml'},rule='store:src_piid_unregistered',zone='L')
            edge(sid,'records',p,f'store:src.{c}',ev_art=r.artifact_id,ev_text=f'{c} = {x.v} on {x.n} rows',props={'rows':x.n}); ts['records']+=1
dangling=[e for e in edges.values() if e['src'] not in nodes or e['dst'] not in nodes]
assert not dangling, dangling[:5]
assert ts['table']>=700 and ts['source_table']==len(reg), ts
print(len(nodes),len(edges),dict(ts))

# COMMAND ----------

# DBTITLE 1,Write tables
nschema='node_id string, node_type string, label string, props string, source_artifact_id string, source_locator string, source_rule string, grade string, zone string, built_at string'
eschema='edge_id string, src string, rel string, dst string, rule string, evidence_artifact_id string, evidence_page int, evidence_chunk_id string, evidence_text string, props string, built_at string'
cn=[c.split()[0] for c in nschema.split(', ')]; ce=[c.split()[0] for c in eschema.split(', ')]
N=[tuple(json.dumps(n[c],default=str,sort_keys=True) if c=='props' else (BUILT if c=='built_at' else n.get(c)) for c in cn) for n in nodes.values()]
E=[tuple(json.dumps(e[c],default=str,sort_keys=True) if c=='props' else (BUILT if c=='built_at' else e.get(c)) for c in ce) for e in edges.values()]
spark.createDataFrame(N,nschema).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(T+'nodes')
spark.createDataFrame(E,eschema).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(T+'edges')
spark.sql(f"COMMENT ON TABLE {T}nodes IS 'Air Carrier knowledge graph nodes. Deterministic: seed YAMLs, MANIFEST.json, KB chunks. No model. node_id = type:key.'")
spark.sql(f"COMMENT ON TABLE {T}edges IS 'Air Carrier knowledge graph edges. Mention edges carry artifact, page, chunk_id and verbatim snippet. Navigation only, never a figure (D27).'")
print(len(N),len(E))

# COMMAND ----------

# DBTITLE 1,Verify
# MAGIC %sql
# MAGIC WITH n AS (SELECT * FROM users.xiaobing_shang1_civ.aircarrier_kg_nodes), e AS (SELECT * FROM users.xiaobing_shang1_civ.aircarrier_kg_edges)
# MAGIC SELECT 'dup_node_ids' chk, CAST(COUNT(*)-COUNT(DISTINCT node_id) AS STRING) val FROM n
# MAGIC UNION ALL SELECT 'dangling_edges', CAST(COUNT(*) AS STRING) FROM e LEFT JOIN n s ON e.src=s.node_id LEFT JOIN n d ON e.dst=d.node_id WHERE s.node_id IS NULL OR d.node_id IS NULL
# MAGIC UNION ALL SELECT 'gaps/variances/decisions (expect 28/16/34)', CONCAT(count_if(node_type='gap'),'/',count_if(node_type='variance'),'/',count_if(node_type='decision')) FROM n
# MAGIC UNION ALL SELECT 'E-14 topic (expect 5,880,250)', get_json_object(props,'$.topic') FROM n WHERE node_id='variance:E-14'
# MAGIC UNION ALL SELECT '16-C-2116 edges', concat_ws('; ', sort_array(collect_list(concat(rel,'->',dst)))) FROM e WHERE src='contract:N00024-16-C-2116'
# MAGIC UNION ALL SELECT 'G27 out', concat_ws('; ', sort_array(collect_list(concat(rel,'->',dst)))) FROM e WHERE src='gap:G27'
# MAGIC UNION ALL SELECT 'mention edges missing evidence (expect 0)', CAST(COUNT(*) AS STRING) FROM e WHERE rel='mentions' AND (evidence_chunk_id IS NULL OR evidence_text IS NULL OR evidence_page IS NULL)
# MAGIC UNION ALL SELECT 'P-5c p.95 table links (expect appropriation, instance_of, line_item)', concat_ws('; ', sort_array(collect_list(concat(rel,'->',dst)))) FROM e WHERE src='table:bb2e90fd1d91a0bc:0095:00' AND rel<>'continues'
# MAGIC UNION ALL SELECT 'p.96 continues p.95', CAST(COUNT(*) AS STRING) FROM e WHERE src='table:bb2e90fd1d91a0bc:0096:00' AND rel='continues' AND dst='table:bb2e90fd1d91a0bc:0095:00'
# MAGIC UNION ALL SELECT 'pdf tables in graph / store', CONCAT((SELECT COUNT(*) FROM n WHERE node_type='pdf_table'),'/',(SELECT COUNT(*) FROM users.xiaobing_shang1_civ.aircarrier_pdf_tables))
# MAGIC UNION ALL SELECT 'source tables recording 09-C-2116', concat_ws('; ', sort_array(collect_list(concat(substr(src,37),' ',get_json_object(props,'$.rows'))))) FROM e WHERE rel='records' AND dst='contract:N00024-09-C-2116'
# MAGIC UNION ALL SELECT 'source tables recording 16-C-2116 (expect 0)', CAST(COUNT(*) AS STRING) FROM e WHERE rel='records' AND dst='contract:N00024-16-C-2116'
# MAGIC UNION ALL SELECT 'piid snippet lacks piid (expect 0)', CAST(COUNT(*) AS STRING) FROM e WHERE rule IN ('regex:piid_full','regex:piid_unregistered') AND NOT regexp_replace(evidence_text,'[- ]','') LIKE concat('%',regexp_replace(substr(dst,10),'-',''),'%')