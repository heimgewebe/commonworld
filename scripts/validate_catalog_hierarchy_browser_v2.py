#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE=ROOT/'docs/evidence/catalog-hierarchy-browser-v2.json'
def require(condition:bool,message:str)->None:
    if not condition: raise ValueError(message)
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def checked_path(root:Path,value:Any,label:str)->Path:
    require(isinstance(value,str) and value.startswith('/') and '\x00' not in value,f'{label} path is invalid')
    target=(root/value.lstrip('/')).resolve();require(target!=root.resolve() and root.resolve() in target.parents,f'{label} path escapes root');require(target.is_file(),f'{label} file is missing');return target
def descriptor(value:Any,root:Path,label:str)->Path:
    require(isinstance(value,dict) and set(value)=={'path','bytes','sha256'},f'{label} descriptor shape mismatch');target=checked_path(root,value.get('path'),label);payload=target.read_bytes();require(value.get('bytes')==len(payload),f'{label} byte length mismatch');require(value.get('sha256')==digest(payload),f'{label} SHA-256 mismatch');return target
def paths(requests:Any,root:Path,label:str)->list[str]:
    require(isinstance(requests,list),f'{label} requests invalid');result=[]
    for i,item in enumerate(requests):descriptor(item,root,f'{label} request {i}');result.append(item['path'])
    return result
def reject_timing(value:Any,path='evidence')->None:
    if isinstance(value,dict):
        for key,child in value.items():require(not any(token in key.lower() for token in ('timing','duration','elapsed','latency')),f'unstable timing field is forbidden: {path}.{key}');reject_timing(child,f'{path}.{key}')
    elif isinstance(value,list):
        for i,child in enumerate(value):reject_timing(child,f'{path}[{i}]')
def validate_browser_evidence(evidence:dict,root:Path=ROOT)->None:
    require(evidence.get('kind')=='commonworld.catalog_hierarchy_browser_evidence','browser evidence kind mismatch');require(evidence.get('version')=='1.0','browser evidence version mismatch');require(evidence.get('task_id')=='COMMONWORLD-PUBLIC-GLOBE-V1-T039','browser evidence task mismatch');reject_timing(evidence)
    browser=evidence.get('browser');require(isinstance(browser,dict) and browser.get('engine')=='chromium' and isinstance(browser.get('version'),str) and browser['version'],'browser identity mismatch');descriptor(evidence.get('runtime_module'),root,'runtime module')
    v1=json.loads((root/'catalog/runtime/manifest.v1.json').read_text());v2=json.loads((root/'catalog/runtime/manifest.v2.json').read_text());aggregate=json.loads((root/'catalog/runtime/aggregate.v2.json').read_text())
    require(evidence.get('source_catalog_sha256')==v2.get('source_catalog_sha256'),'browser source mismatch');require(evidence.get('default_runtime')=={'manifest_url':'catalog/runtime/manifest.v1.json','manifest_version':'1.0','shard_prefix_length':2},'browser default runtime mismatch');require(evidence.get('candidate_runtime')=={'manifest_url':'catalog/runtime/manifest.v2.json','manifest_version':'2.0','index_prefix_length':1,'leaf_prefix_length':3,'cutover_authorized':False,'rollback_manifest_url':'catalog/runtime/manifest.v1.json'},'browser candidate runtime mismatch');require(v1.get('version')=='1.0' and v1.get('shards',{}).get('prefix_length')==2,'current v1 drift');require(v2.get('migration_guard',{}).get('cutover_authorized') is False,'current v2 guard drift')
    scenarios=evidence.get('scenarios');require(isinstance(scenarios,dict) and set(scenarios)=={'candidate_root','default_rollback','theme_selection','leaf_load','corrupt_segment'},'browser scenario inventory mismatch')
    candidate=scenarios['candidate_root'];require(candidate.get('verdict')=='pass' and candidate.get('manifest_version')=='2.0' and candidate.get('aggregate_version')=='2.0','candidate root failed');require(paths(candidate.get('requests'),root,'candidate root')==['/catalog/runtime/manifest.v2.json','/catalog/runtime/aggregate.v2.json'],'candidate root request contract mismatch')
    default=scenarios['default_rollback'];require(default.get('verdict')=='pass' and default.get('manifest_version')=='1.0' and default.get('aggregate_version')=='1.0','default rollback failed');require(paths(default.get('requests'),root,'default rollback')==['/catalog/runtime/manifest.v1.json','/catalog/runtime/aggregate.v1.json'],'default rollback request contract mismatch')
    selection=scenarios['theme_selection'];require(selection.get('verdict')=='pass' and isinstance(selection.get('theme'),str) and selection['theme'],'theme selection failed');seg_desc=next((x for x in aggregate['segments']['themes'] if x.get('key')==selection.get('segment_key')),None);require(isinstance(seg_desc,dict),'theme segment undeclared');seg_path=f"/{seg_desc['url']}";require(paths(selection.get('requests'),root,'theme selection')==[seg_path],'theme selection fetched extra resources');segment=json.loads((root/seg_desc['url']).read_text());require(selection.get('selected_shard_keys')==segment.get('index',{}).get(selection['theme']),'theme selection shard set mismatch');selected=selection['selected_shard_keys'];require(isinstance(selected,list) and selected,'theme selection produced no shard')
    leaf=scenarios['leaf_load'];require(leaf.get('verdict')=='pass' and leaf.get('shard_key')==selected[0],'leaf identity mismatch');key=leaf['shard_key'];index_key=key[:v2['shards']['index_prefix_length']];idx_desc=next((x for x in v2['shards']['indexes'] if x.get('key')==index_key),None);require(isinstance(idx_desc,dict),'leaf index missing');idx=json.loads((root/idx_desc['url']).read_text());leaf_desc=next((x for x in idx['entries'] if x.get('key')==key),None);require(isinstance(leaf_desc,dict),'leaf descriptor missing');require(paths(leaf.get('requests'),root,'leaf load')==[f"/{idx_desc['url']}",f"/{leaf_desc['url']}"],'leaf request contract mismatch');payload=json.loads((root/leaf_desc['url']).read_text());require(leaf.get('record_ids')==[r['id'] for r in payload['records']],'leaf records mismatch')
    corrupt=scenarios['corrupt_segment'];require(corrupt.get('verdict')=='rejected','corrupt segment was not rejected');require(corrupt.get('target_path')==seg_path,'corrupt target mismatch');require(paths(corrupt.get('requests'),root,'corrupt segment')==[seg_path],'corrupt request contract mismatch');require(isinstance(corrupt.get('error'),str) and ('byte length mismatch' in corrupt['error'] or 'SHA-256 mismatch' in corrupt['error']),'corrupt rejection reason mismatch')
    require(evidence.get('decision')=={'browser_transfer_budget_state':'pass','runtime_catalogue_cutover_authorized':False},'browser decision mismatch')
def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,default=DEFAULT_EVIDENCE);args=parser.parse_args();validate_browser_evidence(json.loads(args.evidence.read_text()));print(f'catalog hierarchy browser evidence valid: {args.evidence.relative_to(ROOT)}');return 0
if __name__=='__main__':raise SystemExit(main())
