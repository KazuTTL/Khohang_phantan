// frontend/src/components/LocalBranchPanel.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function LocalBranchPanel({ currentBranch, onActionSuccess }) {
  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const branchTitle = currentBranch === 'HN' ? 'Kho Chi Nhánh Hà Nội (Port 8001)' : 'Kho Chi Nhánh TP.HCM (Port 8002)';

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
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
      {/* Top Banner: Local Autonomy */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 mb-5 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-5 bg-blue-600 rounded-sm"></span>
            <span className="px-2.5 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 font-mono text-xs font-bold">
              NODE {currentBranch}
            </span>
            <h3 className="text-base font-bold text-slate-800">
              Vận Hành Tự Trị Cục Bộ (Local Autonomy) — {branchTitle}
            </h3>
          </div>
          <p className="text-xs text-emerald-700 mt-1 ml-4 font-medium flex items-center gap-1.5">
            <i className="fa-solid fa-shield-halved"></i>
            Chi nhánh xử lý nhập/xuất tại chỗ độc lập trên CSDL riêng, hoạt động 100% bình thường ngay cả khi Trụ sở chính (HQ) tắt.
          </p>
        </div>
        <button
          onClick={fetchBranchData}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors flex items-center gap-1.5 self-start sm:self-auto font-medium"
        >
          <i className="fa-solid fa-arrows-rotate"></i>
          Làm mới CSDL Kho
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Nhập/Xuất tại chỗ */}
        <div className="lg:col-span-5 bg-slate-50/70 p-4 sm:p-5 rounded-xl border border-slate-200">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center text-xs">
              <i className="fa-solid fa-dolly"></i>
            </div>
            <div>
              <h4 className="text-xs sm:text-sm font-bold text-slate-800">
                Tác Vụ Kho Tại Chỗ
              </h4>
              <p className="text-[11px] text-slate-500">Nhập kho mua mới hoặc xuất bán lẻ nội bộ</p>
            </div>
          </div>

          {msg && (
            <div className={`p-3 rounded-lg text-xs mb-4 flex items-start gap-2 ${
              msg.type === 'success' 
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' 
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}>
              <i className={`fa-solid ${msg.type === 'success' ? 'fa-circle-check text-emerald-600' : 'fa-triangle-exclamation text-rose-600'} mt-0.5`}></i>
              <p className="font-medium">{msg.text}</p>
            </div>
          )}

          <form onSubmit={handleAdjust} className="space-y-3.5 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Mặt Hàng (SKU)</label>
              <div className="relative">
                <select
                  value={selectedSku}
                  onChange={e => setSelectedSku(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-medium focus:outline-none focus:border-blue-500 appearance-none pr-8 shadow-2xs"
                >
                  <option value="LAPTOP-DELL-01">LAPTOP-DELL-01 • Dell XPS 15</option>
                  <option value="MACBOOK-AIR-M2">MACBOOK-AIR-M2 • MacBook Air M2</option>
                  <option value="CHUOT-LOGI-MX3">CHUOT-LOGI-MX3 • Chuột Logitech MX Master 3S</option>
                </select>
                <i className="fa-solid fa-chevron-down absolute right-3 top-3 text-slate-400 pointer-events-none text-[10px]"></i>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Loại Nghiệp Vụ</label>
                <div className="relative">
                  <select
                    value={changeType}
                    onChange={e => setChangeType(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-semibold focus:outline-none focus:border-blue-500 appearance-none pr-8 shadow-2xs"
                  >
                    <option value="LOCAL_IN">Nhập Kho (+)</option>
                    <option value="LOCAL_OUT">Xuất Bán (-)</option>
                  </select>
                  <i className="fa-solid fa-chevron-down absolute right-3 top-3 text-slate-400 pointer-events-none text-[10px]"></i>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Số Lượng</label>
                <input
                  type="number"
                  min="1"
                  value={quantity}
                  onChange={e => setQuantity(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-bold focus:outline-none focus:border-blue-500 text-center shadow-2xs"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={`w-full py-2.5 px-4 rounded-lg font-bold text-xs transition-all shadow-xs flex items-center justify-center gap-2 ${
                changeType === 'LOCAL_IN'
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : 'bg-amber-600 hover:bg-amber-700 text-white'
              } disabled:opacity-50`}
            >
              {loading ? (
                <>
                  <i className="fa-solid fa-spinner animate-spin"></i> Đang ghi sổ CSDL cục bộ...
                </>
              ) : (
                <>
                  <i className={`fa-solid ${changeType === 'LOCAL_IN' ? 'fa-arrow-down' : 'fa-arrow-up'}`}></i>
                  {changeType === 'LOCAL_IN' ? 'Xác nhận Nhập Kho Cục Bộ' : 'Xác nhận Xuất Bán Cục Bộ'}
                </>
              )}
            </button>
          </form>
        </div>

        {/* Bảng tồn kho cục bộ & Sổ cái */}
        <div className="lg:col-span-7 space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <i className="fa-solid fa-database text-blue-600"></i>
                Bảng Local_Inventory ({currentBranch})
              </h4>
              <span className="text-[11px] text-slate-400 font-medium">Khóa lạc quan (Optimistic Lock)</span>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-50 text-[11px] text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3">SKU</th>
                    <th className="py-2.5 px-3">Tên Mặt Hàng</th>
                    <th className="py-2.5 px-3 text-center">Khả Dụng</th>
                    <th className="py-2.5 px-3 text-center">Tạm Khóa (Saga)</th>
                    <th className="py-2.5 px-3 text-center">Phiên Bản (Version)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {localStock.map(item => (
                    <tr key={item.sku} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-mono font-bold text-blue-600">{item.sku}</td>
                      <td className="py-2.5 px-3 font-medium text-slate-800">{item.product_name}</td>
                      <td className="py-2.5 px-3 text-center font-bold text-emerald-700">
                        {item.available_qty}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {item.reserved_qty > 0 ? (
                          <span className="font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                            {item.reserved_qty}
                          </span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono text-slate-500">
                        v{item.version}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sổ cái biến động kho */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <i className="fa-solid fa-book-journal-whills text-indigo-600"></i>
                Sổ Cái Biến Động (Stock_Ledger & Idempotency Key)
              </h4>
              <span className="text-[11px] text-slate-400 font-medium">Chống trùng lặp At-Most-Once</span>
            </div>
            <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-200 text-xs">
              {ledger.length === 0 ? (
                <p className="p-4 text-slate-400 text-center">Chưa có giao dịch nào được ghi sổ.</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {ledger.slice(0, 5).map(l => (
                    <div key={l.ledger_id} className="p-2.5 flex items-center justify-between hover:bg-slate-50">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          l.change_type.includes('IN') ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                          l.change_type === 'RESERVE' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                          'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}>
                          {l.change_type}
                        </span>
                        <span className="text-slate-800 font-semibold">{l.sku} ({l.quantity})</span>
                      </div>
                      <span className="text-slate-400 font-mono text-[11px] truncate max-w-[200px]" title={l.reference_id}>
                        Ref: {l.reference_id}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
