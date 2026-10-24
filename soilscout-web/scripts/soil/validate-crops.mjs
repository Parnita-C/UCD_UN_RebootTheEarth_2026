import assert from 'node:assert/strict';
import fs from 'node:fs';
import proj4 from 'proj4';
import {cropSoilProfile,evaluateNextCrops,displayReason} from '../../lib/crop-model.mjs';
import {advise,SOURCES} from '../../lib/soil-model.mjs';
const base=new URL('../../public/data/crops/',import.meta.url);
const grids={meta:JSON.parse(fs.readFileSync(new URL('metadata.json',base)))};
for(const k of ['om','ph','ec','texture']){const b=fs.readFileSync(new URL(k+'.f32',base));grids[k]=new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);assert.equal(grids[k].length,grids.meta.width*grids.meta.height);}
const davis=cropSoilProfile(grids,38.5449,-121.7405);
assert(davis.in_central_valley);assert(Number.isFinite(davis.ph));
for(const [lat,lon] of [[37.7749,-122.4194],[40,-83],[0,0],[91,-121],[NaN,-121]])assert.equal(cropSoilProfile(grids,lat,lon).in_central_valley,false);
const history=['tomatoes','corn','tomatoes'],r=evaluateNextCrops(history,davis);
assert.equal(r.length,7);assert(['Alfalfa','Beans','Wheat'].includes(r[0].crop));
assert(r.find(x=>x.crop==='Tomatoes').reasons.some(x=>x.includes('high disease risk')));
assert(!displayReason('Soil nitrogen depleted by consecutive heavy feeders.').includes('depleted'));
const missing={...grids,ph:new Float32Array(grids.ph.length).fill(NaN)};
assert.equal(cropSoilProfile(missing,38.5449,-121.7405).ph,null);
assert.equal(evaluateNextCrops(history,cropSoilProfile(missing,38.5449,-121.7405)).length,7);
// Explicit edge handling: do not extrapolate nearest edge cells as upstream does.
const m=grids.meta;const [lon,lat]=proj4(m.crsWkt,'EPSG:4326',[m.left-801,m.top-800]);
assert.equal(cropSoilProfile(grids,lat,lon).in_central_valley,false);
const response=advise('What crops should I grow next?',{lat:38.5449,lon:-121.7405,cropProfile:davis,history,cropResults:r});
assert(response.text.includes(r[0].crop));assert(response.text.includes('tomatoes → corn → tomatoes'));assert(response.sources.includes(10));assert(SOURCES[10].url.includes('fbba4b8'));
assert(advise('What crop next?',{}).text.includes('no soil profile'));
console.log('PASS: native grid, Davis/SF/Ohio coverage, invalid coordinates, missing layers, no edge extrapolation and shared advisor context.');
console.log('Davis source profile:',davis);
