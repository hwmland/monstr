import type { FC, ReactNode } from "react";

interface RefreshLabels {
  idle?: string;
  active?: string;
}

interface PanelHeaderProps {
  title: string;
  subtitle?: ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  refreshLabels?: RefreshLabels;
  controls?: ReactNode;
}

const PanelHeader: FC<PanelHeaderProps> = ({
  title,
  subtitle,
  onRefresh,
  isRefreshing = false,
  refreshLabels,
  controls,
}) => {
  const hasActions = Boolean(onRefresh || controls);
  const refreshIdleLabel = refreshLabels?.idle ?? "Refresh";
  const refreshActiveLabel = refreshLabels?.active ?? "Loading...";

  return (
    <header className="panel__header">
      <div>
        <h2 className="panel__title">{title}</h2>
        {subtitle}
      </div>

      {hasActions ? (
        <div className="panel__actions panel__actions--stacked">
          {onRefresh ? (
              <div className="panel-controls__right">
                <button className="button" type="button" onClick={onRefresh} disabled={isRefreshing}>
                  {isRefreshing ? refreshActiveLabel : refreshIdleLabel}
                </button>
              </div>
          ) : null}

          {controls ? <div className="panel-controls">{controls}</div> : null}
        </div>
      ) : null}
    </header>
  );
};

export default PanelHeader;
