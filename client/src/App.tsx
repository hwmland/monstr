import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import HomePage from "./pages/Home";
import DashPage from "./dash/DashPage";

const App = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/dash" element={<DashPage />} />
      </Routes>
    </Layout>
  );
};

export default App;
