import { NavLink, Outlet, useMatch } from "react-router-dom";
import { logout } from "../api/authApi";
import { useAuth } from "./AuthContext";
import { useCurriculumCode } from "./curriculumParam";
import { PS_GUIDELINE } from "./psGuideline";

/**
 * Who is signed in (for recording a Manual Review of a PS the configuration reviews by the user), with a
 * sign-out — kept out of the `.topbar` above (a fixed, link-only nav the tests lock down) and shown instead
 * as its own small line at the top of the page content, on every page.
 */
function AccountBar() {
  const { user, signOut } = useAuth();
  const { search } = useCurriculumCode();
  const onLogout = async () => {
    try {
      await logout();
    } catch {
      /* best effort: the local sign-in state clears below regardless */
    } finally {
      signOut();
    }
  };
  return (
    <div className="mb-4 flex min-h-[44px] items-center justify-end gap-2 text-base" style={{ color: "var(--muted)" }}>
      {user ? (
        <span className="flex items-center gap-2">
          ผู้ใช้งาน: <strong style={{ color: "var(--text)" }}>{user.name}</strong>
          <button
            type="button"
            className="inline-flex min-h-[44px] items-center font-medium underline-offset-4 hover:underline"
            style={{ color: "var(--primary-dark)" }}
            onClick={onLogout}
            data-testid="logout"
          >
            ออกจากระบบ
          </button>
        </span>
      ) : (
        <NavLink
          className="inline-flex min-h-[44px] items-center font-medium underline-offset-4 hover:underline"
          style={{ color: "var(--primary-dark)" }}
          to={`/login${search}`}
          data-testid="login-link"
        >
          เข้าสู่ระบบ
        </NavLink>
      )}
    </div>
  );
}

/**
 * Top bar on every page: AUN-QA, and inside the Programme Standards section (/monitor/ps…) the links
 * PS-01 … PS-09 to their detail pages. The list has no visible label; "Programme Standards" is its
 * accessible name. The PS overview (/monitor/ps) opens from the home page's PS card and the detail
 * pages' back link. The PS codes come from psGuideline.js. Links only; it needs no monitoring data.
 */
export function Layout() {
  const { search } = useCurriculumCode();
  const inProgrammeStandards = useMatch("/monitor/ps/*") !== null;
  return (
    <>
      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand-group">
            <NavLink className="brand" to={`/${search}`} end>AUN-QA Monitor</NavLink>
            <span className="brand-subtitle">ระบบติดตามความพร้อมหลักสูตร</span>
          </div>
          <nav aria-label="Main" className="nav">
            {inProgrammeStandards && (
              <ul className="nav__sub nav__group" aria-label="Programme Standards">
                {PS_GUIDELINE.map(({ psCode }) => (
                  <li key={psCode}>
                    <NavLink to={`/monitor/ps/${encodeURIComponent(psCode)}${search}`}>{psCode}</NavLink>
                  </li>
                ))}
              </ul>
            )}
          </nav>
        </div>
      </header>
      <main className="page">
        <AccountBar />
        <Outlet />
      </main>
    </>
  );
}
