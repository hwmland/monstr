import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MdHelpOutline } from "react-icons/md";

const NodeSelectionHelp: FC = () => {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (!panelRef.current) return;
      if (event.target instanceof Node && panelRef.current.contains(event.target)) return;
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
        aria-label="Node selection help"
        title="Node selection help"
      >
        <MdHelpOutline size={16} aria-hidden />
      </button>

      {open
        ? createPortal(
            <div
              className="settings-overlay"
              onMouseDown={() => setOpen(false)}
              role="dialog"
              aria-modal="true"
              aria-label="Node selection help"
            >
              <div className="settings node-help" ref={panelRef} onMouseDown={(e) => e.stopPropagation()}>
                <div className="node-help__title">Node Selection</div>

                <div className="node-help__separator" />

                <ul className="node-help__list">
                  <li className="node-help__item">
                    <kbd className="node-help__key">Click</kbd>
                    <span className="node-help__desc">Toggle node on / off</span>
                  </li>
                  <li className="node-help__item">
                    <kbd className="node-help__key">Shift + Click</kbd>
                    <span className="node-help__desc">Select <em>only</em> this node — deselects all others</span>
                  </li>
                  <li className="node-help__item">
                    <kbd className="node-help__key">Ctrl + Click</kbd>
                    <span className="node-help__desc">Select all nodes <em>except</em> this one</span>
                  </li>
                </ul>

                <div className="node-help__separator" />

                <div className="node-help__section-title">All button</div>
                <ul className="node-help__list">
                  <li className="node-help__item node-help__item--block">
                    Clicking <strong>All</strong> resets selection to the aggregate view (all nodes combined).
                  </li>
                  <li className="node-help__item node-help__item--block">
                    Selecting individual nodes deselects <strong>All</strong> automatically.
                  </li>
                  <li className="node-help__item node-help__item--block">
                    When every individual node is selected, the selection collapses back to <strong>All</strong>.
                  </li>
                  <li className="node-help__item node-help__item--block">
                    Shift / Ctrl modifiers on <strong>All</strong> have no special effect — it always selects everything.
                  </li>
                </ul>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
};

export default NodeSelectionHelp;
