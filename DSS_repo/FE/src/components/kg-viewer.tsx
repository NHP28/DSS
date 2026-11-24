'use client';
import { useEffect, useMemo, useState } from 'react';
import { Info } from 'lucide-react';
import { api, ApiError } from '@/lib/api';

type Node = { id: string; label: string; type: string };
type Link = { source: string; target: string; type: string; value?: number };
type Graph = { poi: { id: number; name: string }; nodes: Node[]; links: Link[]; cypher: string };
type Poi = { id: number; name: string; category: string; hidden: boolean };

export const nodeTones: Record<string, string> = { POI: '#0d6a6c', Category: '#d9512c', District: '#2f6690', TimeSlot: '#b77a12', User: '#6b5b95' };
const edgeNames: Record<string, string> = { IN_CATEGORY: 'thuộc danh mục', LOCATED_IN: 'nằm ở', BUSY_AT: 'đông vào', NEAR: 'gần', CO_VISITED: 'cùng người ghé' };
const short = (text: string, max = 22) => text.length > max ? `${text.slice(0, max - 1)}…` : text;

/** Shows the neighbourhood of one POI in the Neo4j graph as a radial diagram, with the Cypher that produced it. */
export default function KgViewer() {
  const [pois, setPois] = useState<Poi[]>([]);
  const [id, setId] = useState<number | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'down' | 'error'>('idle');
  const [message, setMessage] = useState('');
  useEffect(() => {
    api<Poi[]>('pois?limit=1000').then(list => {
      const visible = list.filter(poi => !poi.hidden).sort((a, b) => a.name.localeCompare(b.name, 'vi'));
      setPois(visible);
      setId((visible.find(poi => poi.category === 'tourist_spot') || visible[0])?.id ?? null);
    }).catch(problem => { setState('error'); setMessage((problem as Error).message); });
  }, []);
  useEffect(() => {
    if (id === null) return;
    let cancelled = false;
    setState('loading');
    api<Graph>(`kg/poi/${id}`).then(data => { if (!cancelled) { setGraph(data); setState('idle'); } })
      .catch(problem => { if (cancelled) return; setGraph(null); setState(problem instanceof ApiError && problem.status === 503 ? 'down' : 'error'); setMessage((problem as Error).message); });
    return () => { cancelled = true; };
  }, [id]);

  const layout = useMemo(() => {
    if (!graph) return null;
    const [centre, ...others] = graph.nodes;
    const width = 760, height = 520, cx = width / 2, cy = height / 2;
    const positions = new Map<string, { x: number; y: number }>([[centre.id, { x: cx, y: cy }]]);
    others.forEach((node, index) => {
      const angle = -Math.PI / 2 + index / others.length * Math.PI * 2;
      positions.set(node.id, { x: cx + Math.cos(angle) * 290, y: cy + Math.sin(angle) * 205 });
    });
    return { width, height, positions, centre };
  }, [graph]);

  return <div className="stack">
    <label className="field" style={{ maxWidth: 520 }}>Chọn một địa điểm để xem vùng lân cận trong đồ thị
      <select value={id ?? ''} onChange={event => setId(Number(event.target.value))} disabled={!pois.length}>
        {pois.map(poi => <option key={poi.id} value={poi.id}>{poi.name}</option>)}</select></label>
    {state === 'down' && <div className="notice"><Info size={18} /><span><strong>Neo4j chưa bật.</strong> Chạy <code>docker compose up -d --wait neo4j</code> rồi <code>python tools/build_kg.py</code> để dựng đồ thị. Lược đồ và số lượng bên trên được tính trực tiếp từ dữ liệu nên vẫn đúng.</span></div>}
    {state === 'error' && <div className="notice error"><Info size={18} /><span>{message}</span></div>}
    {state === 'loading' && !graph && <div className="skeleton" style={{ height: 360 }} />}
    {graph && layout && <>
      <div className="table-wrap" style={{ padding: '.5rem' }}>
        <svg className="kg-canvas" viewBox={`0 0 ${layout.width} ${layout.height}`} role="img"
          aria-label={`Đồ thị quanh ${graph.poi.name}: ${graph.links.map(link => `${edgeNames[link.type] || link.type} ${graph.nodes.find(node => node.id === link.target)?.label}`).join(', ')}`}>
          {graph.links.map((link, index) => {
            const a = layout.positions.get(link.source)!, b = layout.positions.get(link.target)!;
            const mx = a.x + (b.x - a.x) * .56, my = a.y + (b.y - a.y) * .56;
            return <g key={index}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={link.type === 'CO_VISITED' ? '#d9512c' : '#b9ad92'} strokeWidth={link.type === 'CO_VISITED' ? 1.6 : 1.2} strokeDasharray={link.type === 'NEAR' ? '5 5' : undefined} />
              <text className="edge-label" x={mx} y={my - 4} textAnchor="middle">{edgeNames[link.type] || link.type}{link.value !== undefined && (link.type === 'NEAR' ? ` ${link.value} km` : ` · ${link.value}`)}</text></g>;
          })}
          {graph.nodes.map(node => {
            const point = layout.positions.get(node.id)!, isCentre = node.id === layout.centre.id;
            return <g key={node.id}><circle cx={point.x} cy={point.y} r={isCentre ? 30 : 17} fill={nodeTones[node.type]} stroke="#fffdf8" strokeWidth="3" />
              <text x={point.x} y={point.y + (isCentre ? 48 : 33)} textAnchor="middle" fontWeight={isCentre ? 700 : 500}>{short(node.label, isCentre ? 40 : 22)}</text></g>;
          })}
        </svg>
      </div>
      <div className="legend">{Object.entries({ POI: 'Địa điểm', Category: 'Danh mục', District: 'Quận', TimeSlot: 'Khung giờ' }).map(([type, label]) => <span key={type}><i style={{ ['--tone' as string]: nodeTones[type], borderRadius: '50%' }} />{label}</span>)}
        <span>Số trên cạnh: km (gần), số lượt (đông vào), số người (cùng người ghé)</span></div>
      <details><summary className="link">Xem câu truy vấn Cypher</summary><pre className="code" style={{ marginTop: '.7rem' }}>{graph.cypher}</pre></details>
    </>}
  </div>;
}
