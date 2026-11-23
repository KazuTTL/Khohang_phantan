// frontend/src/components/AppShell.jsx
import React, { useState } from 'react';
import { Link } from './Router';

export default function AppShell({
  brandTitle,
  brandSubtitle,
  brandIcon = 'fa-warehouse',
  navItems = [],
  activeTab,
  onTabChange,
  currentUser,
  onLogout,
  headerExtra,
  sidebarFooter,
  children,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const roleLabels = {
    HQ_MANAGER: { text: 'Quản trị Trụ sở', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
    BRANCH_MANAGER: { text: 'Trưởng kho', cls: 'bg-sky-50 text-sky-700 border-sky-200' },
    BRANCH_STAFF: { text: 'Thủ kho', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  };
  const roleMeta = roleLabels[currentUser?.role] || { text: currentUser?.role || 'User', cls: 'bg-slate-100 text-slate-700 border-slate-200' };

  const renderSidebarContent = () => (
    <div className="flex flex-col h-full bg-white border-r border-slate-200">
      {/* Brand */}
      <div className="h-16 px-5 flex items-center gap-3 border-b border-slate-200 shrink-0">
        <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-sm">
          <i className={`fa-solid ${brandIcon} text-sm`}></i>
        </div>
        <div className="min-w-0">
          <div className="text-sm font-bold text-slate-900 truncate">{brandTitle}</div>
          <div className="text-[11px] text-slate-500 truncate">{brandSubtitle}</div>
        </div>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Phân hệ Nghiệp vụ
        </div>
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onTabChange(item.id);
                setMobileOpen(false);
              }}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700 font-semibold shadow-xs ring-1 ring-indigo-600/15'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <span className="flex items-center gap-2.5 truncate">
                <i className={`fa-solid ${item.icon} w-4 text-center ${isActive ? 'text-indigo-600' : 'text-slate-400'}`}></i>
                <span className="truncate">{item.label}</span>
              </span>
              {item.badge > 0 && (
                <span className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] font-bold tabular-nums ${
                  item.badgeColor || (isActive ? 'bg-indigo-600 text-white' : 'bg-amber-100 text-amber-800')
                }`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}

        {/* Supervisor Quick Jump for HQ_MANAGER */}
        {currentUser?.role === 'HQ_MANAGER' && (
          <div className="pt-5 mt-4 border-t border-slate-100">
            <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Điều hướng Nhanh 3 Site
            </div>
            <Link
              to="/hq"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              <i className="fa-solid fa-building-columns w-4 text-center text-indigo-500"></i>
              <span>Site 1: Trụ sở chính HQ</span>
            </Link>
            <Link
              to="/branch/hn"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              <i className="fa-solid fa-warehouse w-4 text-center text-sky-500"></i>
              <span>Site 2: Kho Hà Nội (HN)</span>
            </Link>
            <Link
              to="/branch/hcm"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            >
              <i className="fa-solid fa-warehouse w-4 text-center text-violet-500"></i>
              <span>Site 3: Kho TP.HCM (HCM)</span>
            </Link>
          </div>
        )}
      </nav>

      {/* Sidebar Footer */}
      {sidebarFooter && (
        <div className="p-3 border-t border-slate-200 bg-slate-50/70">
          {sidebarFooter}
        </div>
      )}
    </div>
  );

  const activeNavObj = navItems.find((i) => i.id === activeTab);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 sticky top-0 h-screen">
        {renderSidebarContent()}
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)}></div>
          <div className="relative w-64 max-w-[80vw] h-full z-10">
            {renderSidebarContent()}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-16 bg-white border-b border-slate-200 sticky top-0 z-30 px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
            >
              <i className="fa-solid fa-bars"></i>
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm sm:text-base font-bold text-slate-900 truncate">
                {activeNavObj && <i className={`fa-solid ${activeNavObj.icon} text-indigo-600 text-sm`}></i>}
                <span className="truncate">{activeNavObj?.label || brandTitle}</span>
              </div>
              <p className="text-[11px] text-slate-500 hidden sm:block truncate">
                {activeNavObj?.description || brandSubtitle}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {headerExtra}

            {/* User Session Pill */}
            <div className="hidden sm:flex items-center gap-2.5 pl-3 pr-2 py-1.5 rounded-xl bg-slate-50 border border-slate-200">
              <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center text-xs font-bold">
                {(currentUser?.full_name || currentUser?.username || 'U').charAt(0).toUpperCase()}
              </div>
              <div className="text-left leading-tight">
                <div className="text-xs font-semibold text-slate-800">{currentUser?.full_name || currentUser?.username}</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`text-[10px] px-1.5 py-0.2 rounded border font-medium ${roleMeta.cls}`}>
                    {roleMeta.text}
                  </span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onLogout}
              title="Đăng xuất"
              className="px-3 py-2 rounded-lg bg-white hover:bg-rose-50 border border-slate-200 hover:border-rose-200 text-slate-600 hover:text-rose-600 text-xs font-semibold transition-colors flex items-center gap-1.5"
            >
              <i className="fa-solid fa-right-from-bracket"></i>
              <span className="hidden md:inline">Đăng xuất</span>
            </button>
          </div>
        </header>

        {/* Page Body */}
        <main className="flex-1 p-4 sm:p-6 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
