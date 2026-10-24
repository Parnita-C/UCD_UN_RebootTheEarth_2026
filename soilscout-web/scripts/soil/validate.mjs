import {regionalScenario,DEFAULT_IMPLEMENTATION} from '../../lib/regional-model.mjs';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {sampleGrid,advise} from '../../lib/soil-model.mjs';
const data=JSON.parse(readFileSync('public/data/comet-ca.json'));
const record=data.records.find(r=>r.county==='Yolo'&&r.planner_implementation===DEFAULT_IMPLEMENTATION);
assert.equal(data.records.length,2204);
assert.equal(new Set(data.records.map(r=>r.county)).size,58);
assert.equal(record.source_row,43213);
assert.equal(record.lrr_fill,null); // XLSX blank K cell must not shift following values.
assert.equal(record.soil_carbon_co2,.462243799591439);
assert.equal(record.total_ghg_co2,.403777459969602);
for(const r of data.records){
 assert.ok(r.lrr_fill===null||r.lrr_fill===0||r.lrr_fill===1);
 if(r.co2_mean!=null&&r.n2o_mean!=null&&r.total_ghg_co2!=null)assert.ok(Math.abs(r.co2_mean+r.n2o_mean-r.total_ghg_co2)<1e-7);
 for(const key of ['soil_carbon_co2','total_ghg_co2'])assert.notEqual(r[key],-999);
}
const base={record,acres:100,payment:30,buffer:20,delay:1,annualCost:156,annualSavings:0,setup:0};
const p=regionalScenario(base);
assert.ok(Math.abs(p.rows[2].carbon-63.0332453988326)<1e-9);
assert.ok(Math.abs(p.annualReceipts-969.0659039270448)<1e-9);
assert.equal(p.rows[0].cashReceived,0);
assert.ok(Math.abs(p.rows[1].cashReceived-p.annualReceipts*1.2)<1e-9);
assert.ok(Math.abs(p.rows[2].cashReceived-p.annualReceipts*2.9)<1e-9);
assert.equal(p.rows[2].cost,78000);
assert.equal(regionalScenario({...base,annualCost:null}).rows[2].net,null);
assert.equal(regionalScenario({...base,already:true}).rows[2].cashReceived,null);
assert.equal(regionalScenario({...base,record:{...record,cpsnum:336}}).rows[2].cashReceived,null);
assert.equal(regionalScenario({...base,payment:null}).rows[2].cashReceived,null);
assert.equal(regionalScenario({...base,record:{...record,total_ghg_co2:null}}).rows[2].cashReceived,null);
assert.equal(regionalScenario({...base,record:{...record,total_ghg_co2:-.1}}).annualReceipts,0);
assert.ok(regionalScenario({...base,record:{...record,soil_carbon_co2:-.1}}).rows[2].carbon<0);
assert.equal(regionalScenario({...base,eligibleSystem:false}),null);
assert.equal(regionalScenario({...base,acres:0}),null);
assert.equal(regionalScenario({...base,annualSavings:36}).rows[2].savings,18000);
const meta=JSON.parse(readFileSync('public/data/metadata.json'));
function floats(path){const b=readFileSync(path);return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4)}
const c=floats('public/data/carbon.f32'),o=floats('public/data/organic-matter.f32');
assert.equal(c.length,meta.width*meta.height);assert.equal(o.length,c.length);
assert.equal(sampleGrid(meta,c,38.53,-121.8),51.3184814453125);
assert.equal(sampleGrid(meta,c,38.5449,-121.7405),null);
assert.equal(sampleGrid(meta,o,38.5449,-121.7405),21.34172821044922);
assert.equal(sampleGrid(meta,c,40,-83),null);
assert.equal(sampleGrid(meta,c,meta.north,meta.east),null);
assert.equal(sampleGrid(meta,c,NaN,-121),null);
assert.match(advise('My nitrogen is low. What cover crop should I plant in Ohio in October?',{}).text,/does not fix atmospheric nitrogen/);
assert.match(advise('How do carbon payments work?',{projection:p}).text,/not buyer offers/);
console.log('PASS: 2,204 source records, exact published Yolo values, GHG reconciliation, XLSX blank cells, carbon conversion, cohort vesting, missing costs, negative rates, eligibility, raster lookups and advisory limits.');
