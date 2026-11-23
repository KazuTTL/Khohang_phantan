// frontend/src/pages/BranchDashboardPage.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from '../components/Router';
import AppShell from '../components/AppShell';
import LocalBranchPanel from '../components/LocalBranchPanel';
import IncomingTransfersTable from '../components/IncomingTransfersTable';

export default function BranchDashboardPage({ branchCode }) {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('inventory');
  const [inventory, setInventory] = useState([]);
  const [orders, setOrders] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [incomingCount, setIncomingCount] = useState(0);
  const [outgoingTransfers, setOutgoingTransfers] = useState([]);
  const [outboxEvents, setOutboxEvents] = useState([]);
  const [wanStatus, setWanStatus] = useState({ wan_online: true, pending_outbox_count: 0 });
  const [clusterInfo, setClusterInfo] = useState(null);
  const [schemaInfo, setSchemaInfo] = useState(null);
  const [replicaPreview, setReplicaPreview] = useState(null);

  // Multi-SKU Order Builder State
  const [custName, setCustName] = useState('');
  const [custPhone, setCustPhone] = useState('');
  const [orderLines, setOrderLines] = useState([{ sku: 'LAPTOP-DELL-01', quantity: 1 }]);
  const [orderMsg, setOrderMsg] = useState(null);
  const [submittingOrder, setSubmittingOrder] = useState(false);

  // Pull Transfer Request State
  const [reqSku, setReqSku] = useState('LAPTOP-DELL-01');
  const [reqQty, setReqQty] = useState(10);
  const [reqReason, setReqReason] = useState('Bổ sung tồn kho chi nhánh');
  const [reqMsg, setReqMsg] = useState(null);

  // Expanded Transaction Detail
  const [selectedTx, setSelectedTx] = useState(null);

  const isHN = branchCode === 'HN';
  const branchUrl = isHN ? HN_URL : HCM_URL;
  const branchName = isHN ? 'Kho Hà Nội (HN)' : 'Kho TP.HCM (HCM)';
  const branchPort = isHN ? 8001 : 8002;
  const otherBranch = isHN ? 'HCM' : 'HN';

  // RBAC Route Guard
  const isAllowedBranch = currentUser?.role === 'HQ_MANAGER' || currentUser?.branch === branchCode;

  const fetchBranchAll = async () => {
    try {
      const [inv, inc, outg, ords, txs, obx, wan] = await Promise.all([
        api.getLocalInventory(branchUrl).catch(() => []),
        api.getIncomingTransfers(branchUrl).catch(() => []),
        api.getOutgoingTransfers(branchUrl).catch(() => []),
        api.getOrders(branchUrl).catch(() => []),
        api.getTransactions(branchUrl).catch(() => []),
        api.getOutbox(branchUrl).catch(() => []),
        api.getWanStatus(branchUrl).catch(() => ({ wan_online: true, pending_outbox_count: 0 })),
      ]);
      setInventory(inv);
      setIncomingCount(inc.length);
      setOutgoingTransfers(outg);
      setOrders(ords);
      setTransactions(txs);
      setOutboxEvents(obx);
      setWanStatus(wan);
      if (inv.length > 0 && !inv.some((i) => i.sku === reqSku)) {
        setReqSku(inv[0].sku);
      }
    } catch (err) {
      console.error('Lỗi tải dữ liệu chi nhánh:', err);
    }
  };

  const fetchInfraInfo = async () => {
    try {
      const [cInfo, sInfo] = await Promise.all([
        api.getBranchClusterStatus(branchUrl).catch(() => null),
        api.getBranchSchemaOverview(branchUrl).catch(() => null),
      ]);
      setClusterInfo(cInfo);
      setSchemaInfo(sInfo);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (!isAllowedBranch) return;
    fetchBranchAll();
    fetchInfraInfo();
    const timer = setInterval(fetchBranchAll, 3000);
    return () => clearInterval(timer);
  }, [branchCode, isAllowedBranch]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleToggleWan = async () => {
    try {
      const res = await api.toggleWan(branchUrl, !wanStatus.wan_online);
      setWanStatus({
        wan_online: res.wan_online,
        pending_outbox_count: res.pending_outbox_count
      });
      fetchBranchAll();
    } catch (err) {
      alert(err.message);
    }
  };

  // Multi-SKU Order handlers
  const handleAddOrderLine = () => {
    const defaultSku = inventory[0]?.sku || 'LAPTOP-DELL-01';
    setOrderLines([...orderLines, { sku: defaultSku, quantity: 1 }]);
  };

  const handleRemoveOrderLine = (idx) => {
    if (orderLines.length <= 1) return;
    setOrderLines(orderLines.filter((_, i) => i !== idx));
  };

  const handleOrderLineChange = (idx, field, value) => {
    const updated = [...orderLines];
    updated[idx] = { ...updated[idx], [field]: value };
    setOrderLines(updated);
  };

  const estimatedOrderTotal = orderLines.reduce((sum, line) => {
    const prod = inventory.find((i) => i.sku === line.sku);
    return sum + (prod?.price || 0) * (parseInt(line.quantity, 10) || 0);
  }, 0);

  const handleCreateOrder = async (e) => {
    e.preventDefault();
    setSubmittingOrder(true);
    setOrderMsg(null);
    try {
      const res = await api.createOrder(branchUrl, {
        customer_name: custName.trim(),
        customer_phone: custPhone.trim() || undefined,
        items: orderLines.map((l) => ({
          sku: l.sku,
          quantity: parseInt(l.quantity, 10) || 1
        }))
      });
      setOrderMsg({
        type: 'success',
        text: `Đã tạo đơn hàng ${res.order_id.slice(0, 8)}... (${res.total_amount.toLocaleString('vi-VN')} đ) và sinh phiếu xuất ${res.receipt_code}.`
      });
      setCustName('');
      setCustPhone('');
      setOrderLines([{ sku: inventory[0]?.sku || 'LAPTOP-DELL-01', quantity: 1 }]);
      fetchBranchAll();
    } catch (err) {
      setOrderMsg({ type: 'error', text: err.message });
    } finally {
      setSubmittingOrder(false);
    }
  };

  const handleSendPullRequest = async (e) => {
    e.preventDefault();
    setReqMsg(null);
    try {
      const res = await api.createTransferRequest({
        requesting_branch: branchCode,
        suggested_source_branch: otherBranch,
        sku: reqSku,
        quantity: parseInt(reqQty, 10),
        reason: reqReason.trim()
      });
      setReqMsg({
        type: 'success',
        text: `Đã gửi yêu cầu xin ${res.quantity} ${res.sku} từ ${res.suggested_source_branch} lên Trụ sở HQ (Mã: ${res.request_id.slice(0, 8)}...).`
      });
    } catch (err) {
      setReqMsg({ type: 'error', text: err.message });
    }
  };

  const handleReadReplica = async () => {
    try {
      const res = await api.getBranchReplicaPreview(branchUrl);
      setReplicaPreview(res);
    } catch (err) {
      alert(err.message);
    }
  };

  // RBAC 403 Guard View
  if (!isAllowedBranch) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center p-4">
        <div className="max-w-md w-full bg-white border border-rose-200 rounded-2xl p-8 text-center shadow-lg">
          <div className="w-14 h-14 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center mx-auto mb-4">
            <i className="fa-solid fa-ban text-rose-600 text-2xl"></i>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">403 Forbidden - Quyền truy cập bị từ chối</h2>
          <p className="text-xs text-slate-600 mb-6 leading-relaxed">
            Tài khoản <span className="font-mono text-indigo-700 font-semibold">@{currentUser?.username}</span> thuộc chi nhánh <strong>{currentUser?.branch}</strong>. Bạn không có quyền truy cập vào dữ liệu của <strong>{branchName}</strong>.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 justify-center">
            <button
              onClick={() => {
                if (currentUser?.branch === 'HN') navigate('/branch/hn');
                else if (currentUser?.branch === 'HCM') navigate('/branch/hcm');
                else navigate('/login');
              }}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold"
            >
              Quay về Chi nhánh của bạn
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </div>
    );
  }

  const totalLocalAvail = inventory.reduce((s, i) => s + (i.available_qty || 0), 0);
  const totalLocalRes = inventory.reduce((s, i) => s + (i.reserved_qty || 0), 0);
  const lowCount = inventory.filter((i) => i.is_low_stock).length;

  const navItems = [
    {
      id: 'inventory',
      label: 'Tồn kho & Xuất/Nhập',
      description: `Vận hành cục bộ TON_KHO_${branchCode}, kiểm kê thực tế & định mức`,
      icon: 'fa-warehouse',
      badge: lowCount,
      badgeColor: lowCount > 0 ? 'bg-rose-100 text-rose-700' : undefined
    },
    {
      id: 'orders',
      label: 'Đơn hàng Chi nhánh',
      description: 'Tạo đơn hàng nhiều mặt hàng (DON_HANG & CHI_TIET_DON_HANG)',
      icon: 'fa-cart-shopping',
      badge: orders.length
    },
    {
      id: 'transactions',
      label: 'Phiếu Giao dịch Kho',
      description: 'Tra cứu GIAO_DICH_KHO & CHI_TIET_GIAO_DICH (ton_sau_giao_dich)',
      icon: 'fa-file-invoice',
    },
    {
      id: 'transfers',
      label: 'Điều chuyển Liên kho',
      description: 'Kiện hàng Chờ Nhập, Kiện hàng Xuất Đi & Xin điều chuyển hàng',
      icon: 'fa-truck-fast',
      badge: incomingCount,
      badgeColor: incomingCount > 0 ? 'bg-amber-100 text-amber-800' : undefined
    },
    {
      id: 'outbox',
      label: 'Outbox & Hạ tầng Site',
      description: 'Theo dõi SU_KIEN_DONG_BO, thử nghiệm đứt mạng WAN & DB Replica',
      icon: 'fa-network-wired',
      badge: wanStatus.pending_outbox_count,
      badgeColor: wanStatus.pending_outbox_count > 0 ? 'bg-rose-100 text-rose-700' : undefined
    },
  ];

  return (
    <AppShell
      brandTitle={branchName.toUpperCase()}
      brandSubtitle={`Site ${isHN ? '2' : '3'} • Cổng :${branchPort}`}
      brandIcon="fa-warehouse"
      navItems={navItems}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      currentUser={currentUser}
      onLogout={handleLogout}
      headerExtra={
        <button
          type="button"
          onClick={handleToggleWan}
          title="Bấm để mô phỏng ngắt hoặc khôi phục đường truyền WAN tới Trung tâm HQ"
          className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-all flex items-center gap-1.5 ${
            wanStatus.wan_online
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
              : 'bg-rose-50 text-rose-700 border-rose-300 hover:bg-rose-100 animate-pulse'
          }`}
        >
          <i className={`fa-solid ${wanStatus.wan_online ? 'fa-wifi' : 'fa-plane-slash'}`}></i>
          <span>{wanStatus.wan_online ? 'WAN: Kết nối HQ' : `WAN: Đang Ngắt (${wanStatus.pending_outbox_count} chờ)`}</span>
        </button>
      }
      sidebarFooter={
        <div className="text-[11px] text-slate-500 space-y-1">
          <div className="font-semibold text-slate-700">Phân mảnh TON_KHO_{branchCode}</div>
          <div className="font-mono text-[10px]">
            {wanStatus.wan_online ? 'Outbox Sync: Active' : 'Offline Autonomy Mode'}
          </div>
        </div>
      }
    >
      {/* WAN Offline Banner */}
      {!wanStatus.wan_online && (
        <div className="mb-5 p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <i className="fa-solid fa-triangle-exclamation text-amber-600 text-base"></i>
            <div>
              <strong>Chế độ Tự trị Cục bộ (Mất kết nối WAN tới Trung tâm HQ):</strong> Chi nhánh {branchCode} vẫn tạo Đơn hàng và Xuất/Nhập kho bình thường. Mọi biến động đang lưu an toàn trong hàng đợi Outbox ({wanStatus.pending_outbox_count} sự kiện).
            </div>
          </div>
          <button
            onClick={handleToggleWan}
            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs shrink-0"
          >
            Khôi phục mạng WAN
          </button>
        </div>
      )}

      {/* TAB 1: INVENTORY & LOCAL OPS */}
      {activeTab === 'inventory' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Danh mục SKU tại Kho</div>
              <div className="text-2xl font-extrabold text-slate-900 mt-1 tabular-nums">{inventory.length}</div>
              <div className="text-[11px] text-slate-400 mt-1">Phân mảnh ngang {branchCode}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Tổng Tồn Khả dụng</div>
              <div className="text-2xl font-extrabold text-emerald-700 mt-1 tabular-nums">{totalLocalAvail.toLocaleString('vi-VN')}</div>
              <div className="text-[11px] text-slate-400 mt-1">Sẵn sàng xuất bán</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Đang Tạm giữ (Saga)</div>
              <div className="text-2xl font-extrabold text-amber-600 mt-1 tabular-nums">{totalLocalRes.toLocaleString('vi-VN')}</div>
              <div className="text-[11px] text-slate-400 mt-1">Chờ kho đích duyệt nhận</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
              <div className="text-xs text-slate-500 font-medium">Cảnh báo Tồn thấp</div>
              <div className={`text-2xl font-extrabold mt-1 tabular-nums ${lowCount > 0 ? 'text-rose-600' : 'text-emerald-700'}`}>{lowCount}</div>
              <div className="text-[11px] text-slate-400 mt-1">Mặt hàng dưới định mức Min</div>
            </div>
          </div>

          <LocalBranchPanel currentBranch={branchCode} currentUser={currentUser} onActionSuccess={fetchBranchAll} />
        </div>
      )}

      {/* TAB 2: MULTI-SKU CUSTOMER ORDERS (DON_HANG & CHI_TIET_DON_HANG) */}
      {activeTab === 'orders' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
              <i className="fa-solid fa-cart-plus text-indigo-600"></i>
              Lập Đơn hàng Khách hàng (DON_HANG)
            </h3>
            {orderMsg && (
              <div className={`p-3 rounded-lg text-xs mb-4 border ${
                orderMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
              }`}>
                {orderMsg.text}
              </div>
            )}
            <form onSubmit={handleCreateOrder} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Khách hàng / Đại lý (*)</label>
                  <input type="text" value={custName} onChange={(e) => setCustName(e.target.value)} required placeholder="VD: Công ty TNHH An Phát" className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2" />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Số điện thoại</label>
                  <input type="text" value={custPhone} onChange={(e) => setCustPhone(e.target.value)} placeholder="VD: 0912345678" className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2" />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="font-semibold text-slate-700">Danh sách Mặt hàng (CHI_TIET_DON_HANG)</label>
                  <button type="button" onClick={handleAddOrderLine} className="text-indigo-600 hover:text-indigo-800 font-semibold text-[11px]">
                    <i className="fa-solid fa-plus mr-1"></i> Thêm dòng
                  </button>
                </div>
                <div className="space-y-2">
                  {orderLines.map((line, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <select
                        value={line.sku}
                        onChange={(e) => handleOrderLineChange(idx, 'sku', e.target.value)}
                        className="flex-1 bg-white border border-slate-300 rounded-lg px-2.5 py-2 font-mono text-xs"
                      >
                        {inventory.map((item) => (
                          <option key={item.sku} value={item.sku}>
                            {item.sku} ({item.available_qty} {item.unit}) - {(item.price || 0).toLocaleString('vi-VN')}đ
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min="1"
                        value={line.quantity}
                        onChange={(e) => handleOrderLineChange(idx, 'quantity', e.target.value)}
                        className="w-20 bg-white border border-slate-300 rounded-lg px-2.5 py-2 font-bold tabular-nums"
                        required
                      />
                      {orderLines.length > 1 && (
                        <button type="button" onClick={() => handleRemoveOrderLine(idx)} className="p-2 text-rose-500 hover:bg-rose-50 rounded-lg">
                          <i className="fa-solid fa-trash"></i>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
                <span className="text-slate-600 font-medium">Tổng tiền dự kiến:</span>
                <span className="text-base font-extrabold text-indigo-700 tabular-nums">
                  {estimatedOrderTotal.toLocaleString('vi-VN')} đ
                </span>
              </div>

              <button type="submit" disabled={submittingOrder} className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold">
                {submittingOrder ? 'Đang xử lý...' : 'Tạo Đơn Hàng & Xuất Kho'}
              </button>
            </form>
          </div>

          <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <i className="fa-solid fa-receipt text-indigo-600"></i>
              Danh sách Đơn hàng tại {branchCode} (DON_HANG)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                    <th className="py-2.5 px-3">Mã Đơn</th>
                    <th className="py-2.5 px-3">Khách hàng</th>
                    <th className="py-2.5 px-3">Chi tiết Sản phẩm</th>
                    <th className="py-2.5 px-3 text-right">Tổng tiền</th>
                    <th className="py-2.5 px-3 text-center">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {orders.length === 0 ? (
                    <tr><td colSpan="5" className="py-8 text-center text-slate-400">Chưa có đơn hàng nào tại kho {branchCode}.</td></tr>
                  ) : (
                    orders.map((o) => (
                      <tr key={o.order_id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-mono text-indigo-700 font-semibold">{o.order_id.slice(0, 8)}...</td>
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-slate-900">{o.customer_name}</div>
                          {o.customer_phone && <div className="text-[10px] text-slate-400">{o.customer_phone}</div>}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="space-y-0.5">
                            {o.items.map((it) => (
                              <div key={it.id} className="font-mono text-[11px] text-slate-700">
                                {it.sku} x <strong>{it.quantity}</strong>
                              </div>
                            ))}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold tabular-nums text-slate-900">
                          {o.total_amount.toLocaleString('vi-VN')} đ
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
                            {o.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: WAREHOUSE TRANSACTIONS (GIAO_DICH_KHO & CHI_TIET_GIAO_DICH) */}
      {activeTab === 'transactions' && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <i className="fa-solid fa-file-invoice text-indigo-600"></i>
                Phiếu Giao dịch Kho & Chi tiết Biến động (GIAO_DICH_KHO / CHI_TIET_GIAO_DICH)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">Bấm vào từng phiếu để kiểm tra tồn kho chụp lại ngay sau giao dịch (ton_sau_giao_dich)</p>
            </div>
            <button onClick={fetchBranchAll} className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-medium text-slate-700">
              <i className="fa-solid fa-rotate mr-1"></i> Làm mới
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                  <th className="py-2.5 px-3">Mã Phiếu</th>
                  <th className="py-2.5 px-3">Loại Nghiệp vụ</th>
                  <th className="py-2.5 px-3">Chi tiết Biến động</th>
                  <th className="py-2.5 px-3">Ghi chú</th>
                  <th className="py-2.5 px-3 text-center">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {transactions.length === 0 ? (
                  <tr><td colSpan="5" className="py-8 text-center text-slate-400">Chưa có phiếu giao dịch nào.</td></tr>
                ) : (
                  transactions.map((t) => (
                    <tr
                      key={t.transaction_id}
                      onClick={() => setSelectedTx(t)}
                      className={`cursor-pointer ${selectedTx?.transaction_id === t.transaction_id ? 'bg-indigo-50/60' : 'hover:bg-slate-50'}`}
                    >
                      <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">{t.receipt_code}</td>
                      <td className="py-2.5 px-3 font-semibold text-slate-800">{t.transaction_type}</td>
                      <td className="py-2.5 px-3">
                        {t.details.map((d) => (
                          <div key={d.detail_id} className="font-mono text-[11px]">
                            {d.sku}:{' '}
                            <strong className={d.quantity >= 0 ? 'text-emerald-700' : 'text-rose-600'}>
                              {d.quantity >= 0 ? `+${d.quantity}` : d.quantity}
                            </strong>{' '}
                            <span className="text-slate-400">(Tồn sau GD: {d.post_transaction_balance})</span>
                          </div>
                        ))}
                      </td>
                      <td className="py-2.5 px-3 text-slate-500 max-w-xs truncate">{t.note || '-'}</td>
                      <td className="py-2.5 px-3 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          t.status === 'HOAN_THANH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          t.status === 'SAGA_ROLLBACK' ? 'bg-rose-50 text-rose-700 border-rose-200' :
                          'bg-amber-50 text-amber-700 border-amber-200'
                        }`}>
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: INCOMING + OUTGOING + PULL REQUESTS */}
      {activeTab === 'transfers' && (
        <div className="space-y-6">
          <IncomingTransfersTable currentBranch={branchCode} currentUser={currentUser} onActionSuccess={fetchBranchAll} />

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Kiện hàng Xuất Đi (Outgoing Transfers) */}
            <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
                <i className="fa-solid fa-paper-plane text-sky-600"></i>
                Kiện hàng Xuất Điều Chuyển từ {branchCode} (Outgoing Transfers)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                      <th className="py-2 px-3">Mã Phiếu</th>
                      <th className="py-2 px-3">Kho Đích</th>
                      <th className="py-2 px-3">SKU</th>
                      <th className="py-2 px-3 text-center">SL</th>
                      <th className="py-2 px-3 text-center">Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {outgoingTransfers.length === 0 ? (
                      <tr><td colSpan="5" className="py-6 text-center text-slate-400">Chưa có kiện hàng nào xuất điều chuyển từ {branchCode}.</td></tr>
                    ) : (
                      outgoingTransfers.map((o) => (
                        <tr key={o.receipt_code} className="hover:bg-slate-50">
                          <td className="py-2 px-3 font-mono font-semibold text-slate-700">{o.receipt_code}</td>
                          <td className="py-2 px-3 font-bold text-indigo-700">{o.dest_branch || '-'}</td>
                          <td className="py-2 px-3 font-mono">{o.sku}</td>
                          <td className="py-2 px-3 text-center font-bold tabular-nums">{o.quantity}</td>
                          <td className="py-2 px-3 text-center">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              o.status === 'HOAN_THANH' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                              o.status === 'SAGA_ROLLBACK' ? 'bg-rose-50 text-rose-700 border-rose-200' :
                              'bg-amber-50 text-amber-700 border-amber-200'
                            }`}>
                              {o.status === 'CHO_XU_LY' ? 'Đang chờ kho đích' : o.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Form Gửi Yêu cầu Xin hàng lên HQ */}
            <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
                <i className="fa-solid fa-hand-holding-medical text-indigo-600"></i>
                Gửi Yêu cầu Xin Điều Chuyển lên HQ
              </h3>
              {reqMsg && (
                <div className={`p-2.5 rounded-lg text-xs mb-3 border ${
                  reqMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
                }`}>
                  {reqMsg.text}
                </div>
              )}
              <form onSubmit={handleSendPullRequest} className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Mặt hàng cần bổ sung (Xin từ {otherBranch})</label>
                  <select value={reqSku} onChange={(e) => setReqSku(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 font-mono">
                    {inventory.map((i) => (
                      <option key={i.sku} value={i.sku}>{i.sku} - {i.product_name} (Hiện còn: {i.available_qty})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Số lượng đề nghị chuyển</label>
                  <input type="number" min="1" value={reqQty} onChange={(e) => setReqQty(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 font-bold tabular-nums" />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Lý do đề nghị</label>
                  <input type="text" value={reqReason} onChange={(e) => setReqReason(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2" />
                </div>
                <button type="submit" className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold">
                  Gửi Đề Nghị Lên Trụ Sở HQ
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: OUTBOX & SITE INFRA */}
      {activeTab === 'outbox' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <i className="fa-solid fa-envelope-open-text text-indigo-600"></i>
                  Hàng đợi Outbox Đồng bộ (SU_KIEN_DONG_BO)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Khi ngắt kết nối WAN, sự kiện được giữ lại ở trạng thái FAILED (tăng retry_count) và tự động gửi đi khi có mạng lại
                </p>
              </div>
              <button
                onClick={handleToggleWan}
                className={`px-3.5 py-2 rounded-lg text-xs font-semibold ${
                  wanStatus.wan_online ? 'bg-rose-600 hover:bg-rose-700 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                }`}
              >
                {wanStatus.wan_online ? 'Thử Ngắt Mạng WAN' : 'Khôi Phục Mạng WAN'}
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                    <th className="py-2.5 px-3">Event ID</th>
                    <th className="py-2.5 px-3">Loại Sự kiện</th>
                    <th className="py-2.5 px-3">Routing Key</th>
                    <th className="py-2.5 px-3 text-center">Trạng thái Gửi</th>
                    <th className="py-2.5 px-3 text-center">Số lần thử (Retry)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs font-mono">
                  {outboxEvents.length === 0 ? (
                    <tr><td colSpan="5" className="py-8 text-center text-slate-400 font-sans">Hàng đợi Outbox đang trống.</td></tr>
                  ) : (
                    outboxEvents.map((e) => (
                      <tr key={e.event_id} className="hover:bg-slate-50">
                        <td className="py-2 px-3 text-slate-500">{e.event_id.slice(0, 8)}...</td>
                        <td className="py-2 px-3 font-semibold text-indigo-700">{e.event_type}</td>
                        <td className="py-2 px-3 text-slate-700">{e.routing_key}</td>
                        <td className="py-2 px-3 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                            e.delivery_status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                            e.delivery_status === 'FAILED' ? 'bg-rose-50 text-rose-700 border-rose-200' :
                            'bg-amber-50 text-amber-700 border-amber-200'
                          }`}>
                            {e.delivery_status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-center font-bold tabular-nums text-slate-700">{e.retry_count}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Cluster & DB Replica Preview */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-5 shadow-xs text-xs space-y-3">
              <h4 className="text-sm font-bold text-slate-900">Hạ tầng Cụm {branchCode} & Bảng Cục bộ</h4>
              {clusterInfo && (
                <div className="space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-500">Load Balancer: {clusterInfo.cluster.load_balancer}</div>
                  {clusterInfo.cluster.instances.map((inst) => (
                    <div key={inst.instance_id} className="flex justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="font-mono font-semibold">{inst.instance_id}</span>
                      <span className="font-bold text-emerald-700 tabular-nums">{inst.requests_served} reqs</span>
                    </div>
                  ))}
                  <div className="pt-2 text-[11px] text-slate-600">
                    DB Replica: <strong className="font-mono text-emerald-700">{clusterInfo.database.replica_db}</strong> ({clusterInfo.database.replication_count} backups)
                  </div>
                </div>
              )}
              {schemaInfo?.tables && (
                <div className="pt-3 border-t border-slate-100 space-y-1">
                  {Object.entries(schemaInfo.tables).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-[11px]">
                      <span className="font-mono text-slate-600 truncate pr-2">{k}</span>
                      <span className="font-bold text-slate-900 tabular-nums">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">Kiểm chứng Đọc DB Replica Dự phòng ({branchCode})</h4>
                  <p className="text-xs text-slate-500">Đọc trực tiếp bảng Local_Inventory từ file *_replica.db</p>
                </div>
                <button onClick={handleReadReplica} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold">
                  Đọc từ DB Replica
                </button>
              </div>
              {replicaPreview && (
                <div className="overflow-x-auto border border-slate-200 rounded-lg">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-[11px]">
                        <th className="py-2 px-3">SKU</th>
                        <th className="py-2 px-3 text-center">Shard Key</th>
                        <th className="py-2 px-3 text-center">Khả dụng</th>
                        <th className="py-2 px-3 text-center">Version</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {replicaPreview.rows.map((r, i) => (
                        <tr key={i}>
                          <td className="py-2 px-3 text-indigo-700 font-bold">{r.sku}</td>
                          <td className="py-2 px-3 text-center">{r.branch_code}</td>
                          <td className="py-2 px-3 text-center font-bold">{r.available_qty}</td>
                          <td className="py-2 px-3 text-center">v{r.version}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
