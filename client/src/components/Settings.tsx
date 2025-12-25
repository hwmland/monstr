import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MdSettings } from 'react-icons/md';
import { use24hTime } from '../utils/time';
import usePanelVisibilityStore from "../store/usePanelVisibility";

const Settings: FC = () => {
  const { panels, togglePanel } = usePanelVisibilityStore();
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const [prefer24h, setPrefer24h] = useState<boolean | null>(() => {
    try {
      const v = localStorage.getItem('pref_time_24h');
      return v === null ? null : v === '1';
    } catch {
      return null;
    }
  });

  const systemUses24h = use24hTime();

  const applyPrefer24h = (value: boolean | null) => {
    setPrefer24h(value);
    try {
      if (value === null) {
        localStorage.removeItem('pref_time_24h');
      } else {
        localStorage.setItem('pref_time_24h', value ? '1' : '0');
      }
    } catch {}
    // notify other components in the same window
    try {
      window.dispatchEvent(new CustomEvent('pref_time_24h_changed', { detail: { prefer24h: value } }));
    } catch {}
  };

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (!pickerRef.current) return;
      if (event.target instanceof Node && pickerRef.current.contains(event.target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <>
      <button
        className="button button--ghost"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open settings"
        title="Open settings"
      >
        <MdSettings size={16} aria-hidden />
      </button>

      {open
        ? createPortal(
            <div
              className="settings-overlay"
              onMouseDown={() => setOpen(false)}
              role="dialog"
              aria-modal="true"
            >
              <div className="settings" ref={pickerRef} onMouseDown={(e) => e.stopPropagation()}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600 }}>Time format</div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginLeft: 8 }}>{prefer24h === null ? `Auto (${systemUses24h ? '24h' : '12h'})` : prefer24h ? '24h' : '12h'}</div>
                  <div className="button-group button-group--micro" style={{ marginLeft: 'auto' }}>
                    <button type="button" className={`button button--micro${prefer24h === null ? ' button--micro-active' : ''}`} onClick={() => applyPrefer24h(null)}>Auto</button>
                    <button type="button" className={`button button--micro${prefer24h === false ? ' button--micro-active' : ''}`} onClick={() => applyPrefer24h(false)}>12h</button>
                    <button type="button" className={`button button--micro${prefer24h === true ? ' button--micro-active' : ''}`} onClick={() => applyPrefer24h(true)}>24h</button>
                  </div>
                </div>

                {/* separator between time format and settings list */}
                <div style={{ height: 2, background: 'rgba(148,163,184,0.4)', margin: '8px 0 10px 0', borderRadius: 2 }} />

                <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 600, marginBottom: 6 }}>Panels</div>

                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.longTerm ?? false}
                    onChange={() => togglePanel("longTerm")}
                  />
                  <span>Long-Term View</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.diskUsage ?? false}
                    onChange={() => togglePanel("diskUsage")}
                  />
                  <span>Disk Usage</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.nodeCompare ?? true}
                    onChange={() => togglePanel("nodeCompare")}
                  />
                  <span>Node Compare</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.satelliteTraffic ?? true}
                    onChange={() => togglePanel("satelliteTraffic")}
                  />
                  <span>Satellite Traffic</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.hourlyTraffic ?? false}
                    onChange={() => togglePanel("hourlyTraffic")}
                  />
                  <span>Hourly Traffic</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.actualPerformance ?? true}
                    onChange={() => togglePanel("actualPerformance")}
                  />
                  <span>Actual Performance</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.dataDistribution ?? true}
                    onChange={() => togglePanel("dataDistribution")}
                  />
                  <span>Data Size Distribution</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.accumulatedTraffic ?? true}
                    onChange={() => togglePanel("accumulatedTraffic")}
                  />
                  <span>Accumulated Traffic</span>
                </label>
                <label className="settings__item">
                  <input
                    type="checkbox"
                    checked={panels.reputations ?? true}
                    onChange={() => togglePanel("reputations")}
                  />
                  <span>Reputations</span>
                </label>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
};

export default Settings;
