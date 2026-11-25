// frontend/src/pages/HQDashboardPage.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from '../components/Router';
import AppShell from '../components/AppShell';
import NodeStatusBanner from '../components/NodeStatusBanner';
import GlobalStockTable from '../components/GlobalStockTable';
import TransferOrderForm from '../components/TransferOrderForm';
import SagaTimelineModal from '../components/SagaTimelineModal';

export default function HQDashboardPage() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('overview');
  const [nodesStatus, setNodesStatus] = useState({ hq: false, hn: false, hcm: false });
  const [globalStock, setGlobalStock] = useState([]);
  const [categories, setCategories] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [transferRequests, setTransferRequests] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [clusterData, setClusterData] = useState({ hq: null, hn: null, hcm: null });
  const [schemaData, setSchemaData] = useState({ hq: null, hn: null, hcm: null });
  const [replicaPreview, setReplicaPreview] = useState(null);
  const [transferPrefill, setTransferPrefill] = useState(null);
  const [loading, setLoading] = useState(false);

  // Form tạo ngành hàng (DANH_MUC_SP)
  const [catName, setCatName] = useState('');
  const [catDesc, setCatDesc] = useState('');
  const [catMsg, setCatMsg] = useState(null);

  // Form tạo & quản lý tài khoản (TAI_KHOAN)
  const [accUsername, setAccUsername] = useState('');
  const [accPassword, setAccPassword] = useState('');
  const [accFullName, setAccFullName] = useState('');
  const [accRole, setAccRole] = useState('BRANCH_STAFF');
  const [accBranch, setAccBranch] = useState('HN');
  const [accMsg, setAccMsg] = useState(null);
  const [branchAccounts, setBranchAccounts] = useState({ hn: [], hcm: [] });
  const [accSearch, setAccSearch] = useState('');
  const [accRoleFilter, setAccRoleFilter] = useState('ALL');
  const [accBranchFilter, setAccBranchFilter] = useState('ALL');
  const [accStatusFilter, setAccStatusFilter] = useState('ALL');
  const [accBusyUser, setAccBusyUser] = useState(null);
  const [editingAccount, setEditingAccount] = useState(null);
  const [editForm, setEditForm] = useState({ full_name: '', role: 'BRANCH_STAFF', branch_code: 'HN', password: '', is_active: true });
  const [confirmDeleteUser, setConfirmDeleteUser] = useState(null);

  const checkHealth = async () => {
    try {
      const [hq, hn, hcm] = await Promise.all([
        api.getHQHealth().then(() => true).catch(() => false),
        api.getHNHealth().then(() => true).catch(() => false),
        api.getHCMHealth().then(() => true).catch(() => false),
      ]);
      setNodesStatus({ hq, hn, hcm });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchHQData = async () => {
    setLoading(true);
    try {
      const [stock, tOrders, cats, reqs, accs, hnAccs, hcmAccs] = await Promise.all([
        api.getGlobalInventory().catch(() => []),
        api.getTransfers().catch(() => []),
        api.getCategories().catch(() => []),
        api.getTransferRequests().catch(() => []),
        api.getAccounts().catch(() => []),
        api.getBranchAccounts(HN_URL).catch(() => []),
        api.getBranchAccounts(HCM_URL).catch(() => []),
      ]);
      setGlobalStock(stock);
      setTransfers(tOrders);
      setCategories(cats);
      setTransferRequests(reqs);
      setAccounts(accs);
      setBranchAccounts({ hn: hnAccs, hcm: hcmAccs });
    } catch (err) {
      console.error('Lỗi nạp dữ liệu HQ:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchInfraData = async () => {
    try {
      const [cHQ, cHN, cHCM, sHQ, sHN, sHCM] = await Promise.all([
        api.getHQClusterStatus().catch(() => null),
        api.getBranchClusterStatus(HN_URL).catch(() => null),
        api.getBranchClusterStatus(HCM_URL).catch(() => null),
        api.getHQSchemaOverview().catch(() => null),
        api.getBranchSchemaOverview(HN_URL).catch(() => null),
        api.getBranchSchemaOverview(HCM_URL).catch(() => null),
      ]);
      setClusterData({ hq: cHQ, hn: cHN, hcm: cHCM });
      setSchemaData({ hq: sHQ, hn: sHN, hcm: sHCM });
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchHQData();
    fetchInfraData();
    const interval = setInterval(() => {
      checkHealth();
      fetchHQData();
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'cluster') {
      fetchInfraData();
    }
  }, [activeTab]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleCreateCategory = async (e) => {
    e.preventDefault();
    setCatMsg(null);
    try {
      await api.createCategory({ category_name: catName.trim(), description: catDesc.trim() });
      setCatMsg({ type: 'success', text: `Đã tạo ngành hàng '${catName}' và nhân bản về HN & HCM qua RabbitMQ.` });
      setCatName('');
      setCatDesc('');
      fetchHQData();
    } catch (err) {
      setCatMsg({ type: 'error', text: err.message });
    }
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setAccMsg(null);
    try {
      const res = await api.createAccount({
        username: accUsername.trim(),
        password: accPassword,
        full_name: accFullName.trim(),
        role: accRole,
        branch_code: accBranch,
        is_active: true
      });
      setAccMsg({ type: 'success', text: res.message });
      setAccUsername('');
      setAccPassword('');
      setAccFullName('');
      fetchHQData();
    } catch (err) {
      setAccMsg({ type: 'error', text: err.message });
    }
  };

  const handleToggleAccountLock = async (acc) => {
    setAccMsg(null);
    setAccBusyUser(acc.username);
    try {
      const res = await api.updateAccountStatus(acc.username, !acc.is_active);
      setAccMsg({ type: 'success', text: res.message });
      await fetchHQData();
    } catch (err) {
      setAccMsg({ type: 'error', text: err.message });
    } finally {
      setAccBusyUser(null);
    }
  };

  const openEditAccount = (acc) => {
    setEditingAccount(acc);
    setEditForm({
      full_name: acc.full_name || '',
      role: acc.role || 'BRANCH_STAFF',
      branch_code: acc.branch_code || 'HN',
      password: '',
      is_active: Boolean(acc.is_active),
    });
  };

  const handleSaveEditAccount = async (e) => {
    e.preventDefault();
    if (!editingAccount) return;
    setAccMsg(null);
    setAccBusyUser(editingAccount.username);
    try {
      const payload = {
        full_name: editForm.full_name.trim(),
        role: editForm.role,
        branch_code: editForm.branch_code,
        is_active: editForm.is_active,
      };
      if (editForm.password.trim()) {
        payload.password = editForm.password;
      }
      const res = await api.updateAccount(editingAccount.username, payload);
      setAccMsg({ type: 'success', text: res.message });
      setEditingAccount(null);
      await fetchHQData();
    } catch (err) {
      setAccMsg({ type: 'error', text: err.message });
    } finally {
      setAccBusyUser(null);
    }
  };

  const handleConfirmDeleteAccount = async () => {
    if (!confirmDeleteUser) return;
    setAccMsg(null);
    setAccBusyUser(confirmDeleteUser.username);
    try {
      const res = await api.deleteAccount(confirmDeleteUser.username);
      setAccMsg({ type: 'success', text: res.message });
      setConfirmDeleteUser(null);
      await fetchHQData();
    } catch (err) {
      setAccMsg({ type: 'error', text: err.message });
      setConfirmDeleteUser(null);
    } finally {
      setAccBusyUser(null);
    }
  };

  const handleResyncAccount = async (username) => {
    setAccMsg(null);
    setAccBusyUser(username);
    try {
      const res = await api.resyncAccount(username);
      setAccMsg({ type: 'success', text: res.message });
      setTimeout(fetchHQData, 500);
    } catch (err) {
      setAccMsg({ type: 'error', text: err.message });
    } finally {
      setAccBusyUser(null);
    }
  };

  const handleApproveRequest = async (reqId) => {
    try {
      await api.approveTransferRequest(reqId);
      fetchHQData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRejectRequest = async (reqId) => {
    try {
      await api.rejectTransferRequest(reqId);
      fetchHQData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleReadReplica = async () => {
    try {
      const res = await api.getHQReplicaPreview();
      setReplicaPreview(res);
    } catch (err) {
      alert(err.message);
    }
  };

  // KPI Metrics
  const totalAvail = globalStock.reduce((s, p) => s + (p.total_available || 0), 0);
  const totalRes = globalStock.reduce((s, p) => s + (p.total_reserved || 0), 0);
  const totalSaleValue = globalStock.reduce((s, p) => s + (p.total_available || 0) * (p.price || 0), 0);
  const totalCostValue = globalStock.reduce((s, p) => s + (p.total_available || 0) * (p.cost_price || 0), 0);
  const lowStockItems = globalStock.filter(
    (p) => (p.branches?.HN?.available ?? 0) <= 10 || (p.branches?.HCM?.available ?? 0) <= 10
  );
  const activeSagas = transfers.filter((t) => ['INITIATED', 'RESERVED_IN_TRANSIT', 'COMPENSATING'].includes(t.saga_status));
  const pendingPullRequests = transferRequests.filter((r) => r.status === 'PENDING');

  // Smart Rebalance Suggestions
  const rebalanceSuggestions = globalStock
    .map((p) => {
      const hn = p.branches?.HN?.available ?? 0;
      const hcm = p.branches?.HCM?.available ?? 0;
      if (hn <= 10 && hcm >= 25) {
        return { sku: p.sku, name: p.product_name, source: 'HCM', dest: 'HN', qty: Math.min(15, Math.floor((hcm - hn) / 2)), srcAvail: hcm, dstAvail: hn };
      }
      if (hcm <= 10 && hn >= 25) {
        return { sku: p.sku, name: p.product_name, source: 'HN', dest: 'HCM', qty: Math.min(15, Math.floor((hn - hcm) / 2)), srcAvail: hn, dstAvail: hcm };
      }
      return null;
    })
    .filter(Boolean);

  // Account Management helpers & filters
  const roleMeta = (role) => {
    if (role === 'HQ_MANAGER') return { label: 'Quản trị HQ', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
    if (role === 'BRANCH_MANAGER') return { label: 'Trưởng kho', cls: 'bg-sky-50 text-sky-700 border-sky-200' };
    return { label: 'Thủ kho', cls: 'bg-teal-50 text-teal-700 border-teal-200' };
  };

  const getAccountSyncState = (acc) => {
    const checkSite = (list, isOnline) => {
      if (!isOnline && list.length === 0) return 'OFFLINE';
      const match = list.find((item) => item.username === acc.username);
      if (!match) return 'MISSING';
      if (match.is_active !== acc.is_active || match.role !== acc.role || match.branch_code !== acc.branch_code) {
        return 'STALE';
      }
      return 'SYNCED';
    };
    if (acc.branch_code === 'HN') {
      return { target: 'HN', state: checkSite(branchAccounts.hn, nodesStatus.hn) };
    }
    if (acc.branch_code === 'HCM') {
      return { target: 'HCM', state: checkSite(branchAccounts.hcm, nodesStatus.hcm) };
    }
    const sHn = checkSite(branchAccounts.hn, nodesStatus.hn);
    const sHcm = checkSite(branchAccounts.hcm, nodesStatus.hcm);
    if (sHn === 'SYNCED' && sHcm === 'SYNCED') return { target: 'HN & HCM', state: 'SYNCED' };
    if (sHn === 'OFFLINE' && sHcm === 'OFFLINE') return { target: 'HN & HCM', state: 'OFFLINE' };
    if (sHn === 'STALE' || sHcm === 'STALE') return { target: 'HN & HCM', state: 'STALE' };
    return { target: 'HN & HCM', state: 'SYNCED' };
  };

  const filteredAccounts = accounts.filter((a) => {
    const q = accSearch.trim().toLowerCase();
    const matchText = !q || a.username.toLowerCase().includes(q) || (a.full_name || '').toLowerCase().includes(q);
    const matchRole = accRoleFilter === 'ALL' || a.role === accRoleFilter;
    const matchBranch = accBranchFilter === 'ALL' || a.branch_code === accBranchFilter;
    const matchStatus =
      accStatusFilter === 'ALL' ||
      (accStatusFilter === 'ACTIVE' && a.is_active) ||
      (accStatusFilter === 'LOCKED' && !a.is_active);
    return matchText && matchRole && matchBranch && matchStatus;
  });

  const activeAccountCount = accounts.filter((a) => a.is_active).length;
  const lockedAccountCount = accounts.filter((a) => !a.is_active).length;
  const branchStaffMgrCount = accounts.filter((a) => a.role !== 'HQ_MANAGER').length;

  const navItems = [
    {
      id: 'overview',
      label: 'Tổng quan Toàn quốc',
      description: 'Báo cáo KPI tài chính, cân bằng tồn kho & trạng thái 3 Site',
      icon: 'fa-chart-pie',
    },
    {
      id: 'catalog',
      label: 'Ngành hàng & Sản phẩm',
      description: 'Quản lý DANH_MUC_SP, SAN_PHAM (Mã vạch, Giá vốn/Giá bán) & Tồn đầu kỳ',
      icon: 'fa-boxes-stacked',
      badge: lowStockItems.length,
      badgeColor: lowStockItems.length > 0 ? 'bg-rose-100 text-rose-700' : undefined
    },
    {
      id: 'transfers',
      label: 'Điều phối Saga & Yêu cầu',
      description: 'Phát lệnh điều chuyển liên kho & duyệt yêu cầu từ Chi nhánh',
      icon: 'fa-route',
      badge: pendingPullRequests.length + activeSagas.length,
    },
    {
      id: 'accounts',
      label: 'Tài khoản & Phân quyền',
      description: 'Quản lý bảng TAI_KHOAN (PBKDF2-SHA256) và nhân bản sang Chi nhánh',
      icon: 'fa-users-gear',
    },
    {
      id: 'cluster',
      label: 'Hạ tầng Cluster & 11 Bảng',
      description: 'Load Balancer, App Instances, DB Primary-Replica & Thống kê 11 Bảng',
      icon: 'fa-server',
    },
  ];

  const allOnline = nodesStatus.hq && nodesStatus.hn && nodesStatus.hcm;

  return (
    <AppShell
      brandTitle="TRỤ SỞ CHÍNH (HQ)"
      brandSubtitle="Site 1 • Trung tâm Điều phối"
      brandIcon="fa-building-columns"
      navItems={navItems}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      currentUser={currentUser}
      onLogout={handleLogout}
      headerExtra={
        <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border hidden md:inline-flex items-center gap-1.5 ${
          allOnline ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${allOnline ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
          {allOnline ? 'Cụm 3 Site Hoạt động' : 'Có Site Mất Kết nối'}
        </span>
      }
      sidebarFooter={
        <div className="text-[11px] text-slate-500 space-y-1">
          <div className="font-semibold text-slate-700">Cụm Site 1 (HQ :8000)</div>
          <div className="font-mono text-[10px]">LB-HQ-Central • Primary + Replica</div>
        </div>
      }
    >
      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                <span>Giá trị Tồn kho (Giá bán)</span>
                <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <i className="fa-solid fa-coins"></i>
                </span>
              </div>
              <div className="text-xl font-extrabold text-slate-900 mt-2 tabular-nums">
                {(totalSaleValue / 1000000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} Tr đ
              </div>
              <div className="text-[11px] text-slate-500 mt-1 tabular-nums">
                Giá vốn: {(totalCostValue / 1000000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} Tr đ
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                <span>Tổng Tồn Khả dụng</span>
                <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <i className="fa-solid fa-cubes"></i>
                </span>
              </div>
              <div className="text-xl font-extrabold text-emerald-700 mt-2 tabular-nums">
                {totalAvail.toLocaleString('vi-VN')} <span className="text-xs font-medium text-slate-500">đơn vị</span>
              </div>
              <div className="text-[11px] text-amber-600 mt-1 tabular-nums">
                Đang tạm giữ Saga: <strong>{totalRes}</strong> đơn vị
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                <span>Cảnh báo Tồn thấp</span>
                <span className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
                  <i className="fa-solid fa-triangle-exclamation"></i>
                </span>
              </div>
              <div className="text-xl font-extrabold text-rose-600 mt-2 tabular-nums">
                {lowStockItems.length} <span className="text-xs font-medium text-slate-500">/ {globalStock.length} SKU</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Dưới định mức tại HN hoặc HCM
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
                <span>Yêu cầu & Saga Đang chạy</span>
                <span className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                  <i className="fa-solid fa-truck-fast"></i>
                </span>
              </div>
              <div className="text-xl font-extrabold text-slate-900 mt-2 tabular-nums">
                {activeSagas.length} Saga <span className="text-xs font-medium text-indigo-600">/ {pendingPullRequests.length} xin hàng</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Tổng lịch sử điều phối: {transfers.length} đơn
              </div>
            </div>
          </div>

          <NodeStatusBanner nodesStatus={nodesStatus} />

          {/* Smart Rebalance Suggestions + Allocation Bars */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
                <i className="fa-solid fa-wand-magic-sparkles text-indigo-600"></i>
                Gợi ý Cân bằng Tồn kho Tự động
              </h3>
              {rebalanceSuggestions.length === 0 ? (
                <div className="p-6 text-center bg-slate-50 rounded-xl border border-slate-100 text-xs text-slate-500">
                  Phân bổ tồn kho giữa Hà Nội và TP.HCM hiện đang cân bằng tốt.
                </div>
              ) : (
                <div className="space-y-3">
                  {rebalanceSuggestions.map((s) => (
                    <div key={s.sku} className="p-3 rounded-xl bg-amber-50/70 border border-amber-200 flex items-center justify-between gap-3">
                      <div className="text-xs">
                        <div className="font-bold text-slate-900">{s.sku} - {s.name}</div>
                        <div className="text-[11px] text-slate-600 mt-0.5">
                          Kho <strong>{s.dest}</strong> chỉ còn <strong className="text-rose-600">{s.dstAvail}</strong>, trong khi <strong>{s.source}</strong> đang có <strong className="text-emerald-700">{s.srcAvail}</strong>.
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setTransferPrefill({ source: s.source, dest: s.dest, sku: s.sku, quantity: s.qty });
                          setActiveTab('transfers');
                        }}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold shrink-0"
                      >
                        Chuyển {s.qty} cái
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
                <i className="fa-solid fa-chart-bar text-sky-600"></i>
                Tỷ trọng Phân bổ Tồn kho HN vs HCM (TONG_HOP_TON_KHO)
              </h3>
              <div className="space-y-3">
                {globalStock.slice(0, 6).map((p) => {
                  const hn = p.branches?.HN?.available ?? 0;
                  const hcm = p.branches?.HCM?.available ?? 0;
                  const sum = hn + hcm || 1;
                  const hnPct = Math.round((hn / sum) * 100);
                  const hcmPct = 100 - hnPct;
                  return (
                    <div key={p.sku} className="text-xs">
                      <div className="flex justify-between mb-1">
                        <span className="font-semibold text-slate-800">
                          <span className="font-mono text-indigo-700">{p.sku}</span> • {p.product_name}
                        </span>
                        <span className="tabular-nums text-slate-600 font-medium">
                          HN: <strong className="text-sky-700">{hn}</strong> | HCM: <strong className="text-violet-700">{hcm}</strong>
                        </span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden flex">
                        <div style={{ width: `${hnPct}%` }} className="bg-sky-500 h-full"></div>
                        <div style={{ width: `${hcmPct}%` }} className="bg-violet-500 h-full"></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CATALOG & PRODUCTS */}
      {activeTab === 'catalog' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
              <i className="fa-solid fa-tags text-indigo-600"></i>
              Quản lý Ngành hàng (DANH_MUC_SP - Nhân bản sang HN & HCM)
            </h3>
            {catMsg && (
              <div className={`p-2.5 rounded-lg text-xs mb-3 border ${
                catMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
              }`}>
                {catMsg.text}
              </div>
            )}
            <div className="space-y-3.5">
              <form onSubmit={handleCreateCategory} className="grid grid-cols-1 sm:grid-cols-12 gap-2.5 text-xs">
                <input
                  type="text"
                  value={catName}
                  onChange={(e) => setCatName(e.target.value)}
                  placeholder="Tên ngành hàng mới..."
                  required
                  className="sm:col-span-4 w-full min-w-0 bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
                <input
                  type="text"
                  value={catDesc}
                  onChange={(e) => setCatDesc(e.target.value)}
                  placeholder="Mô tả ngắn..."
                  className="sm:col-span-6 w-full min-w-0 bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
                <button
                  type="submit"
                  className="sm:col-span-2 w-full px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-xs transition-colors whitespace-nowrap"
                >
                  Thêm & Đồng bộ
                </button>
              </form>
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
                  Hiện có ({categories.length}):
                </span>
                {categories.map((c) => (
                  <span key={c.category_id} className="px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-medium text-slate-700">
                    <strong className="text-indigo-700">#{c.category_id}</strong> {c.category_name}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <GlobalStockTable
            globalStock={globalStock}
            categories={categories}
            loading={loading}
            onRefresh={fetchHQData}
          />
        </div>
      )}

      {/* TAB 3: TRANSFERS & PULL REQUESTS */}
      {activeTab === 'transfers' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5">
              <TransferOrderForm
                products={globalStock}
                prefill={transferPrefill}
                onTransferCreated={fetchHQData}
              />
            </div>

            <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
                <i className="fa-solid fa-inbox text-indigo-600"></i>
                Yêu cầu Xin Điều Chuyển từ Chi Nhánh (Pull Requests)
                {pendingPullRequests.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold">
                    {pendingPullRequests.length} chờ duyệt
                  </span>
                )}
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                      <th className="py-2 px-3">Kho Xin</th>
                      <th className="py-2 px-3">Kho Xuất Đề xuất</th>
                      <th className="py-2 px-3">SKU / SL</th>
                      <th className="py-2 px-3">Lý do</th>
                      <th className="py-2 px-3 text-right">Phê duyệt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {transferRequests.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="py-8 text-center text-slate-400">
                          Chưa có yêu cầu xin điều chuyển hàng nào từ các chi nhánh.
                        </td>
                      </tr>
                    ) : (
                      transferRequests.map((r) => (
                        <tr key={r.request_id} className="hover:bg-slate-50">
                          <td className="py-2.5 px-3 font-bold text-indigo-700">{r.requesting_branch}</td>
                          <td className="py-2.5 px-3 font-semibold text-slate-700">{r.suggested_source_branch}</td>
                          <td className="py-2.5 px-3 font-mono">
                            <strong>{r.sku}</strong> x <strong className="text-slate-900">{r.quantity}</strong>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 max-w-[180px] truncate">{r.reason}</td>
                          <td className="py-2.5 px-3 text-right space-x-1.5">
                            {r.status === 'PENDING' ? (
                              <>
                                <button onClick={() => handleApproveRequest(r.request_id)} className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold">
                                  Duyệt & Chạy Saga
                                </button>
                                <button onClick={() => handleRejectRequest(r.request_id)} className="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-[11px] font-semibold">
                                  Từ chối
                                </button>
                              </>
                            ) : (
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                r.status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
                              }`}>
                                {r.status}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <SagaTimelineModal transfers={transfers} onRefresh={fetchHQData} />
        </div>
      )}

      {/* TAB 4: ACCOUNTS (TAI_KHOAN) */}
      {activeTab === 'accounts' && (
        <div className="space-y-6">
          {/* KPI Summary Strip */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Tổng tài khoản</div>
              <div className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">{accounts.length}</div>
              <div className="text-[11px] text-slate-400 mt-1">Đồng bộ bảng TAI_KHOAN (3 Site)</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Đang hoạt động</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1 tabular-nums">{activeAccountCount}</div>
              <div className="text-[11px] text-slate-400 mt-1">Được phép đăng nhập HQ / Chi nhánh</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Đang bị khóa</div>
              <div className="text-2xl font-bold text-rose-600 mt-1 tabular-nums">{lockedAccountCount}</div>
              <div className="text-[11px] text-slate-400 mt-1">Chặn đăng nhập cục bộ toàn cụm</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Nhân sự Chi nhánh</div>
              <div className="text-2xl font-bold text-indigo-700 mt-1 tabular-nums">{branchStaffMgrCount}</div>
              <div className="text-[11px] text-slate-400 mt-1">Trưởng kho & Thủ kho (HN, HCM)</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left Form: Create Account */}
            <div className="lg:col-span-4 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-2">
                <i className="fa-solid fa-user-plus text-indigo-600"></i>
                Cấp Tài khoản Mới (TAI_KHOAN)
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Mật khẩu được băm PBKDF2-SHA256 và nhân bản sang DB Chi nhánh để đăng nhập cục bộ ngay cả khi đứt mạng WAN.
              </p>
              {accMsg && (
                <div className={`p-2.5 rounded-lg text-xs mb-3 border flex items-start justify-between gap-2 ${
                  accMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
                }`}>
                  <span>{accMsg.text}</span>
                  <button type="button" onClick={() => setAccMsg(null)} className="text-current opacity-60 hover:opacity-100 shrink-0">
                    <i className="fa-solid fa-xmark"></i>
                  </button>
                </div>
              )}
              <form onSubmit={handleCreateAccount} className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Tên đăng nhập (*)</label>
                  <input type="text" value={accUsername} onChange={(e) => setAccUsername(e.target.value)} required placeholder="VD: staff_hn_2" className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 font-mono" />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Mật khẩu (*)</label>
                  <input type="password" value={accPassword} onChange={(e) => setAccPassword(e.target.value)} required placeholder="Nhập mật khẩu..." className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2" />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Họ và tên (*)</label>
                  <input type="text" value={accFullName} onChange={(e) => setAccFullName(e.target.value)} required placeholder="VD: Nguyễn Văn A" className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Vai trò</label>
                    <select value={accRole} onChange={(e) => setAccRole(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2">
                      <option value="BRANCH_STAFF">Thủ kho</option>
                      <option value="BRANCH_MANAGER">Trưởng kho</option>
                      <option value="HQ_MANAGER">Quản trị HQ</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Chi nhánh</label>
                    <select value={accBranch} onChange={(e) => setAccBranch(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2">
                      <option value="HN">Hà Nội (HN)</option>
                      <option value="HCM">TP.HCM (HCM)</option>
                      <option value="HQ">Trụ sở (HQ)</option>
                    </select>
                  </div>
                </div>
                <button type="submit" className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold transition-colors">
                  Tạo & Đồng bộ Tài khoản
                </button>
              </form>
            </div>

            {/* Right Table: Manage Accounts */}
            <div className="lg:col-span-8 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <i className="fa-solid fa-users text-indigo-600"></i>
                    Danh sách Tài khoản & Kiểm soát Truy cập (TAI_KHOAN)
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Quản lý khóa/mở khóa, sửa vai trò/mật khẩu, xóa tài khoản và đối soát đồng bộ xuống HN & HCM
                  </p>
                </div>
                <button
                  type="button"
                  onClick={fetchHQData}
                  className="px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700"
                >
                  <i className="fa-solid fa-rotate mr-1"></i> Làm mới
                </button>
              </div>

              {/* Filter & Search Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5 text-xs">
                <div className="sm:col-span-5 relative">
                  <i className="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400"></i>
                  <input
                    type="text"
                    value={accSearch}
                    onChange={(e) => setAccSearch(e.target.value)}
                    placeholder="Tìm theo username hoặc họ tên..."
                    className="w-full min-w-0 bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-2 focus:bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <select
                  value={accRoleFilter}
                  onChange={(e) => setAccRoleFilter(e.target.value)}
                  className="sm:col-span-3 w-full min-w-0 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2"
                >
                  <option value="ALL">Tất cả vai trò</option>
                  <option value="HQ_MANAGER">Quản trị HQ</option>
                  <option value="BRANCH_MANAGER">Trưởng kho</option>
                  <option value="BRANCH_STAFF">Thủ kho</option>
                </select>
                <select
                  value={accBranchFilter}
                  onChange={(e) => setAccBranchFilter(e.target.value)}
                  className="sm:col-span-2 w-full min-w-0 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2"
                >
                  <option value="ALL">Mọi Site</option>
                  <option value="HQ">HQ</option>
                  <option value="HN">HN</option>
                  <option value="HCM">HCM</option>
                </select>
                <select
                  value={accStatusFilter}
                  onChange={(e) => setAccStatusFilter(e.target.value)}
                  className="sm:col-span-2 w-full min-w-0 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2"
                >
                  <option value="ALL">Mọi trạng thái</option>
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="LOCKED">LOCKED</option>
                </select>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                      <th className="py-2.5 px-3">Tài khoản & Họ tên</th>
                      <th className="py-2.5 px-3">Vai trò & Site</th>
                      <th className="py-2.5 px-3 text-center">Đồng bộ Cụm</th>
                      <th className="py-2.5 px-3 text-center">Trạng thái</th>
                      <th className="py-2.5 px-3 text-right">Thao tác</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {filteredAccounts.map((a) => {
                      const rm = roleMeta(a.role);
                      const syncInfo = getAccountSyncState(a);
                      const isProtected = a.username === 'admin' || a.username === currentUser?.username;
                      const isBusy = accBusyUser === a.username;
                      return (
                        <tr key={a.account_id} className={`hover:bg-slate-50 ${!a.is_active ? 'bg-rose-50/30' : ''}`}>
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono font-bold text-indigo-700">@{a.username}</span>
                              {a.username === 'admin' && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 text-[9px] font-semibold uppercase">
                                  Root
                                </span>
                              )}
                            </div>
                            <div className="font-medium text-slate-700 mt-0.5">{a.full_name}</div>
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${rm.cls}`}>
                                {rm.label}
                              </span>
                              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px] font-bold">
                                {a.branch_code}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono mt-1">PBKDF2-SHA256</div>
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {syncInfo.state === 'SYNCED' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                                {syncInfo.target} OK
                              </span>
                            ) : syncInfo.state === 'OFFLINE' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 text-[10px] font-semibold">
                                {syncInfo.target} Offline
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-semibold">
                                Chờ đồng bộ ({syncInfo.target})
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {a.is_active ? (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
                                ACTIVE
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-bold">
                                LOCKED
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => openEditAccount(a)}
                                title="Sửa thông tin / Đổi vai trò / Đặt lại mật khẩu"
                                className="px-2 py-1 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-[11px] font-semibold disabled:opacity-50"
                              >
                                <i className="fa-solid fa-pen-to-square mr-1"></i>Sửa
                              </button>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => handleResyncAccount(a.username)}
                                title="Đồng bộ lại xuống HN & HCM"
                                className="px-2 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-[11px] font-semibold disabled:opacity-50"
                              >
                                <i className="fa-solid fa-arrows-rotate"></i>
                              </button>
                              {isProtected ? (
                                <span className="px-2 py-1 rounded-lg bg-slate-100 text-slate-400 border border-slate-200 text-[10px] font-semibold">
                                  Bảo vệ
                                </span>
                              ) : (
                                <>
                                  <button
                                    type="button"
                                    disabled={isBusy}
                                    onClick={() => handleToggleAccountLock(a)}
                                    title={a.is_active ? 'Khóa tài khoản' : 'Mở khóa tài khoản'}
                                    className={`px-2 py-1 rounded-lg border text-[11px] font-semibold disabled:opacity-50 ${
                                      a.is_active
                                        ? 'bg-amber-50 hover:bg-amber-100 text-amber-700 border-amber-200'
                                        : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border-emerald-200'
                                    }`}
                                  >
                                    <i className={`fa-solid ${a.is_active ? 'fa-lock' : 'fa-lock-open'} mr-1`}></i>
                                    {a.is_active ? 'Khóa' : 'Mở'}
                                  </button>
                                  <button
                                    type="button"
                                    disabled={isBusy}
                                    onClick={() => setConfirmDeleteUser(a)}
                                    title="Xóa tài khoản trên toàn cụm"
                                    className="px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-[11px] font-semibold disabled:opacity-50"
                                  >
                                    <i className="fa-solid fa-trash-can"></i>
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                    {filteredAccounts.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-slate-400 text-xs">
                          Không tìm thấy tài khoản nào khớp bộ lọc.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* RBAC Permissions Matrix Reference Card */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
              <i className="fa-solid fa-shield-halved text-indigo-600"></i>
              Ma trận Phân quyền RBAC theo Vai trò (Tài liệu Đối chiếu Quản trị)
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                    <th className="py-2 px-3">Nghiệp vụ Hệ thống</th>
                    <th className="py-2 px-3 text-center">Quản trị HQ (HQ_MANAGER)</th>
                    <th className="py-2 px-3 text-center">Trưởng kho (BRANCH_MANAGER)</th>
                    <th className="py-2 px-3 text-center">Thủ kho (BRANCH_STAFF)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {[
                    { feature: 'Quản lý Danh mục, Sản phẩm & Tài khoản (Khóa/Xóa)', hq: true, mgr: false, staff: false },
                    { feature: 'Khởi tạo Điều chuyển Saga & Duyệt Pull Request tại HQ', hq: true, mgr: false, staff: false },
                    { feature: 'Xác nhận / Từ chối kiện hàng Saga & Sửa ngưỡng Min/Max tại Kho', hq: true, mgr: true, staff: false },
                    { feature: 'Bán hàng (DON_HANG), Nhập/Xuất nội bộ, Kiểm kê & Xin hàng (Pull)', hq: false, mgr: true, staff: true },
                    { feature: 'Mô phỏng Ngắt mạng WAN & Xem hàng đợi Outbox cục bộ', hq: true, mgr: true, staff: true },
                  ].map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="py-2 px-3 font-medium text-slate-700">{row.feature}</td>
                      {[row.hq, row.mgr, row.staff].map((allowed, cIdx) => (
                        <td key={cIdx} className="py-2 px-3 text-center">
                          {allowed ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-semibold">
                              <i className="fa-solid fa-check"></i> Cho phép
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-400 border border-slate-200 text-[10px] font-semibold">
                              <i className="fa-solid fa-ban"></i> Chặn (403)
                            </span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Edit / Reset Password Modal */}
          {editingAccount && (
            <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
              <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-5 shadow-xl">
                <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-200">
                  <h4 className="text-sm font-bold text-slate-900">
                    Cập nhật Tài khoản <span className="font-mono text-indigo-700">@{editingAccount.username}</span>
                  </h4>
                  <button type="button" onClick={() => setEditingAccount(null)} className="text-slate-400 hover:text-slate-700">
                    <i className="fa-solid fa-xmark"></i>
                  </button>
                </div>
                <form onSubmit={handleSaveEditAccount} className="space-y-3 text-xs">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Họ và tên</label>
                    <input
                      type="text"
                      required
                      value={editForm.full_name}
                      onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Vai trò</label>
                      <select
                        value={editForm.role}
                        disabled={editingAccount.username === 'admin'}
                        onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 disabled:bg-slate-100"
                      >
                        <option value="BRANCH_STAFF">Thủ kho</option>
                        <option value="BRANCH_MANAGER">Trưởng kho</option>
                        <option value="HQ_MANAGER">Quản trị HQ</option>
                      </select>
                    </div>
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Chi nhánh (Site)</label>
                      <select
                        value={editForm.branch_code}
                        disabled={editingAccount.username === 'admin'}
                        onChange={(e) => setEditForm({ ...editForm, branch_code: e.target.value })}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 disabled:bg-slate-100"
                      >
                        <option value="HN">Hà Nội (HN)</option>
                        <option value="HCM">TP.HCM (HCM)</option>
                        <option value="HQ">Trụ sở (HQ)</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Đặt lại Mật khẩu mới (để trống nếu giữ nguyên)</label>
                    <input
                      type="password"
                      value={editForm.password}
                      onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                      placeholder="Nhập mật khẩu mới nếu cần đặt lại..."
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2"
                    />
                  </div>
                  {editingAccount.username !== 'admin' && editingAccount.username !== currentUser?.username && (
                    <label className="flex items-center gap-2 pt-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editForm.is_active}
                        onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                        className="rounded border-slate-300 text-indigo-600"
                      />
                      <span className="font-medium text-slate-700">Kích hoạt tài khoản (ACTIVE)</span>
                    </label>
                  )}
                  <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => setEditingAccount(null)}
                      className="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                    >
                      Hủy
                    </button>
                    <button
                      type="submit"
                      disabled={accBusyUser === editingAccount.username}
                      className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50"
                    >
                      Lưu & Đồng bộ 3 Site
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Delete Confirmation Modal */}
          {confirmDeleteUser && (
            <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
              <div className="bg-white border border-slate-200 rounded-2xl max-w-sm w-full p-5 shadow-xl space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center shrink-0">
                    <i className="fa-solid fa-triangle-exclamation"></i>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">Xác nhận xóa tài khoản</h4>
                    <p className="text-xs text-slate-600 mt-1">
                      Bạn có chắc muốn xóa tài khoản <strong className="font-mono text-rose-700">@{confirmDeleteUser.username}</strong> ({confirmDeleteUser.full_name})?
                      Lệnh xóa sẽ được đồng bộ sang DB của cả HN và HCM.
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 text-xs">
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteUser(null)}
                    className="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
                  >
                    Giữ lại
                  </button>
                  <button
                    type="button"
                    disabled={accBusyUser === confirmDeleteUser.username}
                    onClick={handleConfirmDeleteAccount}
                    className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold disabled:opacity-50"
                  >
                    Xác nhận Xóa
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: CLUSTER INFRA & 11 TABLES */}
      {activeTab === 'cluster' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Trạng thái Cụm 3 Site (Load Balancer + Multi-Instance + DB Replica)</h3>
              <p className="text-xs text-slate-500">Số liệu thực tế lấy từ /cluster/status & /schema-overview của cả 3 Node</p>
            </div>
            <button onClick={fetchInfraData} className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold">
              <i className="fa-solid fa-rotate mr-1"></i> Cập nhật Số liệu
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { key: 'hq', label: 'Site 1: Trung tâm HQ', data: clusterData.hq },
              { key: 'hn', label: 'Site 2: Kho Hà Nội', data: clusterData.hn },
              { key: 'hcm', label: 'Site 3: Kho TP.HCM', data: clusterData.hcm },
            ].map((site) => (
              <div key={site.key} className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3 text-xs">
                <div className="font-bold text-slate-900 flex items-center justify-between">
                  <span>{site.label}</span>
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {site.data?.cluster?.load_balancer || 'Offline'}
                  </span>
                </div>
                {site.data ? (
                  <>
                    <div className="space-y-1.5">
                      {site.data.cluster.instances.map((inst) => (
                        <div key={inst.instance_id} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                          <span className="font-mono font-semibold text-slate-700">{inst.instance_id}</span>
                          <span className="text-[11px] text-emerald-700 font-bold tabular-nums">{inst.requests_served} reqs</span>
                        </div>
                      ))}
                    </div>
                    <div className="pt-2 border-t border-slate-100 text-[11px] space-y-1">
                      <div className="flex justify-between">
                        <span className="text-slate-500">DB Primary:</span>
                        <span className="font-mono text-slate-800">{site.data.database.primary_db}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">DB Replica Dự phòng:</span>
                        <span className="font-mono text-emerald-700 font-semibold">{site.data.database.replica_db}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Số lần sao lưu nóng:</span>
                        <span className="font-bold tabular-nums text-slate-900">{site.data.database.replication_count} lần ({(site.data.database.replica_size_bytes / 1024).toFixed(1)} KB)</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-slate-400">Không kết nối được tới node.</p>
                )}
              </div>
            ))}
          </div>

          {/* DB Replica Failover Read Tester */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <div>
                <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <i className="fa-solid fa-database text-emerald-600"></i>
                  Kiểm chứng Đọc Dự phòng từ DB Replica (Site 1: db_hq_replica.db)
                </h4>
                <p className="text-xs text-slate-500">Truy vấn trực tiếp file DB Replica Dự phòng để xác minh dữ liệu nhân bản</p>
              </div>
              <button onClick={handleReadReplica} className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold">
                <i className="fa-solid fa-bolt mr-1.5"></i> Đọc thử từ DB Replica
              </button>
            </div>
            {replicaPreview && (
              <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2 text-[11px] font-mono text-slate-600">
                  <span>Nguồn: <strong className="text-emerald-700">{replicaPreview.source}</strong> ({replicaPreview.replica_db})</span>
                  <span>Đồng bộ cuối: {replicaPreview.last_replicated_at}</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 text-[11px] text-slate-500">
                        <th className="py-1.5 px-2">Chi nhánh</th>
                        <th className="py-1.5 px-2">SKU</th>
                        <th className="py-1.5 px-2 text-center">Tồn thực tế</th>
                        <th className="py-1.5 px-2 text-center">Giữ chỗ</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 font-mono text-[11px]">
                      {replicaPreview.rows.map((r, idx) => (
                        <tr key={idx}>
                          <td className="py-1.5 px-2 font-bold">{r.branch_code}</td>
                          <td className="py-1.5 px-2 text-indigo-700">{r.sku}</td>
                          <td className="py-1.5 px-2 text-center font-bold">{r.available_qty}</td>
                          <td className="py-1.5 px-2 text-center">{r.reserved_qty}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* 11-Table Overview across 3 Sites */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { title: 'Site 1: DB_HQ (Trung tâm)', data: schemaData.hq },
              { title: 'Site 2: DB_Branch_HN', data: schemaData.hn },
              { title: 'Site 3: DB_Branch_HCM', data: schemaData.hcm },
            ].map((s, idx) => (
              <div key={idx} className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs text-xs">
                <h4 className="font-bold text-slate-900 mb-2.5 pb-2 border-b border-slate-100">{s.title}</h4>
                {s.data?.tables ? (
                  <div className="space-y-1.5">
                    {Object.entries(s.data.tables).map(([tbl, cnt]) => (
                      <div key={tbl} className="flex items-center justify-between">
                        <span className="font-mono text-[11px] text-slate-600 truncate pr-2">{tbl}</span>
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-bold tabular-nums">{cnt}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400">Chưa có dữ liệu.</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}
