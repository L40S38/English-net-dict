import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { Layout } from "./components/Layout";
import { DevInflectionModalPage } from "./pages/DevInflectionModalPage";
import { DevInflectionMigrationPage } from "./pages/DevInflectionMigrationPage";
import { EtymologyComponentPage } from "./pages/EtymologyComponentPage";
import { EtymologySearchPage } from "./pages/EtymologySearchPage";
import { GroupDetailPage } from "./pages/GroupDetailPage";
import { GroupEditPage } from "./pages/GroupEditPage";
import { GroupListPage } from "./pages/GroupListPage";
import { HomePage } from "./pages/HomePage";
import { PhraseDetailPage } from "./pages/PhraseDetailPage";
import { PhraseEditPage } from "./pages/PhraseEditPage";
import { PhraseListPage } from "./pages/PhraseListPage";
import { WordDetailPage } from "./pages/WordDetailPage";
import { WordEditPage } from "./pages/WordEditPage";

// GroupEditPage はグループ間のナビゲーション（params のみ変化、remount なし）で
// groupDraft/bulkText/pendingRemoveItem 等のローカル state が前のグループ分を
// 引き継いでしまうため、groupId をキーにして強制的に remount させる。
function GroupEditPageForRoute() {
  const { groupId } = useParams();
  return <GroupEditPage key={groupId} />;
}

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/etymology-search" element={<EtymologySearchPage />} />
        <Route path="/etymology-components/:componentText" element={<EtymologyComponentPage />} />
        <Route path="/groups" element={<GroupListPage />} />
        <Route path="/groups/:groupId" element={<GroupDetailPage />} />
        <Route path="/groups/:groupId/edit" element={<GroupEditPageForRoute />} />
        <Route path="/phrases" element={<PhraseListPage />} />
        <Route path="/phrases/:phraseId" element={<PhraseDetailPage />} />
        <Route path="/phrases/:phraseId/edit" element={<PhraseEditPage />} />
        <Route path="/words/:wordKey" element={<WordDetailPage />} />
        <Route path="/words/:wordKey/edit" element={<WordEditPage />} />
        {import.meta.env.DEV && (
          <Route path="/dev/inflection-modal" element={<DevInflectionModalPage />} />
        )}
        {import.meta.env.DEV && (
          <Route path="/dev/migration/inflection" element={<DevInflectionMigrationPage />} />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
