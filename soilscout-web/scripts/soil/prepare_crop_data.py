"""Convert Parnita's pinned native rasters without resampling. Usage: python ... SOURCE_DIR"""
import ast, hashlib, json, pathlib, sys
import numpy as np
import rasterio
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'public/data/crops'; out.mkdir(parents=True,exist_ok=True)
commit='fbba4b8efa4537ac66333aada3ffc0308db8f162'
files={'om':'cv_om_kg_sq_m.tif','ph':'cv_ph.tif','ec':'cv_ec.tif','texture':'cv_texture_0_25.tif'}
meta={'commit':commit,'repository':'https://github.com/Parnita-C/UCD_UN_RebootTheEarth_2026','layers':{}}
geometry=None
for key,name in files.items():
 p=pathlib.Path(sys.argv[1])/name
 with rasterio.open(p) as s:
  g=(s.width,s.height,list(s.transform),s.crs.to_wkt())
  if geometry is not None: assert g==geometry
  geometry=g
  a=s.read(1,masked=True).astype('float32').filled(np.nan)
  a.astype('<f4').tofile(out/f'{key}.f32')
  meta.update(width=s.width,height=s.height,left=s.transform.c,top=s.transform.f,dx=s.transform.a,dy=-s.transform.e,crsWkt=s.crs.to_wkt())
  meta['layers'][key]={'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':f'https://raw.githubusercontent.com/Parnita-C/UCD_UN_RebootTheEarth_2026/{commit}/data/{name}'}
meta['units']={'om':'kg/m² total profile; exact depth unspecified','ph':'pH; depth unspecified','ec':'dS/m; depth unspecified','texture':'class; 0–25 cm'}
(out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
tree=ast.parse((root/'vendor/parnita/recommender_engine.py').read_text())
constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)}
(root/'lib/crop-catalog.json').write_text(json.dumps(constants,indent=2)+'\n')
print('Prepared four aligned 800 m native grids and original crop catalog.')
