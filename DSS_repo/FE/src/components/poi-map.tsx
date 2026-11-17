'use client';
import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { Place } from '@/lib/types';

export default function PoiMap({places,selected,onSelect,latitude,longitude}:{places:Place[];selected:number|null;onSelect:(id:number)=>void;latitude:number;longitude:number}) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map|null>(null);
  const markers = useRef<L.LayerGroup|null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  useEffect(()=>{
    if (!element.current) return;
    map.current = L.map(element.current,{zoomControl:false}).setView([latitude,longitude],13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',maxZoom:19}).addTo(map.current);
    L.control.zoom({position:'bottomright'}).addTo(map.current);
    markers.current = L.layerGroup().addTo(map.current);
    const observer = new ResizeObserver(()=>map.current?.invalidateSize());
    observer.observe(element.current);
    return ()=>{observer.disconnect();map.current?.remove();map.current=null;};
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
  return <div ref={element} className="h-full min-h-[400px] w-full" aria-label="Bản đồ địa điểm gợi ý. Danh sách địa điểm tương ứng ở bên cạnh."/>;
}
