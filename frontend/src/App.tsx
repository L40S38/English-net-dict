import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { EtymologyComponentPage } from "./pages/EtymologyComponentPage";
import { HomePage } from "./pages/HomePage";
import { WordDetailPage } from "./pages/WordDetailPage";
import { WordEditPage } from "./pages/WordEditPage";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/etymology-components/:componentText" element={<EtymologyComponentPage />} />
        <Route path="/words/:wordKey" element={<WordDetailPage />} />
        <Route path="/words/:wordKey/edit" element={<WordEditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
