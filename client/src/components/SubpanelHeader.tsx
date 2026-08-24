import type { FC, ReactNode } from "react";

interface SubpanelHeaderProps {
  title: string;
  controls?: ReactNode;
}

const SubpanelHeader: FC<SubpanelHeaderProps> = ({ title, controls }) => (
  <header className="subpanel__header">
    <h3 className="subpanel__title">{title}</h3>
    {controls ? <div className="subpanel__controls">{controls}</div> : null}
  </header>
);

export default SubpanelHeader;
