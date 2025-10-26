import type { PropsWithChildren } from "react";

const Layout = ({ children }: PropsWithChildren) => (
  <div className="app-shell">
    <main className="app-main">{children}</main>
  </div>
);

export default Layout;
