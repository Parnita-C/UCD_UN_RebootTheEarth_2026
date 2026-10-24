'use client';
import {useEffect,useRef,useState} from 'react';
import type * as Leaflet from 'leaflet';
import 'leaflet/dist/leaflet.css';
export default function SoilMap({lat,lon,onPick,overlay,meta}:{lat:number;lon:number;onPick:(lat:number,lon:number)=>void;overlay:boolean;meta:any}){
 const container=useRef<HTMLDivElement>(null),map=useRef<Leaflet.Map|null>(null),marker=useRef<Leaflet.Marker|null>(null),layer=useRef<Leaflet.ImageOverlay|null>(null),callback=useRef(onPick);
 const [failed,setFailed]=useState(false);callback.current=onPick;
 useEffect(()=>{let disposed=false;let instance:Leaflet.Map;
 import('leaflet').then(L=>{if(disposed||!container.current)return;
 instance=L.map(container.current,{zoomControl:false,minZoom:3,maxZoom:16}).setView([lat,lon],10);map.current=instance;
 L.control.zoom({position:'bottomright'}).addTo(instance);
 const tiles=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'<a href="https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer">Esri, Vantor, Earthstar Geographics, GIS User Community</a>',maxZoom:19}).addTo(instance);
 tiles.on('tileerror',()=>setFailed(true));tiles.on('tileload',()=>setFailed(false));
 const icon=L.divIcon({className:'field-pin',html:'<span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s7-7 7-13A7 7 0 0 0 5 9c0 6 7 13 7 13Z"/><circle cx="12" cy="9" r="2"/></svg></span>',iconSize:[40,46],iconAnchor:[20,44]});
 marker.current=L.marker([lat,lon],{icon,draggable:true,title:'Selected soil location'}).addTo(instance);
 marker.current.on('dragend',()=>{const p=marker.current!.getLatLng();callback.current(p.lat,p.lng)});
 instance.on('click',(e:Leaflet.LeafletMouseEvent)=>callback.current(e.latlng.lat,e.latlng.lng));
 if(meta){layer.current=L.imageOverlay('/data/carbon-overlay.png',[[meta.overlay.south,meta.overlay.west],[meta.overlay.north,meta.overlay.east]],{opacity:.65});if(overlay)layer.current.addTo(instance);}
 });return()=>{disposed=true;instance?.remove();map.current=null;marker.current=null;layer.current=null;};
 },[meta]);
 useEffect(()=>{if(map.current&&marker.current){marker.current.setLatLng([lat,lon]);map.current.panTo([lat,lon]);}},[lat,lon]);
 useEffect(()=>{if(map.current&&layer.current){if(overlay)layer.current.addTo(map.current);else layer.current.remove();}},[overlay,meta]);
 return <div className="map-wrapper"><div ref={container} className="map" aria-label="Click map to select soil location"/>{failed&&<div className="map-error">Base map unavailable. Use the coordinate fields; soil lookups still work.</div>}{overlay&&<div className="map-legend"><strong>Soil carbon · t C/ha</strong><div/><span>0 <i/>100+</span></div>}<div className="map-tip">Click anywhere to explore the soil below</div></div>;
}
