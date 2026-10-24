"""Compare the port against the unchanged upstream pure function (Python stdlib only)."""
import ast, itertools, json, pathlib, subprocess
root=pathlib.Path(__file__).resolve().parents[2]
tree=ast.parse((root/'vendor/parnita/recommender_engine.py').read_text())
tree.body=[n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef))]
scope={};exec(compile(tree,'upstream','exec'),scope)
cases=[]
for history in itertools.product(scope['CROP_DATABASE'],repeat=3):
 for ph,ec,texture in [(6.5,.5,'Loam'),(8.2,.5,'Loam'),(6.5,3.5,'Loam'),(5.2,2,'Clay'),(7.5,2.01,'Sand'),(None,None,'Unknown Texture'),(6,0,'Silt Loam'),(7.8,9.4,'Sandy Loam')]:
  soil={'in_central_valley':True,'ph':ph,'salinity_ec_ds_m':ec,'texture_name':texture}
  cases.append({'history':history,'soil':soil,'expected':scope['evaluate_next_crops'](history,soil)})
js="""import {evaluateNextCrops} from './lib/crop-model.mjs';
import assert from 'node:assert/strict';
let input='';for await(const chunk of process.stdin)input+=chunk;
const cases=JSON.parse(input);
// Python formats integer-valued floats with .0; normalize only that textual difference.
const normalize=s=>s.replace(/(\\d)\\.0(?=[^\\d]|$)/g,'$1');
for(const c of cases){const actual=evaluateNextCrops(c.history,c.soil);assert.deepEqual(actual.map(r=>({...r,reasons:r.reasons.map(normalize)})),c.expected.map(r=>({...r,reasons:r.reasons.map(normalize)})));}
console.log(`PASS: ${cases.length} Python/JavaScript parity cases, all seven crops, scores, order and reasons.`);
"""
subprocess.run(['node','--input-type=module','-e',js],input=json.dumps(cases),text=True,cwd=root,check=True)
