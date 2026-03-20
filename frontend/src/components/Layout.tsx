import { useEffect, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { SearchHeader } from "./SearchHeader";

export function Layout() {
  const location = useLocation();
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia("(max-width: 980px)").matches);
  const [connectionErrorMessage, setConnectionErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 980px)");
    const update = () => {
      const mobile = mediaQuery.matches;
      setIsMobile(mobile);
      if (mobile) {
        setMobileMenuOpen(false);
      }
    };
    update();
    mediaQuery.addEventListener("change", update);
    return () => mediaQuery.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (isMobile) {
      setMobileMenuOpen(false);
    }
  }, [isMobile, location.pathname]);

  useEffect(() => {
    const onConnectionError = (event: Event) => {
      const customEvent = event as CustomEvent<{ message?: string }>;
      setConnectionErrorMessage(
        customEvent.detail?.message ??
          "サーバーに接続できません。ネットワークまたはサーバー状態を確認してください。",
      );
    };
    const onConnectionRecovered = () => {
      setConnectionErrorMessage(null);
    };
    window.addEventListener("api-connection-error", onConnectionError as EventListener);
    window.addEventListener("api-connection-recovered", onConnectionRecovered);
    return () => {
      window.removeEventListener("api-connection-error", onConnectionError as EventListener);
      window.removeEventListener("api-connection-recovered", onConnectionRecovered);
    };
  }, []);

  const collapsed = isMobile ? !mobileMenuOpen : desktopCollapsed;
  const showMenuLabels = isMobile || !desktopCollapsed;
  const showToggleText = isMobile || !desktopCollapsed;
  const toggleLabel = collapsed ? "メニューを開く" : "メニューを閉じる";

  return (
    <>
      <SearchHeader />
      {connectionErrorMessage && (
        <div className="connection-error-banner" role="alert">
          {connectionErrorMessage}
        </div>
      )}
      <div className={`app-shell ${collapsed ? "app-shell-collapsed" : ""}`}>
        <aside
          className={`side-menu ${collapsed ? "collapsed" : ""} ${isMobile ? "mobile" : "desktop"} ${
            mobileMenuOpen ? "mobile-open" : "mobile-closed"
          }`}
        >
          <button
            type="button"
            className="side-menu-toggle"
            onClick={() => {
              if (isMobile) {
                setMobileMenuOpen((prev) => !prev);
                return;
              }
              setDesktopCollapsed((prev) => !prev);
            }}
            aria-label={toggleLabel}
            aria-expanded={!collapsed}
          >
            {showToggleText && <span>検索メニュー</span>}
            {isMobile ? (
              collapsed ? (
                <ChevronDown size={18} aria-hidden="true" />
              ) : (
                <ChevronUp size={18} aria-hidden="true" />
              )
            ) : collapsed ? (
              <ChevronRight size={18} aria-hidden="true" />
            ) : (
              <ChevronLeft size={18} aria-hidden="true" />
            )}
          </button>
          {(!isMobile || mobileMenuOpen) && (
            <nav className="side-menu-nav" aria-label="検索モード切り替え">
              <NavLink
                to="/"
                end
                className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
              >
                <span className="side-menu-item-icon">A</span>
                {showMenuLabels && <span>単語検索</span>}
              </NavLink>
              <NavLink
                to="/etymology-search"
                className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
              >
                <span className="side-menu-item-icon">E</span>
                {showMenuLabels && <span>語源検索</span>}
              </NavLink>
              <NavLink
                to="/groups"
                className={({ isActive }) => `side-menu-item ${isActive ? "active" : ""}`}
              >
                <span className="side-menu-item-icon">G</span>
                {showMenuLabels && <span>グループ</span>}
              </NavLink>
            </nav>
          )}
        </aside>
        <div className="app-main">
          <Outlet />
        </div>
      </div>
    </>
  );
}
