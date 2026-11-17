'use client';
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { Place } from '@/lib/types';

const basemaps = [
  {
    url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution:'Tiles &copy; <a href="https://www.arcgis.com/home/item.html?id=3b93337983e9436f8db950e38a8629af">Esri</a> &mdash; Esri, HERE, Garmin, USGS, Intermap, INCREMENT P, NRCan, Esri Japan, METI, Esri China (Hong Kong), Esri Korea, Esri (Thailand), NGCC, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, GIS User Community',
  },
  {
    url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  },
];

export default function PoiMap({places,selected,onSelect,latitude,longitude}:{places:Place[];selected:number|null;onSelect:(id:number)=>void;latitude:number;longitude:number}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map|null>(null);
  const markers = useRef<L.LayerGroup|null>(null);
  const callback = useRef(onSelect);
  const retryTiles = useRef<()=>void>(()=>{});
  const [tileStatus,setTileStatus] = useState<'loading'|'ready'|'failed'>('loading');
  callback.current = onSelect;
  useEffect(()=>{
    if (!element.current) return;
    const instance = L.map(element.current,{zoomControl:false}).setView([latitude,longitude],13);
    map.current = instance;
    let layer:L.TileLayer|undefined;
    let timeout:ReturnType<typeof setTimeout>|undefined;
    let disposed = false;
    const clearTimeoutIfNeeded = ()=>{if(timeout!==undefined){clearTimeout(timeout);timeout=undefined;}};
    const loadSource = (index:number)=>{
      if(disposed)return;
      clearTimeoutIfNeeded();
      layer?.off();layer?.remove();
      setTileStatus('loading');
      let loaded = 0, errors = 0;
      const failed = ()=>{
        if(disposed)return;
        clearTimeoutIfNeeded();
        if(index+1<basemaps.length)loadSource(index+1);
        else setTileStatus('failed');
      };
      const current = L.tileLayer(basemaps[index].url,{attribution:basemaps[index].attribution,maxZoom:19});
      layer = current;
      current.on('loading',()=>{
        loaded=0;errors=0;
        clearTimeoutIfNeeded();
        timeout=setTimeout(()=>{if(loaded===0)failed();},10000);
      });
      current.on('tileload',()=>{
        loaded++;
        clearTimeoutIfNeeded();
        if(!disposed)setTileStatus('ready');
      });
      current.on('tileerror',()=>{errors++;});
      current.on('load',()=>{if(loaded===0&&errors>0)failed();});
      current.addTo(instance);
    };
    retryTiles.current=()=>loadSource(0);
    loadSource(0);
    L.control.zoom({position:'bottomright'}).addTo(instance);
    markers.current = L.layerGroup().addTo(instance);
    const observer = new ResizeObserver(()=>instance.invalidateSize());
    observer.observe(element.current);
    return ()=>{
      disposed=true;clearTimeoutIfNeeded();layer?.off();
      retryTiles.current=()=>{};
      observer.disconnect();instance.remove();map.current=null;markers.current=null;
    };
    // Initial view only; subsequent position updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  useEffect(()=>{
    if (!map.current || !markers.current) return;
    markers.current.clearLayers();
    L.circleMarker([latitude,longitude],{radius:8,color:'#fff',weight:3,fillColor:'#4689cf',fillOpacity:1}).bindTooltip('Vị trí của bạn').addTo(markers.current);
    for (const p of places) {
      const icon = L.divIcon({className:'poi-marker',html:`<span class="${p.id===selected?'active':''}"><b>${p.rank}</b></span>`,iconSize:[34,38],iconAnchor:[17,38]});
      const marker = L.marker([p.latitude,p.longitude],{icon,keyboard:true,title:p.name}).addTo(markers.current);
      // textContent prevents catalog names from becoming executable popup HTML.
      const label = document.createElement('span');label.textContent=p.name;
      marker.bindTooltip(label).on('click',()=>callback.current(p.id));
    }
    const p = places.find(p=>p.id===selected);
    if (p) {
      L.polyline([[latitude,longitude],[p.latitude,p.longitude]],{color:'#b9814b',weight:2,dashArray:'6 7',opacity:.8})
        .bindTooltip('Khoảng cách đường chim bay; không phải tuyến đường di chuyển').addTo(markers.current);
      map.current.panTo([p.latitude,p.longitude]);
    }
    else if (places.length) map.current.fitBounds(L.latLngBounds([[latitude,longitude],...places.map(p=>[p.latitude,p.longitude] as L.LatLngTuple)]),{padding:[55,55],maxZoom:14});
    else map.current.setView([latitude,longitude],13);
  },[places,selected,latitude,longitude]);
  return <>
    <div ref={element} className="h-full min-h-[400px] w-full" aria-label="Bản đồ địa điểm gợi ý. Danh sách địa điểm tương ứng ở bên cạnh."/>
    {tileStatus==='loading'&&<div className="map-tile-loading" role="status">Đang tải bản đồ nền…</div>}
    {tileStatus==='failed'&&<div className="map-tile-notice" role="status"><span>Chưa tải được bản đồ nền. Kiểm tra kết nối mạng rồi thử lại.</span><button type="button" onClick={()=>retryTiles.current()}>Thử tải lại</button></div>}
  </>;
}
