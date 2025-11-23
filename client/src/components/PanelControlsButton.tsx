import type { ButtonHTMLAttributes, FC, ReactNode } from "react";

interface PanelControlsButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children" | "content"> {
  active?: boolean;
  content: ReactNode;
}

const PanelControlsButton: FC<PanelControlsButtonProps> = ({ active = false, content, ...rest }) => (
  <button {...rest} className={active ? "button button--micro button--micro-active" : "button button--micro"}>{content}</button>
);

export default PanelControlsButton;
