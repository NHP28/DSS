import { percent } from '@/lib/types';

export const groupTones: Record<string, { tone: string; label: string }> = {
  heuristic: { tone: '#b7a98a', label: 'Không học' },
  ml: { tone: '#6b5b95', label: 'Machine learning truyền thống' },
  gnn: { tone: '#0d6a6c', label: 'Mạng nơ-ron đồ thị' },
  main: { tone: '#d9512c', label: 'TAS-GNN (model chính)' },
};
export type BarItem = { key: string; label: string; value: number; group: string; main?: boolean; note?: string; spread?: number };

/** Horizontal bars sorted by value. Every bar is labelled with its number, so colour is never the only cue. */
export default function MetricBars({ items, metric }: { items: BarItem[]; metric: string }) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const max = Math.max(...sorted.map(item => item.value), 1e-9);
  return <div className="bars" role="img" aria-label={`${metric}: ${sorted.map(item => `${item.label} ${percent(item.value)}`).join('; ')}`}>
    {sorted.map(item => <div key={item.key} className={item.main ? 'bar-row main' : 'bar-row'}>
      <span className="label">{item.label}{item.note && <span className="muted small"> · {item.note}</span>}</span>
      <div className="track"><div className="fill" style={{ width: `${item.value / max * 100}%`, ['--tone' as string]: groupTones[item.main ? 'main' : item.group]?.tone }} /></div>
      <span className="value">{percent(item.value)}{item.spread !== undefined && <span className="muted small" style={{ fontWeight: 400 }}><br />± {percent(item.spread)}</span>}</span>
    </div>)}
  </div>;
}

export function GroupLegend({ groups }: { groups: string[] }) {
  return <div className="legend">{groups.map(group => <span key={group}><i style={{ ['--tone' as string]: groupTones[group].tone }} />{groupTones[group].label}</span>)}</div>;
}
