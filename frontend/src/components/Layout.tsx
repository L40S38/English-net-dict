import { Outlet } from "react-router-dom";

import { SearchHeader } from "./SearchHeader";

export function Layout() {
  return (
    <>
      <SearchHeader />
      <Outlet />
    </>
  );
}
