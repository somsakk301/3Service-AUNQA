import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {createBrowserRouter, RouterProvider, Navigate, NavLink, Outlet, useLocation, useNavigate} from 'react-router-dom';
import {AuthProvider, useAuth} from '@monitor/app/AuthContext';
import {LoginPage} from '@monitor/pages/Login';
import {MonitorPage} from '@monitor/pages/Monitor';
import {PSDetailPage} from '@monitor/pages/PSDetail';
import {ScopeNoticePage} from '@monitor/pages/ScopeNotice';
import {logout} from '@monitor/api/authApi';
import {GeneratePage} from '@generator/pages/GeneratePage/GeneratePage';
import {HistoryPage} from '@generator/pages/HistoryPage/HistoryPage';
import {ReferencePage} from '@generator/pages/ReferencePage/ReferencePage';
import '@monitor/app/styles.css';
import '@generator/styles/globals.css';
import './style.css';

const links = [['/', 'Dashboard'], ['/import', 'Import Document'], ['/monitor', 'Monitor'],
  ['/monitor/ps/PS-01', 'PS Detail'], ['/generator', 'Generate SAR'],
  ['/generator/history', 'Document History'], ['/generator/reference', 'Reference']];

function SessionLayout() {
  const {user, signIn, signOut} = useAuth();
  const [checking, setChecking] = useState(true);
  const [failure, setFailure] = useState('');
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    fetch('/api/auth/me', {credentials: 'same-origin'})
      .then(async r => {
        if (r.status === 401) { if (active) signOut(); return; }
        if (!r.ok) throw new Error('ไม่สามารถตรวจสอบการเข้าสู่ระบบ กรุณาลองใหม่');
        const u = await r.json();
        if (active) signIn(u);
      }).catch(e => {if (active) setFailure(e.message);})
      .finally(() => {if (active) setChecking(false);});
    return () => {active = false;};
  }, [location.pathname, signIn, signOut]);
  async function leave() {
    setFailure('');
    try { await logout(); signOut(); navigate('/login', {replace:true}); }
    catch {setFailure('ออกจากระบบไม่สำเร็จ กรุณาลองใหม่');}
  }
  if (checking) return <div className="portal-loading" role="status">กำลังตรวจสอบ Session…</div>;
  if (failure) return <main className="portal-loading"><p role="alert">{failure}</p><button onClick={() => window.location.reload()}>ลองใหม่</button></main>;
  if (!user && location.pathname !== '/login') return <Navigate to="/login" replace />;
  if (user && location.pathname === '/login') return <Navigate to="/" replace />;
  return <div className="portal-shell">
    <header className="portal-header"><NavLink to="/" className="portal-brand">AQ <span>AUN-QA Portal<small>ระบบจัดการข้อมูลและรายงานหลักสูตร</small></span></NavLink>
      {user && <div className="portal-account"><span>{user.name}</span><button onClick={leave}>Logout · ออกจากระบบ</button></div>}
    </header>
    {user && <nav className="portal-nav" aria-label="Main navigation">{links.map(([path,label]) => <NavLink end to={path + location.search} key={path}>{label}</NavLink>)}</nav>}
    <main className="portal-content"><Outlet /></main>
    <footer className="portal-footer">AUN-QA · Import → Monitor → Generate</footer>
  </div>;
}

function Dashboard() {
  const [curricula, setCurricula] = useState([]);
  const [error,setError] = useState('');
  const navigate = useNavigate();
  useEffect(() => {fetch('/api/import/curricula').then(r => {if (!r.ok) throw Error('โหลดรายชื่อหลักสูตรไม่สำเร็จ'); return r.json();}).then(setCurricula).catch(e => setError(e.message));},[]);
  return <section><p className="portal-kicker">AUN-QA WORKSPACE</p><h1>ภาพรวมการทำงาน</h1><p>นำเข้าหลักฐาน ตรวจความพร้อม และจัดทำรายงาน SAR ในพื้นที่เดียว</p>
    {error && <p role="alert">{error}</p>}
    <div className="portal-cards">{[['01','นำเข้าเอกสาร','อัปโหลด ตรวจแก้ และยืนยันข้อมูลหลักสูตรและหลักฐาน','/import'],['02','ตรวจความพร้อม','ตรวจข้อมูลตามเกณฑ์ PS พร้อมหลักฐานและรายการที่ขาด','/monitor'],['03','สร้างรายงาน SAR','ใช้แม่แบบและข้อมูลที่ผ่านการตรวจ พร้อมประวัติและแหล่งอ้างอิง','/generator']].map(([n,title,body,path]) => <NavLink className="portal-card" key={n} to={path}><span>{n}</span><h2>{title}</h2><p>{body}</p><strong>เปิดใช้งาน →</strong></NavLink>)}</div>
    <section className="portal-panel"><h2>หลักสูตรในระบบ</h2>{curricula.length ? <ul>{curricula.map(c => <li key={c.curriculumId}><button onClick={() => navigate('/monitor?curriculumCode='+encodeURIComponent(c.curriculumCode))}>{c.curriculumCode} · {c.curriculumName} ({c.curriculumYear})</button></li>)}</ul> : <p>ยังไม่มีหลักสูตร เริ่มจากเมนู Import Document</p>}</section>
  </section>;
}
function ImportPage() {
  return <section><iframe className="import-frame" title="Import Document workspace" src="/import-workspace/" /></section>;
}
function GeneratorLayout() {return <section className="generator-workspace"><Outlet /></section>;}
function AppRoot() {return <AuthProvider><SessionLayout /></AuthProvider>;}
const router = createBrowserRouter([{element:<AppRoot />, errorElement:<main className="portal-loading"><h1>ไม่สามารถเปิดหน้านี้ได้</h1><p>กรุณาโหลดหน้าใหม่ หรือลองกลับไป Dashboard</p><a href="/">กลับ Dashboard</a></main>, children:[
  {path:'/', element:<Dashboard />}, {path:'/login',element:<LoginPage />},
  {path:'/import',element:<ImportPage />}, {path:'/monitor',element:<MonitorPage />},
  {path:'/monitor/ps',element:<MonitorPage />}, {path:'/monitor/ps/:psCode',element:<PSDetailPage />},
  {path:'/monitor/:group',element:<ScopeNoticePage label="เกณฑ์นี้" />},
  {element:<GeneratorLayout />,children:[{path:'/generator',element:<GeneratePage />},
    {path:'/generator/history',element:<HistoryPage />}, {path:'/generator/reference',element:<ReferencePage />},
    {path:'/generator/reference/:version',element:<ReferencePage />}]},
  {path:'*',element:<section><h1>ไม่พบหน้านี้</h1><NavLink to="/">กลับ Dashboard</NavLink></section>}
]}]);
createRoot(document.getElementById('root')).render(<RouterProvider router={router} />);

