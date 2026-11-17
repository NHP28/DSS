'use client';

import { SlidersHorizontal } from 'lucide-react';
import { criteria } from '@/lib/explorer-query';

export default function PriorityControls({ enabled, levels, onToggle, onChange }: {
  enabled: boolean;
  levels: number[];
  onToggle: (enabled: boolean) => void;
  onChange: (levels: number[]) => void;
}) {
  const total = levels.reduce((sum, value) => sum + value, 0);
  return <fieldset className="priority-controls">
    <legend className="sr-only">Điều chỉnh mức ưu tiên khi xếp hạng</legend>
    <div className="priority-header">
      <div><SlidersHorizontal size={17}/><span><strong>Điều gì quan trọng với bạn?</strong><small>Chọn bộ ưu tiên ở trên hoặc tự điều chỉnh.</small></span></div>
      <label className="priority-toggle"><input type="checkbox" checked={enabled} onChange={event => onToggle(event.target.checked)}/>Tự điều chỉnh</label>
    </div>
    {enabled && <>
      <div className="priority-grid">{criteria.map((criterion, index) => <label className="priority-slider" key={criterion.label}>
        <span>{criterion.label}<output>{Math.round(levels[index] / total * 100)}%</output></span>
        <input type="range" min="1" max="9" step="1" value={levels[index]}
          aria-label={`Mức ưu tiên ${criterion.label.toLowerCase()}`}
          aria-valuetext={`Mức ${levels[index]} trên 9, tương đương ${Math.round(levels[index] / total * 100)} phần trăm tổng ưu tiên`}
          onChange={event => onChange(levels.map((value, i) => i === index ? Number(event.target.value) : value))}/>
        <small>{criterion.hint}</small>
      </label>)}</div>
      <p className="priority-help">Tỷ trọng được tính lại theo tổng ưu tiên. Bấm <strong>Tìm địa điểm</strong> để xem thứ hạng mới.</p>
    </>}
  </fieldset>;
}
