// frontend/src/components/LocalBranchPanel.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function LocalBranchPanel({ currentBranch, onActionSuccess }) {
  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const branchTitle = currentBranch === 'HN' ? 'Chi nhánh Hà Nội (Port 8001)' : 'Chi nhánh TP.HCM (Port 8002)';

  const [localStock, setLocalStock] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [selectedSku, setSelectedSku] = useState('LAPTOP-DELL-01');
  const [quantity, setQuantity] = useState(5);
  const [changeType, setChangeType] = useState('LOCAL_IN');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const fetchBranchData = async () => {
    try {
      const stock = await api.getLocalInventory(branchUrl);
      setLocalStock(stock);
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
        quantity: parseInt(quantity, 10)
      });
      setMsg({ type: 'success', text: `${res.message} (Mã tham chiếu: ${res.reference_id})` });
      fetchBranchData();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Thao tác thất bại' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg">
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
        {/* Form Nhập/Xuất tại chỗ */}
        <div className="lg:col-span-5 bg-slate-900/60 p-4 rounded-xl border border-slate-700/80">
          <h4 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <i className="fa-solid fa-boxes-packing text-indigo-400"></i>
            Tác vụ Kho Cục bộ (Nhập mua / Xuất bán)
          </h4>

          {msg && (
            <div className={`p-3 rounded-lg text-xs mb-4 ${
              msg.type === 'success' 
                ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30' 
                : 'bg-red-950/40 text-red-300 border border-red-500/30'
            }`}>
              {msg.text}
            </div>
          )}

          <form onSubmit={handleAdjust} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Hàng hóa (SKU)</label>
              <select
                value={selectedSku}
                onChange={e => setSelectedSku(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="LAPTOP-DELL-01">LAPTOP-DELL-01 (Laptop Dell XPS 15)</option>
                <option value="MACBOOK-AIR-M2">MACBOOK-AIR-M2 (MacBook Air M2)</option>
                <option value="CHUOT-LOGI-MX3">CHUOT-LOGI-MX3 (Chuột Logitech MX Master 3S)</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Loại Nghiệp vụ</label>
                <select
                  value={changeType}
                  onChange={e => setChangeType(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
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
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={`w-full py-2.5 px-4 rounded-lg font-semibold text-sm transition-all shadow-md ${
                changeType === 'LOCAL_IN'
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40'
                  : 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-950/40'
              } disabled:opacity-50`}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <i className="fa-solid fa-spinner animate-spin"></i> Đang ghi sổ CSDL...
                </span>
              ) : (
                <span>
                  {changeType === 'LOCAL_IN' ? 'Xác nhận Nhập Kho Cục Bộ' : 'Xác nhận Xuất Bán Cục Bộ'}
                </span>
              )}
            </button>
          </form>
        </div>

        {/* Bảng tồn kho cục bộ */}
        <div className="lg:col-span-7">
          <h4 className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <i className="fa-solid fa-database text-amber-400"></i>
            Dữ liệu Bảng Local_Inventory ({branchTitle})
          </h4>
          <div className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-900/50">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 text-slate-400 uppercase tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-3">SKU</th>
                  <th className="py-2.5 px-3">Tên Sản phẩm</th>
                  <th className="py-2.5 px-3 text-center">Khả dụng</th>
                  <th className="py-2.5 px-3 text-center">Tạm giữ (Saga)</th>
                  <th className="py-2.5 px-3 text-center font-mono">Version (Khóa)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60 font-sans">
                {localStock.map(item => (
                  <tr key={item.sku} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 font-mono font-medium text-amber-300">{item.sku}</td>
                    <td className="py-2 px-3 font-medium text-slate-200">{item.product_name}</td>
                    <td className="py-2 px-3 text-center font-bold text-emerald-400 text-sm">
                      {item.available_qty}
                    </td>
                    <td className="py-2 px-3 text-center text-amber-400">
                      {item.reserved_qty}
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
          <h4 className="text-sm font-semibold text-slate-200 mt-4 mb-2 flex items-center gap-2">
            <i className="fa-solid fa-list-check text-blue-400"></i>
            Sổ cái Biến động Gần nhất (Stock_Ledger & Idempotency)
          </h4>
          <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/50 text-xs font-mono">
            {ledger.length === 0 ? (
              <p className="p-3 text-slate-500 text-center">Chưa có giao dịch biến động nào.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {ledger.slice(0, 5).map(l => (
                  <div key={l.ledger_id} className="p-2 flex items-center justify-between hover:bg-slate-800/30">
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        l.change_type.includes('IN') ? 'bg-emerald-900/60 text-emerald-300' :
                        l.change_type === 'RESERVE' ? 'bg-amber-900/60 text-amber-300' :
                        'bg-rose-900/60 text-rose-300'
                      }`}>
                        {l.change_type}
                      </span>
                      <span className="text-slate-300 font-semibold">{l.sku} ({l.quantity})</span>
                    </div>
                    <span className="text-slate-500 text-[11px] truncate max-w-[200px]" title={l.reference_id}>
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
