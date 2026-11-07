// frontend/src/App.jsx
import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import NodeStatusBanner from './components/NodeStatusBanner';
import GlobalStockTable from './components/GlobalStockTable';
import LocalBranchPanel from './components/LocalBranchPanel';
import TransferOrderForm from './components/TransferOrderForm';
import IncomingTransfersTable from './components/IncomingTransfersTable';
import SagaTimelineModal from './components/SagaTimelineModal';

export default function App() {
  const [currentRole, setCurrentRole] = useState('HQ'); // 'HQ' | 'HN' | 'HCM'
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

  // Lấy dữ liệu tồn kho toàn cục & đơn điều chuyển từ HQ
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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-900/50">
              <i className="fa-solid fa-warehouse text-white text-lg"></i>
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                DISTRIBUTED WMS
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Saga + Outbox
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Hệ thống Quản lý Kho hàng Phân tán Đa Chi nhánh (Đồ án Môn UDPT)
              </p>
            </div>
          </div>

          {/* Role Switcher */}
          <div className="flex items-center bg-slate-800/80 p-1 rounded-xl border border-slate-700/80 shadow-inner self-start md:self-auto">
            <span className="text-xs font-semibold px-3 text-slate-400 flex items-center gap-1.5">
              <i className="fa-solid fa-user-tag text-indigo-400"></i>
              Góc nhìn:
            </span>
            <button
              onClick={() => setCurrentRole('HQ')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                currentRole === 'HQ'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/50'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <i className="fa-solid fa-building-columns"></i>
              Trụ sở chính (HQ - 8000)
            </button>
            <button
              onClick={() => setCurrentRole('HN')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                currentRole === 'HN'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/50'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <i className="fa-solid fa-map-pin"></i>
              Kho Hà Nội (8001)
            </button>
            <button
              onClick={() => setCurrentRole('HCM')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                currentRole === 'HCM'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/50'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <i className="fa-solid fa-map-pin"></i>
              Kho TP.HCM (8002)
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-6 flex-1 w-full">
        {/* Node Status Banner */}
        <NodeStatusBanner nodesStatus={nodesStatus} />

        {/* Nội dung theo từng vai trò */}
        {currentRole === 'HQ' ? (
          <div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
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
          </div>
        ) : (
          <div>
            {/* Chi nhánh Hà Nội hoặc TP.HCM */}
            <LocalBranchPanel 
              currentBranch={currentRole} 
              onActionSuccess={fetchHQData} 
            />

            {/* Bảng kiện hàng đang chuyển tới chi nhánh */}
            <IncomingTransfersTable 
              currentBranch={currentRole} 
              onActionSuccess={fetchHQData} 
            />

            {/* Bảng tồn kho toàn hệ thống để đối soát */}
            <div className="mt-6">
              <GlobalStockTable 
                globalStock={globalStock} 
                loading={loading} 
                onRefresh={fetchHQData} 
              />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-900/60 border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        Đồ án Phát triển Ứng dụng Phân tán • Nhóm 3 Thành viên • Kiến trúc: FastAPI + SQL Server + RabbitMQ + ReactJS
      </footer>
    </div>
  );
}
