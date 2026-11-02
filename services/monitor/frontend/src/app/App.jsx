import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { HomePage } from "../pages/Home";
import { LoginPage } from "../pages/Login";
import { MonitorPage } from "../pages/Monitor";
import { PSDetailPage } from "../pages/PSDetail";
import { ScopeNoticePage } from "../pages/ScopeNotice";
import { AuthProvider } from "./AuthContext";
import { CRITERIA_GROUPS } from "./criteriaGroups";
import { Layout } from "./Layout";

/** Redirects to the home page, keeping the query (e.g. ?curriculumCode=). */
function ToHome() {
  const { search } = useLocation();
  return <Navigate to={`/${search}`} replace />;
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/monitor/ps" element={<MonitorPage />} />
          <Route path="/monitor/ps/:psCode" element={<PSDetailPage />} />
          {CRITERIA_GROUPS.filter((g) => !g.inScope).map((g) => (
            <Route key={g.key} path={`/monitor/${g.key}`} element={<ScopeNoticePage label={g.label} />} />
          ))}
          <Route path="*" element={<ToHome />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
