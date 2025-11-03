import type { FC } from 'react';

interface LegendItem {
  label: string;
  color: string;
}

interface LegendProps {
  items: LegendItem[];
  fontSize?: number;
  fontColor?: string;
  gap?: number;
  boxSize?: number;
  borderRadius?: number;
}

const Legend: FC<LegendProps> = ({ items, fontSize = 16, fontColor = 'var(--color-text-muted)', gap = 6, boxSize = 12, borderRadius = 3 }) => {
  return (
    <div style={{ display: 'flex', gap, alignItems: 'center', flexWrap: 'wrap', marginTop: 2 }}>
      {items.map((it) => (
        <div key={it.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: boxSize, height: boxSize, background: it.color, display: 'inline-block', borderRadius, border: '1px solid rgba(0,0,0,0.08)' }} />
          <span style={{ color: fontColor, fontSize }}>{it.label}</span>
        </div>
      ))}
    </div>
  );
};

export default Legend;
