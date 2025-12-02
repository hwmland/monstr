import type { FC, ReactNode } from "react";

interface PanelControlsProps {
  ariaLabel: string;
  buttons: ReactNode[];
}

const PanelControls: FC<PanelControlsProps> = ({ ariaLabel, buttons }) => (
  <div className="panel-controls">
    <div className="button-group button-group--micro" role="group" aria-label={ariaLabel}>
      {buttons}
    </div>
  </div>
);

export default PanelControls;
