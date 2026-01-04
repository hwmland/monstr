import type { FC, ReactNode, ReactElement } from "react";
import { cloneElement } from "react";

interface PanelControlsProps {
  ariaLabel: string;
  buttons: ReactNode[];
  // optional localStorage key to persist selection for this control group
  storageKey?: string;
}

const PanelControls: FC<PanelControlsProps> = ({ ariaLabel, buttons, storageKey }) => {
  const rendered = buttons.map((b, i) => {
    if (!storageKey || !b || typeof b !== 'object') return b;
    const el = b as ReactElement<any>;
    const key = el.key != null ? String(el.key) : (el.props && (el.props.value ?? el.props['data-key'] ?? String(i)));
    const originalOnClick = el.props && el.props.onClick;
    const wrappedOnClick = (e?: any) => {
      try {
        if (typeof originalOnClick === 'function') originalOnClick(e);
      } finally {
        try {
          localStorage.setItem(storageKey, String(key));
        } catch {
          // ignore
        }
      }
    };
    return cloneElement(el, { onClick: wrappedOnClick });
  });

  return (
    <div className="panel-controls">
      <div className="button-group button-group--micro" role="group" aria-label={ariaLabel}>
        {rendered}
      </div>
    </div>
  );
};

export default PanelControls;

export function getStoredSelection<T extends string>(
  key: string | undefined,
  allowedValues: readonly T[] | null,
  defaultValue: T,
): T {
  if (!key) {
    return defaultValue;
  }

  try {
    const stored = localStorage.getItem(key);
    if (!stored) {
      return defaultValue;
    }
    if (!allowedValues) {
      return stored as T;
    }
    return allowedValues.includes(stored as T) ? (stored as T) : defaultValue;
  } catch {
    return defaultValue;
  }
}
