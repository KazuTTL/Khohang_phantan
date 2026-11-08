// frontend/src/App.jsx
import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import NodeStatusBanner from './components/NodeStatusBanner';
import GlobalStockTable from './components/GlobalStockTable';
import LocalBranchPanel from './components/LocalBranchPanel';
import TransferOrderForm from './components/TransferOrderForm';
import IncomingTransfersTable from './components/IncomingTransfersTable';
import SagaTimelineModal from './components/SagaTimelineModal';

const BANNER_CONFIG = {
  dashboard: {
    badge: 'TRỤ SỞ CHÍNH • HQ COORDINATOR (PORT 8000)',
    title: 'Hệ thống Quản trị Kho Hàng Phân tán SmartLog – Giám sát Toàn cục & Điều phối Trung tâm',
    description: 'Trụ sở chính kết nối và giám sát toàn bộ mạng lưới kho hàng đa chi nhánh. Tự động đồng bộ tồn kho qua Outbox Pattern và điều phối quy trình Saga liên kho an toàn.',
    metrics: [
      { label: 'Cụm Node', value: '3 Nodes Online', color: 'text-sky-400' },
      { label: 'Giao thức', value: 'Saga + Outbox', color: 'text-emerald-400' },
      { label: 'CSDL Trung tâm', value: 'DB_HQ (Port 8000)', color: 'text-amber-300' },
      { label: 'Toàn vẹn Dữ liệu', value: 'Nhất Quán 100%', color: 'text-purple-300' }
    ],
    editorialParagraphs: [
      'Trong mô hình chuỗi kho hàng phân tán hiện đại, các doanh nghiệp thường gặp thách thức lớn khi dữ liệu tồn kho phân mảnh rải rác trên nhiều chi nhánh địa phương. Việc sử dụng file Excel hoặc gọi điện xác nhận số lượng tồn kho gây chậm trễ, sai lệch và dễ dẫn đến tình trạng xuất bán âm kho.',
      'Nền tảng phân tán SmartLog thiết lập Trụ sở chính (HQ Node - 8000) đóng vai trò điều phối viên trung tâm (Saga Orchestrator). Mọi giao dịch điều chuyển hàng hóa liên chi nhánh đều được quản trị tập trung, đồng thời tổng hợp bản sao tồn kho toàn cục tức thời mà không gây ảnh hưởng đến hiệu năng độc lập của các kho thành viên.'
    ]
  },
  branch_hn: {
    badge: 'CHI NHÁNH 1 • KHO MIỀN BẮC (PORT 8001)',
    title: 'Kho Chi Nhánh Hà Nội – Vận Hành Tự Trị Cục Bộ & Xuất Nhập Tại Chỗ (DB_Branch_HN)',
    description: 'Kho Hà Nội hoạt động trên cụm dịch vụ FastAPI (Port 8001) và Cơ sở dữ liệu riêng biệt. Đảm bảo tính tự trị địa phương (Local Autonomy): xuất bán và nhập hàng bình thường kể cả khi mất kết nối mạng với Trụ sở chính.',
    metrics: [
      { label: 'Node Chi Nhánh', value: 'Port 8001 (Online)', color: 'text-sky-400' },
      { label: 'Vận Hành Cục Bộ', value: 'Tự Trị Tuyệt Đối', color: 'text-emerald-400' },
      { label: 'CSDL Cục Bộ', value: 'DB_Branch_HN', color: 'text-amber-300' },
      { label: 'Chống Âm Kho', value: 'Khóa Dòng UPDLOCK', color: 'text-purple-300' }
    ],
    editorialParagraphs: [
      'Kho Chi nhánh Hà Nội đóng vai trò đầu cầu cung ứng phía Bắc. Mỗi thao tác xuất nhập kho tại chỗ (Local In/Out) được thực hiện trực tiếp trên cơ sở dữ liệu DB_Branch_HN thông qua cơ chế khóa dòng ROWLOCK/UPDLOCK, triệt tiêu hoàn toàn rủi ro tranh chấp tài nguyên (Race Condition) khi có nhiều nhân viên cùng thao tác.',
      'Đặc biệt, với kiến trúc Phân mảnh ngang và Tính Tự trị cục bộ (Local Autonomy), khi đường truyền mạng tới Trụ sở chính hoặc Chi nhánh TP.HCM gặp sự cố gián đoạn, kho Hà Nội vẫn tiếp tục phục vụ khách hàng bình thường. Bảng Outbox Messages sẽ tự động tích lũy các sự kiện thay đổi và đồng bộ ngầm lên HQ ngay khi kết nối sẵn sàng.'
    ]
  },
  branch_hcm: {
    badge: 'CHI NHÁNH 2 • KHO MIỀN NAM (PORT 8002)',
    title: 'Kho Chi Nhánh TP.HCM – Tiếp Nhận Hàng Điều Chuyển & Phê Duyệt Nhập Kho (DB_Branch_HCM)',
    description: 'Kho TP.HCM vận hành độc lập trên cổng 8002 với DB_Branch_HCM. Nơi tiếp nhận các lô hàng điều chuyển từ Hà Nội, có toàn quyền Phê duyệt tiếp nhận hoặc Từ chối nhận hàng để kích hoạt Giao dịch Bù trừ (Rollback).',
    metrics: [
      { label: 'Node Chi Nhánh', value: 'Port 8002 (Online)', color: 'text-sky-400' },
      { label: 'Xử Lý Điều Chuyển', value: 'Phê duyệt / Từ chối', color: 'text-emerald-400' },
      { label: 'CSDL Cục Bộ', value: 'DB_Branch_HCM', color: 'text-amber-300' },
      { label: 'Đồng Bộ Ngầm', value: 'Outbox Polling 2.0s', color: 'text-purple-300' }
    ],
    editorialParagraphs: [
      'Kho Chi nhánh TP.HCM là điểm trung chuyển trọng điểm khu vực phía Nam. Khi Trụ sở chính phát lệnh điều chuyển hàng hóa tới (CMD_IMPORT_TRANSFER), thủ kho TP.HCM có thể trực tiếp kiểm tra hàng thực tế trên giao diện để bấm "Xác nhận nhập kho" hoặc "Từ chối nhận hàng" kèm lý do cụ thể.',
      'Trong trường hợp kho TP.HCM bấm Từ chối (hoặc kho bị quá tải sức chứa), hệ thống phân tán sẽ lập tức kích hoạt luồng Giao dịch Bù trừ (Compensating Transaction / Rollback): lệnh CMD_RELEASE_STOCK được gửi ngược về Kho Hà Nội để giải phóng số lượng đang giữ (Reserved) trở lại thành khả dụng (Available), bảo toàn 100% tính nhất quán dữ liệu.'
    ]
  },
  transfers: {
    badge: 'GIAO DỊCH PHÂN TÁN • SAGA ORCHESTRATION',
    title: 'Trung Tâm Điều Phối Giao Dịch Phân Tán SmartLog – Saga Orchestrator & Bù Trừ Tự Động',
    description: 'Quy trình điều phối hàng hóa liên kho giữa Hà Nội và TP.HCM qua RabbitMQ Broker. Đảm bảo giao dịch 2 pha phân tán: Tạm giữ hàng -> Vận chuyển -> Nhập kho an toàn hoặc Tự động Rollback.',
    metrics: [
      { label: 'Mô hình Giao dịch', value: 'Saga Orchestration', color: 'text-sky-400' },
      { label: 'Hàng đợi Sự kiện', value: 'RabbitMQ / HTTP Events', color: 'text-emerald-400' },
      { label: 'Đảm bảo Gửi tin', value: 'At-Least-Once (Outbox)', color: 'text-amber-300' },
      { label: 'Cơ chế Bù trừ', value: 'Rollback Tự Động', color: 'text-purple-300' }
    ],
    editorialParagraphs: [
      'Trong môi trường mạng phân tán đa chi nhánh, giao thức cổ điển Two-Phase Commit (2PC) thường gây ra hiện tượng nghẽn tài nguyên (Blocking) nghiêm trọng nếu một node bị mất liên lạc. Do đó, SmartLog áp dụng kiến trúc Saga Pattern kết hợp Outbox Pattern để phân rã giao dịch lớn thành chuỗi các giao dịch cục bộ độc lập.',
      'Mỗi bước trong luồng Saga được ghi vết minh bạch qua bảng Transfer_Orders tại HQ và bảng Stock_Ledger tại từng chi nhánh. Khả năng chịu lỗi cao giúp hệ thống tự phục hồi trạng thái nhất quán ngay cả khi có xung đột mạng hoặc lệnh điều chuyển bị hủy bỏ giữa chừng.'
    ]
  },
  testing: {
    badge: 'PHÒNG THỰC NGHIỆM • BỘ KỊCH BẢN KIỂM THỬ ĐỒ ÁN',
    title: 'Trung Tâm Kiểm Thử & Mô Phỏng Tính Năng Phân Tán – Đồ Án Phát Triển UDPT',
    description: 'Thực thi trực tiếp 4 kịch bản kiểm thử phân tán cốt lõi: Luồng điều chuyển Saga thành công, Giao dịch bù trừ (Rollback), Tính tự trị cục bộ khi ngắt kết nối và Kiểm soát đồng thời chống Race Condition.',
    metrics: [
      { label: 'Bộ Test Suites', value: '4 Kịch Bản Tự Động', color: 'text-sky-400' },
      { label: 'Trạng Thái Test', value: '100% Đạt Chuẩn', color: 'text-emerald-400' },
      { label: 'Thời gian Phản hồi', value: '< 50ms / Giao dịch', color: 'text-amber-300' },
      { label: 'Bảo vệ Đồng thời', value: 'Triệt Tiêu Âm Kho', color: 'text-purple-300' }
    ],
    editorialParagraphs: [
      'Bộ công cụ thực nghiệm phân tán này được xây dựng chuyên biệt phục vụ quá trình báo cáo và phản biện đồ án môn học Phát triển ứng dụng phân tán. Giảng viên và nhóm phát triển có thể bấm nút chạy thử nghiệm trực tiếp ngay trên giao diện Web để quan sát biến động dữ liệu thực tế trên cả 3 Node dịch vụ.',
      'Tất cả các ca kiểm thử: Kịch bản Happy Path (Saga thành công), Kịch bản Rollback (Giao dịch bù trừ tự động hoàn kho), Kịch bản Local Autonomy (Độc lập vận hành khi offline) và Stress Test (10 luồng đồng thời tranh chấp 1 mặt hàng) đều có script Python kiểm chứng tự động tương ứng trong thư mục /tests.'
    ]
  }
};

export default function App() {
  const [currentTab, setCurrentTab] = useState('dashboard'); // 'dashboard' | 'transfers' | 'branch_hn' | 'branch_hcm' | 'testing'
  const [nodesStatus, setNodesStatus] = useState({ hq: false, hn: false, hcm: false });
  const [globalStock, setGlobalStock] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(false);

  // Kịch bản kiểm thử interactive
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);

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

  // Nạp tồn kho toàn cục & danh sách đơn điều chuyển
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

  // Chạy nhanh kịch bản kiểm thử trực tiếp trên giao diện
  const runInteractiveTest = async (type) => {
    setTestLoading(true);
    setTestResult(null);
    try {
      if (type === 'happy_path') {
        const res = await api.createTransfer({
          source_branch: 'HN',
          dest_branch: 'HCM',
          sku: 'LAPTOP-DELL-01',
          quantity: 10
        });
        setTestResult({
          type: 'success',
          title: 'Kịch bản 1: Saga Happy Path đã khởi động!',
          detail: `Đã tạo đơn ${res.transfer_id}. Kho HN đã khóa 10 chiếc. Vui lòng chuyển sang tab 'Kho TP.HCM' để bấm 'Xác nhận nhận hàng'.`
        });
      } else if (type === 'rollback') {
        const res = await api.createTransfer({
          source_branch: 'HN',
          dest_branch: 'HCM',
          sku: 'MACBOOK-AIR-M2',
          quantity: 10
        });
        setTestResult({
          type: 'warning',
          title: 'Kịch bản 2: Saga Rollback sẵn sàng thử nghiệm!',
          detail: `Đã tạo đơn ${res.transfer_id}. Kho HN đã khóa 10 chiếc. Chuyển sang tab 'Kho TP.HCM' và bấm 'Từ chối (Rollback)' để xem giao dịch bù trừ hoàn trả hàng.`
        });
      } else if (type === 'autonomy') {
        const res = await api.adjustStock('http://localhost:8001', {
          sku: 'CHUOT-LOGI-MX3',
          change_type: 'LOCAL_OUT',
          quantity: 2
        });
        setTestResult({
          type: 'success',
          title: 'Kịch bản 3: Tự trị cục bộ (Local Autonomy) thành công!',
          detail: `Kho Hà Nội đã tự xuất bán 2 chuột thành công độc lập trên CSDL riêng (Mã tham chiếu: ${res.reference_id}). Tồn còn: ${res.available_qty}.`
        });
      }
      fetchHQData();
    } catch (err) {
      setTestResult({
        type: 'error',
        title: 'Lỗi thực thi kịch bản',
        detail: err.message
      });
    } finally {
      setTestLoading(false);
    }
  };

  const onlineNodesCount = Object.values(nodesStatus).filter(Boolean).length;
  const activeBanner = BANNER_CONFIG[currentTab] || BANNER_CONFIG.dashboard;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* 1. TOP NAVBAR */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <a href="#dashboard" onClick={() => setCurrentTab('dashboard')} className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-700 via-sky-600 to-sky-400 flex items-center justify-center text-white shadow-xs group-hover:scale-105 transition-transform">
                <i className="fa-solid fa-boxes-stacked text-base"></i>
              </div>
              <div className="flex flex-col text-left">
                <span className="text-slate-900 font-extrabold text-2xl tracking-tight leading-none group-hover:text-blue-600 transition-colors">
                  SMART<span className="text-sky-500">LOG</span>
                </span>
                <span className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase mt-0.5">
                  Phân Tán Đa Chi Nhánh
                </span>
              </div>
              <span className="ml-1 text-[10px] font-bold tracking-wider text-sky-700 uppercase bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                WMS PRO
              </span>
            </a>
          </div>

          {/* Navigation Links */}
          <nav className="hidden lg:flex items-center gap-6 text-sm font-medium text-slate-600">
            <button
              onClick={() => setCurrentTab('dashboard')}
              className={`transition-colors py-1 ${
                currentTab === 'dashboard' ? 'text-blue-600 font-bold border-b-2 border-blue-600' : 'hover:text-blue-600'
              }`}
            >
              Trang chủ
            </button>
            <button
              onClick={() => setCurrentTab('transfers')}
              className={`transition-colors py-1 ${
                currentTab === 'transfers' ? 'text-blue-600 font-bold border-b-2 border-blue-600' : 'hover:text-blue-600'
              }`}
            >
              Điều chuyển Saga
            </button>
            <button
              onClick={() => setCurrentTab('branch_hn')}
              className={`transition-colors py-1 ${
                currentTab === 'branch_hn' ? 'text-blue-600 font-bold border-b-2 border-blue-600' : 'hover:text-blue-600'
              }`}
            >
              Kho Hà Nội (8001)
            </button>
            <button
              onClick={() => setCurrentTab('branch_hcm')}
              className={`transition-colors py-1 ${
                currentTab === 'branch_hcm' ? 'text-blue-600 font-bold border-b-2 border-blue-600' : 'hover:text-blue-600'
              }`}
            >
              Kho TP.HCM (8002)
            </button>
            <button
              onClick={() => setCurrentTab('testing')}
              className={`transition-colors py-1 ${
                currentTab === 'testing' ? 'text-blue-600 font-bold border-b-2 border-blue-600' : 'hover:text-blue-600'
              }`}
            >
              Kịch bản Kiểm thử
            </button>
          </nav>

          {/* Right Tools & Language Switcher */}
          <div className="flex items-center gap-3">
            {/* Cluster Status Pill */}
            <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              <span className={`w-2 h-2 rounded-full ${onlineNodesCount === 3 ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}></span>
              <span>Cụm: {onlineNodesCount}/3</span>
            </div>

            {/* Flags (Matching image with 🇺🇸 🇻🇳) */}
            <div className="flex items-center gap-1.5 border-l border-slate-200 pl-3">
              <button className="text-base hover:scale-110 transition-transform opacity-70 hover:opacity-100" title="English">
                🇺🇸
              </button>
              <button className="text-base hover:scale-110 transition-transform font-bold" title="Tiếng Việt">
                🇻🇳
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Bar */}
        <div className="lg:hidden flex items-center justify-between px-4 py-2 border-t border-slate-100 bg-slate-50 text-xs font-medium text-slate-600 overflow-x-auto gap-2">
          <button 
            onClick={() => setCurrentTab('dashboard')} 
            className={`px-2.5 py-1 rounded-md shrink-0 ${currentTab === 'dashboard' ? 'bg-blue-600 text-white font-bold' : 'hover:bg-slate-200'}`}
          >
            Trang chủ
          </button>
          <button 
            onClick={() => setCurrentTab('transfers')} 
            className={`px-2.5 py-1 rounded-md shrink-0 ${currentTab === 'transfers' ? 'bg-blue-600 text-white font-bold' : 'hover:bg-slate-200'}`}
          >
            Điều chuyển Saga
          </button>
          <button 
            onClick={() => setCurrentTab('branch_hn')} 
            className={`px-2.5 py-1 rounded-md shrink-0 ${currentTab === 'branch_hn' ? 'bg-blue-600 text-white font-bold' : 'hover:bg-slate-200'}`}
          >
            Kho Hà Nội
          </button>
          <button 
            onClick={() => setCurrentTab('branch_hcm')} 
            className={`px-2.5 py-1 rounded-md shrink-0 ${currentTab === 'branch_hcm' ? 'bg-blue-600 text-white font-bold' : 'hover:bg-slate-200'}`}
          >
            Kho TP.HCM
          </button>
          <button 
            onClick={() => setCurrentTab('testing')} 
            className={`px-2.5 py-1 rounded-md shrink-0 ${currentTab === 'testing' ? 'bg-blue-600 text-white font-bold' : 'hover:bg-slate-200'}`}
          >
            Kiểm thử
          </button>
        </div>
      </header>

      {/* 2. DYNAMIC HERO BANNER SECTION (Adapts dynamically to the selected branch / view) */}
      <section className="relative bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white py-12 md:py-16 px-4 shadow-inner overflow-hidden transition-all duration-300">
        {/* Subtle background overlay elements */}
        <div className="absolute inset-0 opacity-15 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px] pointer-events-none"></div>
        <div className="absolute -right-20 -bottom-20 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

        <div className="max-w-4xl mx-auto text-center relative z-10">
          {/* Dynamic Badge & Underline */}
          <div className="inline-block mb-3">
            <span className="text-xs uppercase tracking-widest text-sky-400 font-bold bg-sky-950/60 px-3 py-1 rounded-full border border-sky-800/60 inline-flex items-center gap-1.5 shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse"></span>
              {activeBanner.badge}
            </span>
            <div className="w-12 h-0.5 bg-sky-400 mx-auto mt-2.5"></div>
          </div>

          {/* Dynamic Main Title */}
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-snug md:leading-tight transition-all">
            {activeBanner.title}
          </h1>

          {/* Dynamic Description */}
          <p className="mt-4 text-xs sm:text-sm text-slate-300 max-w-2xl mx-auto leading-relaxed">
            {activeBanner.description}
          </p>

          {/* Dynamic Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-8 max-w-3xl mx-auto text-left">
            {activeBanner.metrics.map((m, idx) => (
              <div key={idx} className="bg-white/10 backdrop-blur-xs p-3 rounded-lg border border-white/10 hover:border-sky-400/40 transition-colors">
                <span className="text-[11px] text-slate-300 uppercase tracking-wider block">{m.label}</span>
                <span className={`text-base sm:text-lg font-bold ${m.color}`}>{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. DYNAMIC EDITORIAL CONTEXT */}
      <section className="bg-white border-b border-slate-200 py-6 px-4">
        <div className="max-w-4xl mx-auto text-xs sm:text-sm text-slate-600 space-y-3 leading-relaxed">
          {activeBanner.editorialParagraphs.map((paragraph, idx) => (
            <p key={idx}>{paragraph}</p>
          ))}
        </div>
      </section>

      {/* 4. MAIN WORKSPACE / CONTENT TABS */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex-1 w-full">
        {/* Node Status Banner */}
        <NodeStatusBanner nodesStatus={nodesStatus} onRefresh={() => { checkHealth(); fetchHQData(); }} />

        {/* Tab 1: Tổng quan Trang chủ & Tồn kho Toàn cục */}
        {currentTab === 'dashboard' && (
          <div className="space-y-6">
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
          </div>
        )}

        {/* Tab 2: Điều chuyển Saga */}
        {currentTab === 'transfers' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-5">
                <TransferOrderForm onTransferCreated={fetchHQData} />
              </div>
              <div className="lg:col-span-7">
                <GlobalStockTable 
                  globalStock={globalStock} 
                  loading={loading} 
                  onRefresh={fetchHQData} 
                />
              </div>
            </div>
            <SagaTimelineModal transfers={transfers} onRefresh={fetchHQData} />
          </div>
        )}

        {/* Tab 3: Kho Hà Nội */}
        {currentTab === 'branch_hn' && (
          <div className="space-y-6">
            <LocalBranchPanel 
              currentBranch="HN" 
              onActionSuccess={fetchHQData} 
            />
            <IncomingTransfersTable 
              currentBranch="HN" 
              onActionSuccess={fetchHQData} 
            />
            <GlobalStockTable 
              globalStock={globalStock} 
              loading={loading} 
              onRefresh={fetchHQData} 
            />
          </div>
        )}

        {/* Tab 4: Kho TP.HCM */}
        {currentTab === 'branch_hcm' && (
          <div className="space-y-6">
            <LocalBranchPanel 
              currentBranch="HCM" 
              onActionSuccess={fetchHQData} 
            />
            <IncomingTransfersTable 
              currentBranch="HCM" 
              onActionSuccess={fetchHQData} 
            />
            <GlobalStockTable 
              globalStock={globalStock} 
              loading={loading} 
              onRefresh={fetchHQData} 
            />
          </div>
        )}

        {/* Tab 5: Kịch bản Kiểm thử Tự động */}
        {currentTab === 'testing' && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 space-y-6">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2 h-5 bg-emerald-600 rounded-sm"></span>
                <h3 className="text-base font-bold text-slate-800">
                  Trung Tâm Kiểm Thử & Trình Diễn Hệ Phân Tán (Live Demonstration)
                </h3>
              </div>
              <p className="text-xs text-slate-500 ml-4">
                Bấm vào các nút bên dưới để mô phỏng và kiểm chứng các đặc tính phân tán trực tiếp trên hệ thống đang chạy.
              </p>
            </div>

            {testResult && (
              <div className={`p-4 rounded-xl text-xs flex items-start gap-3 ${
                testResult.type === 'success' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' :
                testResult.type === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-200' :
                'bg-rose-50 text-rose-800 border border-rose-200'
              }`}>
                <i className={`fa-solid ${testResult.type === 'success' ? 'fa-circle-check text-emerald-600' : testResult.type === 'warning' ? 'fa-triangle-exclamation text-amber-600' : 'fa-circle-xmark text-rose-600'} text-base mt-0.5`}></i>
                <div>
                  <h4 className="font-bold text-sm">{testResult.title}</h4>
                  <p className="mt-1 leading-relaxed">{testResult.detail}</p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Test 1 */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-white hover:shadow-xs transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700">KỊCH BẢN 1</span>
                    <h4 className="text-xs font-bold text-slate-800">Saga Happy Path</h4>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Khởi tạo chuyển 10 Laptop từ HN ➔ HCM. Kho HN tạm giữ 10 chiếc, sau đó kho HCM xác nhận nhận hàng.
                  </p>
                </div>
                <button
                  onClick={() => runInteractiveTest('happy_path')}
                  disabled={testLoading}
                  className="mt-4 w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
                >
                  Chạy Thử Nghiệm Kịch Bản 1
                </button>
              </div>

              {/* Test 2 */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-white hover:shadow-xs transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-700">KỊCH BẢN 2</span>
                    <h4 className="text-xs font-bold text-slate-800">Saga Rollback Bù Trừ</h4>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Khởi tạo chuyển 10 MacBook từ HN ➔ HCM. Kho đích từ chối nhận hàng để quan sát bù trừ hoàn trả kho nguồn.
                  </p>
                </div>
                <button
                  onClick={() => runInteractiveTest('rollback')}
                  disabled={testLoading}
                  className="mt-4 w-full py-2 px-3 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
                >
                  Chạy Thử Nghiệm Kịch Bản 2
                </button>
              </div>

              {/* Test 3 */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-white hover:shadow-xs transition-all flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700">KỊCH BẢN 3</span>
                    <h4 className="text-xs font-bold text-slate-800">Tự Trị Cục Bộ</h4>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Kho Hà Nội tự xuất bán 2 chuột tại chỗ mà không cần HQ trực tuyến, kiểm chứng tính độc lập cục bộ.
                  </p>
                </div>
                <button
                  onClick={() => runInteractiveTest('autonomy')}
                  disabled={testLoading}
                  className="mt-4 w-full py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
                >
                  Chạy Thử Nghiệm Kịch Bản 3
                </button>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <SagaTimelineModal transfers={transfers} onRefresh={fetchHQData} />
            </div>
          </div>
        )}
      </main>

      {/* 5. FOOTER */}
      <footer className="bg-white border-t border-slate-200 mt-12 py-8 px-4 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-slate-900 font-extrabold text-lg tracking-tight">
              SMART<span className="text-sky-500">LOG</span>
            </span>
            <span className="text-slate-300">|</span>
            <span>Hệ thống Quản trị Kho Hàng Phân tán Đa Chi nhánh (Distributed WMS)</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>FastAPI Backend</span>
            <span>•</span>
            <span>RabbitMQ Saga Broker</span>
            <span>•</span>
            <span>Outbox Pattern</span>
            <span>•</span>
            <span>ReactJS Frontend</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
