import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { SearchHeader } from "./SearchHeader";

export function Layout() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      <SearchHeader />
      <div className={`app-shell ${collapsed ? "app-shell-collapsed" : ""}`}>
        <aside className={`side-menu ${collapsed ? "collapsed" : ""}`}>
          <button
            type="button"
            className="side-menu-toggle"
            onClick={() => setCollapsed((prev) => !prev)}
            aria-label={collapsed ? "サイドメニューを開く" : "サイドメニューを閉じる"}
          >
            {collapsed ? ">>" : "<<"}
          </button>
          <nav className="side-menu-nav" aria-label="検索モード切り替え">
            <NavLink
              to="/"
              end
              className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
            >
              <span className="side-menu-item-icon">A</span>
              {!collapsed && <span>単語検索</span>}
            </NavLink>
            <NavLink
              to="/etymology-search"
              className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
            >
              <span className="side-menu-item-icon">E</span>
              {!collapsed && <span>語源検索</span>}
            </NavLink>
            <NavLink
              to="/groups"
              className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
            >
              <span className="side-menu-item-icon">G</span>
              {!collapsed && <span>グループ</span>}
            </NavLink>
          </nav>
        </aside>
        <div className="app-main">
          <Outlet />
        </div>
      </div>
    </>
  );
}
