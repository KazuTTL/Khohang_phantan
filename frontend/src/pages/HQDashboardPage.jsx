// frontend/src/pages/HQDashboardPage.jsx
import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from '../components/Router';
import NodeStatusBanner from '../components/NodeStatusBanner';
import GlobalStockTable from '../components/GlobalStockTable';
import TransferOrderForm from '../components/TransferOrderForm';
import SagaTimelineModal from '../components/SagaTimelineModal';
import NetworkChaosSimulator from '../components/NetworkChaosSimulator';

export default function HQDashboardPage() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [nodesStatus, setNodesStatus] = useState({ hq: false, hn: false, hcm: false });
  const [globalStock, setGlobalStock] = useState([]);
  const [transfers, setTransfers] = useState([]);
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

  // Nạp dữ liệu tồn kho toàn cục & đơn điều chuyển
  const fetchHQData = async () => {
    setLoading(true);
    try {
      const stock = await api.getGlobalInventory();
      setGlobalStock(stock);
      const tOrders = await api.getTransfers();
      setTransfers(tOrders);
    } catch (err) {
      console.error('Lỗi nạp dữ liệu HQ:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchHQData();
    const interval = setInterval(() => {
      checkHealth();
      fetchHQData();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-900/50">
              <i className="fa-solid fa-building-columns text-white text-lg"></i>
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                TRỤ SỞ CHÍNH (HQ COORDINATOR)
              </h1>
              <p className="text-xs text-slate-400">
                Điều phối đơn hàng phân tán, chính sách giá và phân bổ tồn kho liên chi nhánh
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Quick Links to Branches for HQ Supervisor */}
            <div className="flex items-center bg-slate-800/80 p-1 rounded-xl border border-slate-700/80 text-xs">
              <span className="px-2.5 text-slate-400 font-semibold flex items-center gap-1">
                <i className="fa-solid fa-eye text-indigo-400"></i>
                Giám sát:
              </span>
              <Link
                to="/branch/hn"
                className="px-2.5 py-1 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700/50 transition-colors flex items-center gap-1 font-medium"
              >
                <i className="fa-solid fa-location-dot text-indigo-400"></i>
                Kho Hà Nội
              </Link>
              <Link
                to="/branch/hcm"
                className="px-2.5 py-1 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700/50 transition-colors flex items-center gap-1 font-medium"
              >
                <i className="fa-solid fa-location-dot text-violet-400"></i>
                Kho TP.HCM
              </Link>
            </div>

            {/* User Session Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/90 border border-slate-700 text-xs">
              <i className="fa-solid fa-user-shield text-indigo-400"></i>
              <div>
                <span className="font-bold text-slate-200">{currentUser?.full_name || 'Admin HQ'}</span>
                <span className="text-[10px] text-slate-400 block font-mono">@{currentUser?.username || 'admin'} (HQ_MANAGER)</span>
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

        {/* Distributed Properties & Chaos Simulator */}
        <NetworkChaosSimulator />

        {/* Bảng tồn kho toàn cục & Form tạo đơn điều chuyển Saga */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <GlobalStockTable 
              globalStock={globalStock} 
              loading={loading} 
              onRefresh={fetchHQData} 
            />
          </div>
          <div className="lg:col-span-5">
            <TransferOrderForm onTransferCreated={fetchHQData} />
          </div>
        </div>

        {/* Tiến trình Saga trực quan */}
        <SagaTimelineModal transfers={transfers} onRefresh={fetchHQData} />
      </main>

      {/* Footer */}
      <footer className="bg-slate-900/60 border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        Distributed Warehouse Management System • Kiến trúc Microservices: FastAPI + RabbitMQ + ReactJS
      </footer>
    </div>
  );
}
