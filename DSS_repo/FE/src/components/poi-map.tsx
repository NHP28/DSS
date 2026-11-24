'use client';
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { Place } from '@/lib/types';

const basemaps = [
  { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' },
  { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', attribution: 'Tiles &copy; Esri &mdash; &copy; OpenStreetMap contributors' },
];
type Props = { places: Place[]; selected?: number | null; onSelect?: (id: number) => void; latitude: number; longitude: number; interactive?: boolean };

export default function PoiMap({ places, selected = null, onSelect, latitude, longitude, interactive = true }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const callback = useRef(onSelect);
  const retryTiles = useRef<() => void>(() => {});
  const [tiles, setTiles] = useState<'loading' | 'ready' | 'failed'>('loading');
  callback.current = onSelect;

  useEffect(() => {
    if (!element.current) return;
    const instance = L.map(element.current, { zoomControl: false, scrollWheelZoom: interactive }).setView([latitude, longitude], 13);
    map.current = instance;
    let layer: L.TileLayer | undefined, timeout: ReturnType<typeof setTimeout> | undefined, disposed = false;
    const load = (index: number) => {
      if (disposed) return;
      clearTimeout(timeout); layer?.off(); layer?.remove(); setTiles('loading');
      let loaded = 0;
      const failed = () => { if (disposed) return; clearTimeout(timeout); if (index + 1 < basemaps.length) load(index + 1); else setTiles('failed'); };
      const current = L.tileLayer(basemaps[index].url, { attribution: basemaps[index].attribution, maxZoom: 19 });
      layer = current;
      // No tile within 10 seconds means this source is unreachable: try the next one.
      current.on('loading', () => { loaded = 0; clearTimeout(timeout); timeout = setTimeout(() => { if (!loaded) failed(); }, 10000); });
      current.on('tileload', () => { loaded++; clearTimeout(timeout); if (!disposed) setTiles('ready'); });
      current.addTo(instance);
    };
    retryTiles.current = () => load(0);
    load(0);
    if (interactive) L.control.zoom({ position: 'bottomright' }).addTo(instance);
    markers.current = L.layerGroup().addTo(instance);
    const observer = new ResizeObserver(() => instance.invalidateSize());
    observer.observe(element.current);
    return () => { disposed = true; clearTimeout(timeout); layer?.off(); observer.disconnect(); instance.remove(); map.current = null; markers.current = null; };
    // Initial view only; later position changes are handled by the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!map.current || !markers.current) return;
    markers.current.clearLayers();
    L.circleMarker([latitude, longitude], { radius: 8, color: '#fff', weight: 3, fillColor: '#2f6690', fillOpacity: 1 }).bindTooltip('Vị trí của bạn').addTo(markers.current);
    for (const place of places) {
      const icon = L.divIcon({ className: 'poi-marker', html: `<span class="${place.id === selected ? 'active' : ''}"><b>${place.rank}</b></span>`, iconSize: [34, 38], iconAnchor: [17, 38] });
      const marker = L.marker([place.latitude, place.longitude], { icon, keyboard: true, title: place.name }).addTo(markers.current);
      // textContent keeps catalog names from being parsed as HTML.
      const label = document.createElement('span'); label.textContent = place.name;
      marker.bindTooltip(label).on('click', () => callback.current?.(place.id));
    }
    const active = places.find(place => place.id === selected);
    if (active) {
      L.polyline([[latitude, longitude], [active.latitude, active.longitude]], { color: '#d9512c', weight: 2, dashArray: '6 7', opacity: .85 })
        .bindTooltip('Đường chim bay, không phải tuyến đường').addTo(markers.current);
      map.current.panTo([active.latitude, active.longitude]);
    } else if (places.length) {
      map.current.fitBounds(L.latLngBounds([[latitude, longitude], ...places.map(place => [place.latitude, place.longitude] as L.LatLngTuple)]), { padding: [50, 50], maxZoom: 15 });
    } else map.current.setView([latitude, longitude], 13);
  }, [places, selected, latitude, longitude]);

  return <>
    <div ref={element} style={{ height: '100%', width: '100%' }} role="application" aria-label="Bản đồ các địa điểm gợi ý; danh sách tương ứng nằm bên cạnh" />
    {tiles === 'loading' && <div className="map-status" role="status">Đang tải bản đồ nền…</div>}
    {tiles === 'failed' && <div className="map-status" role="status">Chưa tải được bản đồ nền.<button type="button" onClick={() => retryTiles.current()}>Thử lại</button></div>}
  </>;
}
