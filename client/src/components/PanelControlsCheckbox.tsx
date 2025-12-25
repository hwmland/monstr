import type { FC } from "react";

interface PanelControlsCheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  ariaLabel?: string;
}

const PanelControlsCheckbox: FC<PanelControlsCheckboxProps> = ({ label, checked, onChange, ariaLabel }) => {
  const handleToggle = () => {
    onChange(!checked);
  };

  return (
    <button
      type="button"
      className={checked ? "button button--micro button--micro-active" : "button button--micro"}
      onClick={handleToggle}
      aria-pressed={checked}
      aria-label={ariaLabel ?? label}
    >
      <span className="panel-controls-checkbox__icon" aria-hidden="true">{checked ? "☑" : "☐"}</span>
      <span className="panel-controls-checkbox__label">{label}</span>
    </button>
  );
};

export default PanelControlsCheckbox;
