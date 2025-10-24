import { Link } from "react-router-dom";
import type { PropsWithChildren } from "react";

const Layout = ({ children }: PropsWithChildren) => (
  <div className="app-shell">
    <header className="app-header">
      <Link to="/" className="brand">
        Monstr
      </Link>
    </header>
    <main className="app-main">{children}</main>
  </div>
);

export default Layout;
