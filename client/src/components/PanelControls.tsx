import type { ComponentProps, FC, ReactElement } from "react";

import PanelControlsButton from "./PanelControlsButton";

type PanelControlsButtonElement = ReactElement<ComponentProps<typeof PanelControlsButton>>;

interface PanelControlsProps {
  ariaLabel: string;
  buttons: PanelControlsButtonElement[];
}

const PanelControls: FC<PanelControlsProps> = ({ ariaLabel, buttons }) => (
  <div className="panel-controls">
    <div className="button-group button-group--micro" role="group" aria-label={ariaLabel}>
      {buttons}
    </div>
  </div>
);

export default PanelControls;
