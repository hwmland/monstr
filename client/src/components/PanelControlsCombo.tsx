import type { FC, MouseEvent as ReactMouseEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface PanelControlsComboOption {
  value: string;
  label: string;
}

interface PanelControlsComboProps {
  options: PanelControlsComboOption[];
  activeValue?: string | null;
  defaultValue?: string;
  onSelect: (value: string) => void;
  ariaLabel?: string;
  storageKey?: string;
}

const PanelControlsCombo: FC<PanelControlsComboProps> = ({
  options,
  activeValue,
  defaultValue,
  onSelect,
  ariaLabel = "Select option",
  storageKey,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const comboRef = useRef<HTMLDivElement | null>(null);

  const initialSelected = useMemo(() => {
    if (defaultValue && options.some((opt) => opt.value === defaultValue)) {
      return defaultValue;
    }
    return options[0]?.value ?? "";
  }, [defaultValue, options]);

  const [selectedValue, setSelectedValue] = useState(initialSelected);

  useEffect(() => {
    if (activeValue && options.some((opt) => opt.value === activeValue)) {
      setSelectedValue(activeValue);
    }
  }, [activeValue, options]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (comboRef.current && !comboRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedLabel = useMemo(() => {
    return options.find((opt) => opt.value === selectedValue)?.label ?? options[0]?.label ?? "";
  }, [options, selectedValue]);

  const isActive = Boolean(activeValue && options.some((opt) => opt.value === activeValue));

  const persistSelection = useCallback((value: string) => {
    if (!storageKey) {
      return;
    }
    try {
      localStorage.setItem(storageKey, value);
    } catch {
      // ignore storage failures
    }
  }, [storageKey]);

  const applySelected = () => {
    if (!selectedValue) return;
    onSelect(selectedValue);
    persistSelection(selectedValue);
    setIsOpen(false);
  };

  const handleArrowToggle = (event: ReactMouseEvent<HTMLSpanElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsOpen((prev) => !prev);
  };

  const handleOptionClick = (value: string) => {
    setSelectedValue(value);
    onSelect(value);
    persistSelection(value);
    setIsOpen(false);
  };

  if (options.length === 0) {
    return null;
  }

  return (
    <div
      className={isActive ? "panel-controls-combo panel-controls-combo--active" : "panel-controls-combo"}
      ref={comboRef}
    >
      <button
        type="button"
        className={
          isActive
            ? "button button--micro button--micro-active panel-controls-combo__button"
            : "button button--micro panel-controls-combo__button"
        }
        onClick={applySelected}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="panel-controls-combo__label">{selectedLabel}</span>
        <span className="panel-controls-combo__arrow" onClick={handleArrowToggle} role="presentation">
          ▾
        </span>
      </button>
      {isOpen ? (
        <div className="panel-controls-combo__menu" role="listbox">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={
                option.value === selectedValue
                  ? "button button--micro button--micro-active"
                  : "button button--micro"
              }
              onClick={() => handleOptionClick(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default PanelControlsCombo;
