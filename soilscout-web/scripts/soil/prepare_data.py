"""Prepare browser-readable grids from the supplied soil rasters (no source changes)."""
import json, hashlib, argparse
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform, transform_bounds
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--input-dir', required=True, type=Path, help='Directory containing the two original uploaded GeoTIFFs')
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
source=args.input_dir
out=root/'public/data'
with rasterio.open(source/'GSOCseq_T0_Map030_CA.tif') as carbon, rasterio.open(source/'om_kg_sq_m.tif') as om:
    c=carbon.read(1).astype('<f4')
    c[(c==carbon.nodata)|(~np.isfinite(c))|(c<0)]=np.nan
    o=np.full(c.shape,np.nan,dtype='<f4')
    reproject(source=rasterio.band(om,1),destination=o,src_transform=om.transform,src_crs=om.crs,src_nodata=om.nodata,dst_transform=carbon.transform,dst_crs=carbon.crs,dst_nodata=np.nan,resampling=Resampling.nearest)
    o[(~np.isfinite(o))|(o<0)]=np.nan
    c.tofile(out/'carbon.f32'); o.tofile(out/'organic-matter.f32')
    meta={'width':carbon.width,'height':carbon.height,'west':carbon.bounds.left,'north':carbon.bounds.top,'east':carbon.bounds.right,'south':carbon.bounds.bottom,'dx':carbon.res[0],'dy':carbon.res[1],'crs':'EPSG:4326','encoding':'little-endian Float32, NaN=no data','carbon':{'file':'GSOCseq_T0_Map030_CA.tif','unit':'t C/ha','depth':'0–30 cm','period':'GSOCseq T0 baseline (2020 model reference)','resolution':'30 arc-seconds (~1 km)','note':'Units and depth follow FAO GSOCseq documentation; uploaded GeoTIFF has no unit tags.'},'organic_matter':{'file':'om_kg_sq_m.tif','unit':'kg/m²','depth':'Total profile; exact depth not provided in uploaded file','resolution':'800 m source, nearest-cell resampled to the carbon grid','note':'Not organic matter percentage; do not derive carbon from this layer.'},'sources':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source.glob('*.tif')]}
    overlay_transform, ow, oh = calculate_default_transform(carbon.crs, 'EPSG:3857', carbon.width, carbon.height, *carbon.bounds)
    overlay_data=np.full((oh,ow),np.nan,dtype='<f4')
    reproject(source=c,destination=overlay_data,src_transform=carbon.transform,src_crs=carbon.crs,src_nodata=np.nan,dst_transform=overlay_transform,dst_crs='EPSG:3857',dst_nodata=np.nan,resampling=Resampling.nearest)
    west,south,east,north=transform_bounds('EPSG:3857','EPSG:4326',*rasterio.transform.array_bounds(oh,ow,overlay_transform))
    meta['overlay']={'west':west,'south':south,'east':east,'north':north}
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
    # Diagnostic/render layer only; numeric lookups use the full float grids.
    scaled=np.clip(overlay_data/100,0,1); rgba=np.zeros((*overlay_data.shape,4),dtype=np.uint8)
    for k, (a,b) in enumerate([(225,28),(232,83),(196,57)]):
        rgba[:,:,k]=np.nan_to_num(a+(b-a)*scaled).astype(np.uint8)
    rgba[:,:,3]=np.where(np.isfinite(overlay_data),135,0)
    Image.fromarray(rgba).save(out/'carbon-overlay.png')
    samples=[]
    for name,lat,lon in [('Davis',38.5449,-121.7405),('Fresno',36.7468,-119.7726),('Bakersfield',35.3733,-119.0187),('Ohio',40.0,-83.0)]:
        row,col=carbon.index(lon,lat)
        result={'name':name,'lat':lat,'lon':lon,'carbon':None,'organic_matter':None}
        if 0<=row<carbon.height and 0<=col<carbon.width:
            for key,a in [('carbon',c),('organic_matter',o)]: result[key]=float(a[row,col]) if np.isfinite(a[row,col]) else None
        samples.append(result)
    (root/'scripts/soil/expected-samples.json').write_text(json.dumps(samples,indent=2))
    print(json.dumps({'samples':samples,'valid_carbon_pixels':int(np.isfinite(c).sum()),'valid_om_pixels':int(np.isfinite(o).sum())},indent=2))
