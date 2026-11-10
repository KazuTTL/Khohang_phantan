// frontend/src/pages/BranchDashboardPage.jsx
import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from '../components/Router';
import NodeStatusBanner from '../components/NodeStatusBanner';
import LocalBranchPanel from '../components/LocalBranchPanel';
import IncomingTransfersTable from '../components/IncomingTransfersTable';
import GlobalStockTable from '../components/GlobalStockTable';

export default function BranchDashboardPage({ branchCode }) {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const isHN = branchCode === 'HN';
  const branchTitle = isHN ? 'HÀ NỘI (PORT 8001)' : 'TP. HỒ CHÍ MINH (PORT 8002)';
  const themeAccent = isHN ? 'indigo' : 'violet';

  const [nodesStatus, setNodesStatus] = useState({ hq: false, hn: false, hcm: false });
  const [globalStock, setGlobalStock] = useState([]);
  const [loading, setLoading] = useState(false);

  // Kiểm tra sức khỏe các Node
  const checkHealth = async () => {
    try {
      const hq = await api.getHQHealth().then(() => true).catch(() => false);
      const hn = await api.getHNHealth().then(() => true).catch(() => false);
      const hcm = await api.getHCMHealth().then(() => true).catch(() => false);
      setNodesStatus({ hq, hn, hcm });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchGlobalStock = async () => {
    setLoading(true);
    try {
      const stock = await api.getGlobalInventory();
      setGlobalStock(stock);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchGlobalStock();
    const interval = setInterval(() => {
      checkHealth();
    }, 4000);
    return () => clearInterval(interval);
  }, [branchCode]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Kiểm tra phân quyền truy cập chéo chi nhánh (Role-based Access Control Guard)
  const isAuthorized = 
    currentUser?.role === 'HQ_MANAGER' || 
    currentUser?.branch === branchCode;

  if (!isAuthorized) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-red-500/40 rounded-2xl p-6 text-center shadow-2xl">
          <div className="w-16 h-16 rounded-full bg-red-950/60 border border-red-500/50 flex items-center justify-center mx-auto mb-4 text-red-400 text-2xl">
            <i className="fa-solid fa-ban"></i>
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Truy Cập Bị Từ Chối (403 Forbidden)</h2>
          <p className="text-xs text-slate-400 mb-4">
            Tài khoản <span className="font-mono font-bold text-amber-300">@{currentUser?.username}</span> trực thuộc Chi nhánh <span className="font-bold text-indigo-300">{currentUser?.branch}</span>, không có quyền can thiệp vào nghiệp vụ của Chi nhánh <span className="font-bold text-violet-300">{branchCode}</span>.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => navigate(`/branch/${currentUser?.branch?.toLowerCase()}`)}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all"
            >
              Về Chi nhánh {currentUser?.branch}
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
            >
              Đổi tài khoản khác
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${isHN ? 'from-blue-600 to-indigo-500 shadow-indigo-900/50' : 'from-purple-600 to-violet-500 shadow-violet-900/50'} flex items-center justify-center shadow-lg`}>
              <i className="fa-solid fa-map-pin text-white text-lg"></i>
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                CHI NHÁNH {branchTitle}
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${isHN ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' : 'bg-violet-500/20 text-violet-300 border-violet-500/30'} border`}>
                  Local Autonomy + Outbox
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Tự trị cục bộ: Quản lý xuất nhập, sổ cái kiểm toán và tiếp nhận kiện hàng liên chi nhánh
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* HQ Supervisor Return Link */}
            {currentUser?.role === 'HQ_MANAGER' && (
              <Link
                to="/hq"
                className="px-3 py-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/80 border border-indigo-500/40 text-indigo-300 text-xs font-semibold transition-all flex items-center gap-1.5"
              >
                <i className="fa-solid fa-arrow-left"></i>
                <span>Về Trụ sở chính HQ</span>
              </Link>
            )}

            {/* User Session Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/90 border border-slate-700 text-xs">
              <i className="fa-solid fa-user-shield text-indigo-400"></i>
              <div>
                <span className="font-bold text-slate-200">{currentUser?.full_name}</span>
                <span className="text-[10px] text-slate-400 block font-mono">@{currentUser?.username} ({currentUser?.role})</span>
              </div>
            </div>

            {/* Logout Button */}
            <button
              onClick={handleLogout}
              title="Đăng xuất khỏi phiên làm việc"
              className="px-3 py-2 rounded-lg bg-red-950/40 hover:bg-red-900/60 border border-red-500/40 text-red-300 text-xs font-semibold transition-all flex items-center gap-1.5"
            >
              <i className="fa-solid fa-right-from-bracket"></i>
              <span>Đăng xuất</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        {/* Node Status Banner */}
        <NodeStatusBanner nodesStatus={nodesStatus} />

        {/* Nghiệp vụ Kho Cục bộ: Xuất Bán, Nhập Mua, Kiểm Kê */}
        <LocalBranchPanel 
          currentBranch={branchCode} 
          onActionSuccess={fetchGlobalStock} 
        />

        {/* Bảng Kiện hàng đang vận chuyển tới chi nhánh */}
        <IncomingTransfersTable 
          currentBranch={branchCode} 
          onActionSuccess={fetchGlobalStock} 
        />

        {/* Bảng Tồn kho Toàn hệ thống để đối soát số liệu */}
        <div className="mt-8 pt-4 border-t border-slate-800/80">
          <div className="mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <i className="fa-solid fa-table-list text-slate-500"></i>
            Bảng đối soát tồn kho toàn quốc (Read-Only)
          </div>
          <GlobalStockTable 
            globalStock={globalStock} 
            loading={loading} 
            onRefresh={fetchGlobalStock} 
            readOnly={true}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900/60 border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        Distributed Warehouse Management System • Kiến trúc Microservices: FastAPI + RabbitMQ + ReactJS
      </footer>
    </div>
  );
}
