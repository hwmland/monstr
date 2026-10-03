import type { FC, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface PanelControlsComboOption {
  value: string;
  label: string;
  disabled?: boolean;
  icon?: ReactNode;
}

interface PanelControlsComboProps {
  options: PanelControlsComboOption[];
  activeValue?: string | null;
  displayOnlyLabel?: string;
  defaultValue?: string;
  onSelect: (value: string) => void;
  ariaLabel?: string;
  storageKey?: string;
}

const PanelControlsCombo: FC<PanelControlsComboProps> = ({
  options,
  activeValue,
  displayOnlyLabel,
  defaultValue,
  onSelect,
  ariaLabel = 'Select option',
  storageKey,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const comboRef = useRef<HTMLDivElement | null>(null);

  const initialSelected = useMemo(() => {
    if (defaultValue && options.some((opt) => opt.value === defaultValue && !opt.disabled)) {
      return defaultValue;
    }
    return options.find((opt) => !opt.disabled)?.value ?? '';
  }, [defaultValue, options]);

  const [selectedValue, setSelectedValue] = useState(initialSelected);

  useEffect(() => {
    if (activeValue && options.some((opt) => opt.value === activeValue && !opt.disabled)) {
      setSelectedValue(activeValue);
    }
  }, [activeValue, options]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (comboRef.current && !comboRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeOption =
    activeValue === undefined ? undefined : options.find((opt) => opt.value === activeValue);
  const selectedOption =
    activeValue === undefined ? options.find((opt) => opt.value === selectedValue) : activeOption;
  const selectedLabel =
    selectedOption?.label ??
    displayOnlyLabel ??
    options.find((opt) => opt.value === selectedValue)?.label ??
    options[0]?.label ??
    '';

  const isActive = Boolean(activeOption && !activeOption.disabled);

  const persistSelection = useCallback(
    (value: string) => {
      if (!storageKey) {
        return;
      }
      try {
        localStorage.setItem(storageKey, value);
      } catch {
        // ignore storage failures
      }
    },
    [storageKey],
  );

  const applySelected = () => {
    const value = activeValue === undefined ? selectedValue : activeValue;
    const option = options.find((opt) => opt.value === value);
    if (!value || !option || option.disabled) return;
    onSelect(value);
    persistSelection(value);
    setIsOpen(false);
  };

  const handleArrowToggle = (event: ReactMouseEvent<HTMLSpanElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsOpen((prev) => !prev);
  };

  const handleOptionClick = (option: PanelControlsComboOption) => {
    if (option.disabled) return;
    setSelectedValue(option.value);
    onSelect(option.value);
    persistSelection(option.value);
    setIsOpen(false);
  };

  if (options.length === 0) {
    return null;
  }

  return (
    <div
      className={
        isActive ? 'panel-controls-combo panel-controls-combo--active' : 'panel-controls-combo'
      }
      ref={comboRef}
    >
      <button
        type="button"
        className={
          isActive
            ? 'button button--micro button--micro-active panel-controls-combo__button'
            : 'button button--micro panel-controls-combo__button'
        }
        onClick={applySelected}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        {selectedOption?.icon ? (
          <span className="panel-controls-combo__icon">{selectedOption.icon}</span>
        ) : null}
        <span className="panel-controls-combo__label">{selectedLabel}</span>
        <span
          className="panel-controls-combo__arrow"
          onClick={handleArrowToggle}
          role="presentation"
        >
          ▾
        </span>
      </button>
      {isOpen ? (
        <div className="panel-controls-combo__menu" role="listbox">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={option.disabled}
              className={
                (
                  activeValue === undefined
                    ? option.value === selectedValue
                    : option.value === activeValue
                )
                  ? 'button button--micro button--micro-active'
                  : 'button button--micro'
              }
              onClick={() => handleOptionClick(option)}
            >
              {option.icon ? (
                <span className="panel-controls-combo__icon">{option.icon}</span>
              ) : null}
              <span className="panel-controls-combo__label">{option.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default PanelControlsCombo;
