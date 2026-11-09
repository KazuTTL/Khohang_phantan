// frontend/src/components/LocalBranchPanel.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function LocalBranchPanel({ currentBranch, onActionSuccess }) {
  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const branchTitle = currentBranch === 'HN' ? 'Chi nhánh Hà Nội (Port 8001)' : 'Chi nhánh TP.HCM (Port 8002)';

  const [activeTab, setActiveTab] = useState('adjust'); // 'adjust' | 'audit'
  const [localStock, setLocalStock] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [selectedSku, setSelectedSku] = useState('');
  const [quantity, setQuantity] = useState(5);
  const [changeType, setChangeType] = useState('LOCAL_IN');
  const [partnerName, setPartnerName] = useState('');
  const [note, setNote] = useState('');
  const [auditQty, setAuditQty] = useState(0);
  const [auditNote, setAuditNote] = useState('Kiểm kê định kỳ tháng này');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const fetchBranchData = async () => {
    try {
      const stock = await api.getLocalInventory(branchUrl);
      setLocalStock(stock);
      if (stock.length > 0 && !selectedSku) {
        setSelectedSku(stock[0].sku);
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
      setMsg({ type: 'success', text: `${res.message} (Mã tham chiếu: ${res.reference_id})` });
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
        text: `Kiểm kê SKU '${res.sku}' hoàn tất! Sổ sách: ${res.old_qty}, Thực tế: ${res.actual_qty}, Chênh lệch: ${res.variance >= 0 ? '+' : ''}${res.variance}`
      });
      fetchBranchData();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Kiểm kê thất bại' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-700 mb-5 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono text-xs font-semibold">
              LOCAL NODE: {currentBranch}
            </span>
            <h3 className="text-lg font-bold text-white">
              Vận hành Độc lập Cục bộ (Local Autonomy) - {branchTitle}
            </h3>
          </div>
          <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1.5">
            <i className="fa-solid fa-shield-halved"></i>
            Chi nhánh xử lý nhập/xuất tại chỗ trên CSDL riêng, không phụ thuộc vào tình trạng Trụ sở chính (HQ).
          </p>
        </div>
        <button
          onClick={fetchBranchData}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors flex items-center gap-1.5 self-start md:self-auto"
        >
          <i className="fa-solid fa-arrows-rotate"></i>
          Cập nhật CSDL Chi nhánh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Tác vụ Cục bộ */}
        <div className="lg:col-span-5 bg-slate-900/60 p-4 rounded-xl border border-slate-700/80">
          <div className="flex items-center gap-2 mb-4 border-b border-slate-700 pb-2">
            <button
              onClick={() => setActiveTab('adjust')}
              className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'adjust'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <i className="fa-solid fa-boxes-packing mr-1.5"></i>
              Nhập Mua / Xuất Bán
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={`text-xs font-bold px-3 py-1.5 rounded-lg transition-all ${
                activeTab === 'audit'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <i className="fa-solid fa-clipboard-check mr-1.5"></i>
              Kiểm Kê Thực Tế
            </button>
          </div>

          {msg && (
            <div className={`p-3 rounded-lg text-xs mb-4 ${
              msg.type === 'success' 
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30' 
                : 'bg-red-950/40 text-red-300 border border-red-500/30'
            }`}>
              {msg.text}
            </div>
          )}

          {activeTab === 'adjust' ? (
            <form onSubmit={handleAdjust} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Mặt hàng (SKU)</label>
                <select
                  value={selectedSku}
                  onChange={e => setSelectedSku(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  {localStock.map(p => (
                    <option key={p.sku} value={p.sku}>
                      {p.sku} - {p.product_name} (Tồn: {p.available_qty})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Loại Nghiệp vụ</label>
                  <select
                    value={changeType}
                    onChange={e => setChangeType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="LOCAL_IN">Nhập kho (+)</option>
                    <option value="LOCAL_OUT">Xuất bán (-)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Số lượng</label>
                  <input
                    type="number"
                    min="1"
                    value={quantity}
                    onChange={e => setQuantity(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  {changeType === 'LOCAL_IN' ? 'Nhà Cung Cấp (Vendor)' : 'Khách Hàng (Customer)'}
                </label>
                <input
                  type="text"
                  placeholder={changeType === 'LOCAL_IN' ? 'VD: Cty TNHH Thiết bị ABC' : 'VD: Đại lý Bán lẻ Miền Bắc'}
                  value={partnerName}
                  onChange={e => setPartnerName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Ghi chú / Số hóa đơn</label>
                <input
                  type="text"
                  placeholder="VD: Hóa đơn GTGT #HD-2026-88"
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className={`w-full py-2.5 px-4 rounded-lg font-semibold text-xs transition-all shadow-md ${
                  changeType === 'LOCAL_IN'
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40'
                    : 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-950/40'
                } disabled:opacity-50`}
              >
                {loading ? 'Đang ghi sổ CSDL...' : (changeType === 'LOCAL_IN' ? 'Xác nhận Nhập Kho Cục Bộ' : 'Xác nhận Xuất Bán Cục Bộ')}
              </button>
            </form>
          ) : (
            <form onSubmit={handleAudit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Mặt hàng Kiểm kê</label>
                <select
                  value={selectedSku}
                  onChange={e => {
                    setSelectedSku(e.target.value);
                    const it = localStock.find(x => x.sku === e.target.value);
                    if (it) setAuditQty(it.available_qty);
                  }}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  {localStock.map(p => (
                    <option key={p.sku} value={p.sku}>
                      {p.sku} - {p.product_name} (Sổ sách: {p.available_qty})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Số lượng Đếm thực tế tại Kệ</label>
                <input
                  type="number"
                  min="0"
                  value={auditQty}
                  onChange={e => setAuditQty(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Lý do điều chỉnh kiểm kê</label>
                <input
                  type="text"
                  value={auditNote}
                  onChange={e => setAuditNote(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-lg font-semibold text-xs bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-md shadow-indigo-950/40 disabled:opacity-50"
              >
                {loading ? 'Đang điều chỉnh tồn kho...' : 'Xác nhận Điều Chỉnh Kiểm Kê'}
              </button>
            </form>
          )}
        </div>

        {/* Bảng tồn kho cục bộ */}
        <div className="lg:col-span-7">
          <h4 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <i className="fa-solid fa-database text-amber-400"></i>
            Dữ liệu Bảng Local_Inventory ({branchTitle})
          </h4>
          <div className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-900/50 mb-4">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 text-slate-400 uppercase tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-3">SKU</th>
                  <th className="py-2.5 px-3">Tên Sản phẩm</th>
                  <th className="py-2.5 px-3 text-center">Khả dụng</th>
                  <th className="py-2.5 px-3 text-center">Tạm giữ</th>
                  <th className="py-2.5 px-3 text-center">Định mức Min</th>
                  <th className="py-2.5 px-3 text-center font-mono">Khóa Version</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60 font-sans">
                {localStock.map(item => (
                  <tr key={item.sku} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 font-mono font-medium text-amber-300">{item.sku}</td>
                    <td className="py-2 px-3 font-medium text-slate-200">{item.product_name}</td>
                    <td className="py-2 px-3 text-center font-bold text-sm">
                      <span className={item.is_low_stock ? 'text-red-400' : 'text-emerald-400'}>
                        {item.available_qty}
                      </span>
                      {item.is_low_stock && (
                        <span className="block text-[9px] text-red-400 font-semibold">(Tồn thấp)</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-center text-amber-400">
                      {item.reserved_qty}
                    </td>
                    <td className="py-2 px-3 text-center text-slate-400">
                      {item.min_threshold || 10}
                    </td>
                    <td className="py-2 px-3 text-center font-mono text-slate-400">
                      v{item.version}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Lịch sử Sổ cái */}
          <h4 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <i className="fa-solid fa-list-check text-blue-400"></i>
            Sổ cái Biến động Gần nhất (Stock_Ledger & Audit Trail)
          </h4>
          <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/50 text-xs font-mono">
            {ledger.length === 0 ? (
              <p className="p-3 text-slate-500 text-center">Chưa có giao dịch biến động nào.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {ledger.slice(0, 7).map(l => (
                  <div key={l.ledger_id} className="p-2 flex items-center justify-between hover:bg-slate-800/30">
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        l.change_type.includes('IN') ? 'bg-emerald-900/60 text-emerald-300' :
                        l.change_type === 'RESERVE' ? 'bg-amber-900/60 text-amber-300' :
                        l.change_type === 'AUDIT_ADJUST' ? 'bg-blue-900/60 text-blue-300' :
                        'bg-rose-900/60 text-rose-300'
                      }`}>
                        {l.change_type}
                      </span>
                      <span className="text-slate-300 font-semibold">{l.sku} ({l.quantity >= 0 ? '+' : ''}{l.quantity})</span>
                      {l.partner_name && (
                        <span className="text-[11px] text-slate-400 font-sans">[{l.partner_name}]</span>
                      )}
                    </div>
                    <span className="text-slate-500 text-[10px] truncate max-w-[160px]" title={l.reference_id}>
                      {l.reference_id}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
