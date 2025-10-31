import type { FC, ReactNode } from "react";
import { useEffect, useState } from "react";
import { formatWindowTime, use24hTime } from "../utils/time";

interface Props {
  windowStart?: string | null;
  windowEnd?: string | null;
  selectedNodes?: string[];
  children?: ReactNode;
}

const PanelSubtitle: FC<Props> = ({ windowStart, windowEnd, selectedNodes, children }) => {
  const [prefer24h, setPrefer24h] = useState<boolean | null>(() => {
    try {
      const v = localStorage.getItem('pref_time_24h');
      return v === null ? null : v === '1';
    } catch {
      return null;
    }
  });

  useEffect(() => {
    const handler = (ev: Event) => {
      try {
        // @ts-ignore custom event
        const detail = (ev as CustomEvent).detail;
        setPrefer24h(detail?.prefer24h ?? null);
      } catch {
        // ignore
      }
    };
    window.addEventListener('pref_time_24h_changed', handler as EventListener);
    return () => window.removeEventListener('pref_time_24h_changed', handler as EventListener);
  }, []);

  const hour12: boolean | null | undefined = (() => {
    if (prefer24h === true) return false; // prefer 24h -> hour12 = false
    if (prefer24h === false) return true; // prefer 12h -> hour12 = true
    // auto: consult centralized helper to decide if system uses 24h
    try {
      const system24 = use24hTime();
      return system24 ? false : true;
    } catch {
      return undefined;
    }
  })();

  const parts: string[] = [];
  const isParsable = (v?: string | null) => {
    if (!v) return false;
    const d = new Date(v);
    return !Number.isNaN(d.getTime());
  };

  const fmt = (v?: string | null) => {
    if (!v) return "—";
    if (isParsable(v)) return formatWindowTime(v, hour12 as any);
    // assume already formatted string (e.g. panels passed preformatted value)
    return v;
  };

  if (windowStart || windowEnd) {
    parts.push(`Window: ${fmt(windowStart)} – ${fmt(windowEnd)}`);
  }
  // compute nodes label if the caller provided selected nodes
  const nodesLabel = selectedNodes === undefined ? undefined : (selectedNodes.length === 0 || selectedNodes.includes("All") ? "All nodes" : `Nodes: ${selectedNodes.join(", ")}`);
  if (nodesLabel) parts.push(nodesLabel);

  return (
    <p className="panel__subtitle">
      {parts.length > 0 ? parts.join(" • ") : null}
      {children ? (
        <>
          {parts.length > 0 ? " • " : null}
          {children}
        </>
      ) : null}
    </p>
  );
};

export default PanelSubtitle;
