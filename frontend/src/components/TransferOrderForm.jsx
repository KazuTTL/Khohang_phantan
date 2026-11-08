// frontend/src/components/TransferOrderForm.jsx
import React, { useState } from 'react';
import { api } from '../api/client';

export default function TransferOrderForm({ onTransferCreated }) {
  const [source, setSource] = useState('HN');
  const [dest, setDest] = useState('HCM');
  const [sku, setSku] = useState('LAPTOP-DELL-01');
  const [quantity, setQuantity] = useState(15);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (source === dest) {
      alert('Kho nguồn và kho đích không được trùng nhau!');
      return;
    }
    setLoading(true);
    setResult(null);

    try {
      const res = await api.createTransfer({
        source_branch: source,
        dest_branch: dest,
        sku: sku,
        quantity: parseInt(quantity, 10)
      });
      setResult({ type: 'success', data: res });
      if (onTransferCreated) onTransferCreated(res);
    } catch (err) {
      setResult({ type: 'error', message: err.message || 'Lỗi khởi tạo Saga' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-2 h-5 bg-indigo-600 rounded-sm"></span>
        <h3 className="text-base font-bold text-slate-800">
          Tạo Lệnh Điều Chuyển Kho Liên Chi Nhánh
        </h3>
      </div>
      <p className="text-xs text-slate-500 mb-4 ml-4">
        Khởi động chuỗi giao dịch Saga được điều phối tập trung bởi Trụ sở chính (HQ Node - Cổng 8000)
      </p>

      {result && (
        <div className={`p-3.5 rounded-lg text-xs mb-4 flex items-start gap-2.5 ${
          result.type === 'success' 
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' 
            : 'bg-rose-50 text-rose-800 border border-rose-200'
        }`}>
          <i className={`fa-solid ${result.type === 'success' ? 'fa-circle-check text-emerald-600' : 'fa-triangle-exclamation text-rose-600'} mt-0.5 text-sm`}></i>
          <div>
            {result.type === 'success' ? (
              <>
                <p className="font-bold text-emerald-900">Khởi tạo Saga thành công!</p>
                <p className="mt-0.5 font-mono text-[11px] text-slate-600">
                  Mã điều chuyển: <span className="font-bold text-indigo-700">{result.data.transfer_id}</span>
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Lệnh <code className="bg-white px-1 py-0.5 rounded border border-emerald-300">CMD_RESERVE_STOCK</code> đã phát tới Kho {result.data.source_branch}.
                </p>
              </>
            ) : (
              <p className="font-medium">{result.message}</p>
            )}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Kho Xuất Hàng (Nguồn)</label>
            <div className="relative">
              <select
                value={source}
                onChange={e => {
                  setSource(e.target.value);
                  if (e.target.value === dest) setDest(e.target.value === 'HN' ? 'HCM' : 'HN');
                }}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-medium focus:outline-none focus:border-blue-500 focus:bg-white transition-all appearance-none pr-8"
              >
                <option value="HN">Chi nhánh Hà Nội (HN)</option>
                <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
              </select>
              <i className="fa-solid fa-chevron-down absolute right-3 top-3 text-slate-400 pointer-events-none text-[10px]"></i>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Kho Nhận Hàng (Đích)</label>
            <div className="relative">
              <select
                value={dest}
                onChange={e => setDest(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-medium focus:outline-none focus:border-blue-500 focus:bg-white transition-all appearance-none pr-8"
              >
                <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
                <option value="HN">Chi nhánh Hà Nội (HN)</option>
              </select>
              <i className="fa-solid fa-chevron-down absolute right-3 top-3 text-slate-400 pointer-events-none text-[10px]"></i>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="block font-semibold text-slate-700 mb-1">Mặt Hàng (SKU)</label>
            <div className="relative">
              <select
                value={sku}
                onChange={e => setSku(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-medium focus:outline-none focus:border-blue-500 focus:bg-white transition-all appearance-none pr-8"
              >
                <option value="LAPTOP-DELL-01">LAPTOP-DELL-01 • Dell XPS 15</option>
                <option value="MACBOOK-AIR-M2">MACBOOK-AIR-M2 • MacBook Air M2</option>
                <option value="CHUOT-LOGI-MX3">CHUOT-LOGI-MX3 • Chuột Logitech MX Master 3S</option>
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
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-bold focus:outline-none focus:border-blue-500 focus:bg-white transition-all text-center"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-bold text-xs shadow-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <>
              <i className="fa-solid fa-spinner animate-spin"></i> Đang phát lệnh điều phối Saga...
            </>
          ) : (
            <>
              <i className="fa-solid fa-paper-plane"></i> Phát Lệnh Chuyển Kho (Start Saga)
            </>
          )}
        </button>
      </form>
    </div>
  );
}
