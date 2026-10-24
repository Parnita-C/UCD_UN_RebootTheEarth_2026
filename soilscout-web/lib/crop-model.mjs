import proj4 from 'proj4';
import catalog from './crop-catalog.json' with {type:'json'};
export const CROP_DATABASE=catalog.CROP_DATABASE;
export const CROP_NAMES=Object.keys(CROP_DATABASE);
export const ENGINE_URL='https://github.com/Parnita-C/UCD_UN_RebootTheEarth_2026/tree/fbba4b8efa4537ac66333aada3ffc0308db8f162';
const outside=()=>({in_central_valley:false,organic_matter_kg_m2:null,ph:null,salinity_ec_ds_m:null,texture_code:null,texture_name:'No data'});
export function cropSoilProfile(grids,lat,lon){
 if(!grids||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)return outside();
 const m=grids.meta;
 const [x,y]=proj4('EPSG:4326',m.crsWkt,[lon,lat]);
 const col=Math.floor((x-m.left)/m.dx),row=Math.floor((m.top-y)/m.dy);
 if(!Number.isFinite(col)||!Number.isFinite(row)||col<0||row<0||col>=m.width||row>=m.height)return outside();
 const i=row*m.width+col;
 const read=k=>{const v=grids[k][i];if(!Number.isFinite(v))return null;const scaled=v*100,base=Math.floor(scaled);return (scaled-base===0.5?base+(base%2):Math.round(scaled))/100;};
 const om=read('om'); if(om==null)return outside();
 const t=read('texture');
 return {in_central_valley:true,organic_matter_kg_m2:om,ph:read('ph'),salinity_ec_ds_m:read('ec'),texture_code:t,texture_name:catalog.TEXTURE_LOOKUP[t]||'Unknown Texture'};
}
// Direct port of evaluate_next_crops at the pinned commit. Keep weights and tie order.
export function evaluateNextCrops(history,soil){
 if(!soil?.in_central_valley)return [{error:'Location is outside the Central Valley coverage area.'}];
 const past=history.map(c=>c.trim().toLowerCase());
 const families=past.filter(c=>CROP_DATABASE[c]).map(c=>CROP_DATABASE[c].family);
 const heavy=past.filter(c=>CROP_DATABASE[c]?.n_demand==='high').length;
 return Object.entries(CROP_DATABASE).map(([name,t])=>{
  let score=80;const reasons=[];
  if(families.includes(t.family)){score-=35;reasons.push(`Same family (${t.family}) grown recently; high disease risk.`)}
  if(heavy>=2&&t.n_demand==='fixer'){score+=20;reasons.push('Heavy nitrogen users grown recently; legume fixer strongly recommended.')}
  else if(heavy>=2&&t.n_demand==='high'){score-=25;reasons.push('Soil nitrogen depleted by consecutive heavy feeders.')}
  const ph=soil.ph,ec=soil.salinity_ec_ds_m;
  if(Number.isFinite(ph)&&!(t.min_ph<=ph&&ph<=t.max_ph)){score-=30;reasons.push(`Soil pH (${ph}) outside optimal range (${t.min_ph.toFixed(1)}-${t.max_ph.toFixed(1)}).`)}
  if(Number.isFinite(ec)&&ec>2&&t.salt_tol==='sensitive'){score-=30;reasons.push(`EC level (${ec} dS/m) exceeds sensitivity threshold.`)}
  else if(Number.isFinite(ec)&&ec>2&&t.salt_tol==='tolerant'){score+=10;reasons.push(`Tolerant to elevated soil salinity (${ec} dS/m).`)}
  if(t.pref_textures.includes(soil.texture_name)){score+=10;reasons.push(`Well-suited for ${soil.texture_name} soil texture.`)}
  return {crop:name[0].toUpperCase()+name.slice(1),score:Math.max(0,Math.min(100,score)),reasons};
 }).sort((a,b)=>b.score-a.score);
}
// Explain the original heuristics without presenting crop history as a soil test.
export function displayReason(reason){
 if(reason==='Soil nitrogen depleted by consecutive heavy feeders.')return 'Several recent crops have high nitrogen demand; available nitrogen has not been measured.';
 if(reason.includes('legume fixer strongly recommended'))return 'Recent high-nitrogen-demand crops give legumes a bonus in the rotation rules.';
 if(reason.includes('high disease risk'))return reason.replace('high disease risk.','a rotation flag to review with local advice.');
 return reason;
}
