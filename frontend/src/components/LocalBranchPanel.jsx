// frontend/src/components/LocalBranchPanel.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function LocalBranchPanel({ currentBranch, currentUser, onActionSuccess }) {
  const [inventory, setInventory] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [activeTab, setActiveTab] = useState('adjust');

  // Form Nhập / Xuất
  const [selectedSku, setSelectedSku] = useState('LAPTOP-DELL-01');
  const [changeType, setChangeType] = useState('LOCAL_OUT');
  const [quantity, setQuantity] = useState(5);
  const [partnerName, setPartnerName] = useState('');
  const [note, setNote] = useState('');

  // Form Kiểm kê
  const [auditQty, setAuditQty] = useState(0);
  const [auditNote, setAuditNote] = useState('Kiểm kê định kỳ cuối ngày');

  // Form Ngưỡng Min/Max (Chỉ Manager)
  const [thMin, setThMin] = useState(10);
  const [thMax, setThMax] = useState(200);

  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const isStaffOnly = currentUser?.role === 'BRANCH_STAFF';

  const fetchBranchData = async () => {
    try {
      const inv = await api.getLocalInventory(branchUrl);
      setInventory(inv);
      if (inv.length > 0 && !inv.some((i) => i.sku === selectedSku)) {
        setSelectedSku(inv[0].sku);
      }
      const logs = await api.getLedger(branchUrl);
      setLedger(logs);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchBranchData();
  }, [currentBranch]);

  const handleAdjust = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.adjustStock(branchUrl, {
        sku: selectedSku,
        change_type: changeType,
        quantity: parseInt(quantity, 10),
        partner_name: partnerName.trim() || undefined,
        note: note.trim() || undefined
      });
      setMsg({ type: 'success', text: `${res.message} (Mã phiếu: ${res.receipt_code || res.reference_id})` });
      setPartnerName('');
      setNote('');
      fetchBranchData();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Thao tác thất bại' });
    } finally {
      setLoading(false);
    }
  };

  const handleAudit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.auditStock(branchUrl, {
        sku: selectedSku,
        actual_qty: parseInt(auditQty, 10),
        note: auditNote.trim()
      });
      setMsg({
        type: 'success',
        text: `${res.message} (Phiếu: ${res.receipt_code || res.reference_id})`
      });
      fetchBranchData();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Kiểm kê thất bại' });
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateThresholds = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.updateThresholds(branchUrl, selectedSku, {
        min_threshold: parseInt(thMin, 10),
        max_threshold: parseInt(thMax, 10)
      });
      setMsg({ type: 'success', text: res.message });
      fetchBranchData();
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Không thể cập nhật định mức' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Tác vụ Cục bộ */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
          <div className="flex items-center gap-2 mb-4 border-b border-slate-200 pb-2.5 flex-wrap">
            <button
              onClick={() => setActiveTab('adjust')}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'adjust' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <i className="fa-solid fa-boxes-packing mr-1.5"></i> Nhập / Xuất Lẻ
            </button>
            <button
              onClick={() => {
                setActiveTab('audit');
                const found = inventory.find((i) => i.sku === selectedSku);
                if (found) setAuditQty(found.available_qty);
              }}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'audit' ? 'bg-sky-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <i className="fa-solid fa-clipboard-check mr-1.5"></i> Kiểm kê Thực tế
            </button>
            <button
              onClick={() => {
                setActiveTab('threshold');
                const found = inventory.find((i) => i.sku === selectedSku);
                if (found) {
                  setThMin(found.min_threshold ?? 10);
                  setThMax(found.max_threshold ?? 200);
                }
              }}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'threshold' ? 'bg-amber-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <i className="fa-solid fa-sliders mr-1.5"></i> Định mức
            </button>
          </div>

          {msg && (
            <div className={`p-3 rounded-lg text-xs mb-4 border ${
              msg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
            }`}>
              {msg.text}
            </div>
          )}

          {activeTab === 'adjust' && (
            <form onSubmit={handleAdjust} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mặt hàng (SKU)</label>
                <select
                  value={selectedSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600"
                >
                  {inventory.map((i) => (
                    <option key={i.sku} value={i.sku}>
                      {i.sku} - {i.product_name} (Tồn: {i.available_qty})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Loại Nghiệp vụ</label>
                  <select
                    value={changeType}
                    onChange={(e) => setChangeType(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 focus:outline-none focus:border-indigo-600"
                  >
                    <option value="LOCAL_OUT">Xuất bán (-)</option>
                    <option value="LOCAL_IN">Nhập NCC (+)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Số lượng</label>
                  <input
                    type="number"
                    min="1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-bold tabular-nums"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  {changeType === 'LOCAL_IN' ? 'Nhà cung cấp (NCC)' : 'Khách hàng / Đại lý'}
                </label>
                <input
                  type="text"
                  value={partnerName}
                  onChange={(e) => setPartnerName(e.target.value)}
                  placeholder={changeType === 'LOCAL_IN' ? 'VD: Công ty Phân phối Synnex FPT' : 'VD: Đại lý Bán lẻ Miền Bắc'}
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Ghi chú / Số chứng từ</label>
                <input
                  type="text"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="VD: Hóa đơn GTGT #HD-2026"
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className={`w-full py-2.5 rounded-xl font-semibold text-white transition-all shadow-xs ${
                  changeType === 'LOCAL_OUT' ? 'bg-amber-600 hover:bg-amber-700' : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                {loading ? 'Đang xử lý...' : changeType === 'LOCAL_OUT' ? 'Xác nhận Xuất Kho Cục Bộ' : 'Xác nhận Nhập Kho NCC'}
              </button>
            </form>
          )}

          {activeTab === 'audit' && (
            <form onSubmit={handleAudit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mặt hàng Kiểm kê</label>
                <select
                  value={selectedSku}
                  onChange={(e) => {
                    setSelectedSku(e.target.value);
                    const found = inventory.find((i) => i.sku === e.target.value);
                    if (found) setAuditQty(found.available_qty);
                  }}
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-mono"
                >
                  {inventory.map((i) => (
                    <option key={i.sku} value={i.sku}>
                      {i.sku} (Sổ sách: {i.available_qty} {i.unit})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Số lượng Đếm Thực tế tại kệ</label>
                <input
                  type="number"
                  min="0"
                  value={auditQty}
                  onChange={(e) => setAuditQty(e.target.value)}
                  className="w-full bg-white border border-sky-300 rounded-lg px-3 py-2 text-slate-900 font-bold tabular-nums"
                  required
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Lý do chênh lệch / Biên bản</label>
                <input
                  type="text"
                  value={auditNote}
                  onChange={(e) => setAuditNote(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-xl font-semibold text-white bg-sky-600 hover:bg-sky-700 transition-all shadow-xs"
              >
                {loading ? 'Đang ghi nhận...' : 'Cập nhật Tồn Kho Thực Tế'}
              </button>
            </form>
          )}

          {activeTab === 'threshold' && (
            <form onSubmit={handleUpdateThresholds} className="space-y-3 text-xs">
              {isStaffOnly && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-[11px] flex items-center gap-1.5">
                  <i className="fa-solid fa-lock"></i>
                  <span>Thủ kho không được phép thay đổi định mức Min/Max (Chỉ Trưởng kho).</span>
                </div>
              )}
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mặt hàng</label>
                <select
                  value={selectedSku}
                  onChange={(e) => {
                    setSelectedSku(e.target.value);
                    const found = inventory.find((i) => i.sku === e.target.value);
                    if (found) {
                      setThMin(found.min_threshold ?? 10);
                      setThMax(found.max_threshold ?? 200);
                    }
                  }}
                  className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-mono"
                >
                  {inventory.map((i) => (
                    <option key={i.sku} value={i.sku}>{i.sku} - {i.product_name}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Định mức Min</label>
                  <input type="number" min="0" value={thMin} onChange={(e) => setThMin(e.target.value)} disabled={isStaffOnly} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 font-bold disabled:bg-slate-100" />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Định mức Max</label>
                  <input type="number" min="1" value={thMax} onChange={(e) => setThMax(e.target.value)} disabled={isStaffOnly} className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 font-bold disabled:bg-slate-100" />
                </div>
              </div>
              <button
                type="submit"
                disabled={loading || isStaffOnly}
                className="w-full py-2.5 rounded-xl font-semibold text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-40"
              >
                Lưu Định Mức Tồn Kho
              </button>
            </form>
          )}
        </div>

        {/* Bảng Dữ liệu Kho Cục bộ & Sổ cái */}
        <div className="lg:col-span-7 space-y-5">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <i className="fa-solid fa-database text-indigo-600"></i>
                Tồn kho Phân mảnh tại {currentBranch} (TON_KHO_{currentBranch})
              </h4>
              <button onClick={fetchBranchData} className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700">
                <i className="fa-solid fa-arrows-rotate mr-1"></i> Cập nhật
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase font-semibold">
                    <th className="py-2 px-3">SKU / Mã vạch</th>
                    <th className="py-2 px-3">Tên Sản Phẩm</th>
                    <th className="py-2 px-3 text-center">Khả Dụng</th>
                    <th className="py-2 px-3 text-center">Tạm Giữ</th>
                    <th className="py-2 px-3 text-center">Min</th>
                    <th className="py-2 px-3 text-center">Version</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {inventory.map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-50">
                      <td className="py-2 px-3">
                        <div className="font-mono font-bold text-indigo-700">{item.sku}</div>
                        <div className="font-mono text-[10px] text-slate-400">{item.barcode || `BC-${item.sku}`}</div>
                      </td>
                      <td className="py-2 px-3 font-medium text-slate-800">{item.product_name}</td>
                      <td className={`py-2 px-3 text-center font-bold tabular-nums ${item.is_low_stock ? 'text-rose-600' : 'text-emerald-700'}`}>
                        {item.available_qty}
                        {item.is_low_stock && <span className="block text-[10px] text-rose-500 font-medium">(Dưới Min)</span>}
                      </td>
                      <td className="py-2 px-3 text-center font-bold text-amber-600 tabular-nums">{item.reserved_qty}</td>
                      <td className="py-2 px-3 text-center text-slate-500 tabular-nums">{item.min_threshold || 10}</td>
                      <td className="py-2 px-3 text-center font-mono text-slate-400">v{item.version}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
            <h4 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <i className="fa-solid fa-list-check text-sky-600"></i>
              Sổ cái Biến động Gần nhất (Stock_Ledger & Audit Trail)
            </h4>
            <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100 text-xs font-mono">
              {ledger.length === 0 ? (
                <p className="p-4 text-slate-400 text-center">Chưa có giao dịch biến động nào.</p>
              ) : (
                ledger.slice(0, 12).map((l) => {
                  const changeType = l.change_type || '';
                  const rawQty = l.quantity ?? 0;
                  const absQty = Math.abs(rawQty);
                  const isDecrease = ['LOCAL_OUT', 'RESERVE', 'COMMIT_OUT'].includes(changeType);
                  const isIncrease = ['LOCAL_IN', 'TRANSFER_IN', 'RELEASE_RESERVE', 'INITIAL_STOCK'].includes(changeType);

                  let displayQty = `+${absQty}`;
                  let qtyColor = 'text-emerald-700 font-bold';
                  let badgeClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';

                  if (isDecrease) {
                    displayQty = `-${absQty}`;
                    qtyColor = 'text-rose-600 font-bold';
                    badgeClass = changeType === 'RESERVE'
                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                      : 'bg-rose-50 text-rose-700 border-rose-200';
                  } else if (isIncrease) {
                    displayQty = `+${absQty}`;
                    qtyColor = 'text-emerald-700 font-bold';
                    badgeClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
                  } else {
                    badgeClass = changeType === 'AUDIT_ADJUST'
                      ? 'bg-sky-50 text-sky-700 border-sky-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200';
                    if (rawQty < 0) {
                      displayQty = `-${absQty}`;
                      qtyColor = 'text-rose-600 font-bold';
                    } else if (rawQty > 0) {
                      displayQty = `+${absQty}`;
                      qtyColor = 'text-emerald-700 font-bold';
                    } else {
                      displayQty = '0';
                      qtyColor = 'text-slate-500 font-bold';
                    }
                  }

                  return (
                    <div key={l.ledger_id} className="p-2.5 flex items-center justify-between hover:bg-slate-50">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold shrink-0 ${badgeClass}`}>
                          {l.change_type}
                        </span>
                        <span className="text-slate-800 font-semibold truncate">
                          {l.sku} <span className={qtyColor}>({displayQty})</span>
                        </span>
                        {l.partner_name && (
                          <span className="text-[11px] text-slate-500 font-sans truncate">[{l.partner_name}]</span>
                        )}
                      </div>
                      <span className="text-slate-400 text-[10px] shrink-0 ml-2">{l.reference_id}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
