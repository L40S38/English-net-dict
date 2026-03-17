import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { EtymologyComponentPage } from "./pages/EtymologyComponentPage";
import { EtymologySearchPage } from "./pages/EtymologySearchPage";
import { GroupDetailPage } from "./pages/GroupDetailPage";
import { GroupEditPage } from "./pages/GroupEditPage";
import { GroupListPage } from "./pages/GroupListPage";
import { HomePage } from "./pages/HomePage";
import { WordDetailPage } from "./pages/WordDetailPage";
import { WordEditPage } from "./pages/WordEditPage";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/etymology-search" element={<EtymologySearchPage />} />
        <Route path="/etymology-components/:componentText" element={<EtymologyComponentPage />} />
        <Route path="/groups" element={<GroupListPage />} />
        <Route path="/groups/:groupId" element={<GroupDetailPage />} />
        <Route path="/groups/:groupId/edit" element={<GroupEditPage />} />
        <Route path="/words/:wordKey" element={<WordDetailPage />} />
        <Route path="/words/:wordKey/edit" element={<WordEditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
