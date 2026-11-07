// frontend/src/components/TransferOrderForm.jsx
import React, { useState } from 'react';
import { api } from '../api/client';

export default function TransferOrderForm({ onTransferCreated }) {
  const [source, setSource] = useState('HN');
  const [dest, setDest] = useState('HCM');
  const [sku, setSku] = useState('LAPTOP-DELL-01');
  const [quantity, setQuantity] = useState(20);
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
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg">
      <div className="flex items-center gap-2 mb-3">
        <i className="fa-solid fa-dolly text-indigo-400 text-lg"></i>
        <h3 className="text-base font-bold text-white">
          Tạo Lệnh Điều Chuyển Kho Liên Chi Nhánh (Saga Orchestration)
        </h3>
      </div>
      <p className="text-xs text-slate-400 mb-4">
        Lệnh được Trụ sở chính (HQ - Cổng 8000) điều phối qua Message Broker (RabbitMQ), thực hiện khóa tạm tại kho xuất và bảo đảm tính nhất quán cuối cùng.
      </p>

      {result && (
        <div className={`p-3 rounded-lg text-xs mb-4 ${
          result.type === 'success' 
            ? 'bg-emerald-950/40 text-emerald-300 border border-emerald-500/30' 
            : 'bg-red-950/40 text-red-300 border border-red-500/30'
        }`}>
          {result.type === 'success' ? (
            <div>
              <p className="font-semibold text-emerald-200">
                <i className="fa-solid fa-circle-check mr-1.5"></i>
                Khởi tạo Saga thành công!
              </p>
              <p className="mt-1 font-mono text-[11px] text-slate-300">
                Mã: {result.data.transfer_id} | Trạng thái: <span className="text-amber-300 font-bold">{result.data.saga_status}</span>
              </p>
            </div>
          ) : (
            <p><i className="fa-solid fa-triangle-exclamation mr-1.5"></i> {result.message}</p>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-slate-400 mb-1">Kho Nguồn (Xuất)</label>
            <select
              value={source}
              onChange={e => {
                setSource(e.target.value);
                if (e.target.value === dest) setDest(e.target.value === 'HN' ? 'HCM' : 'HN');
              }}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="HN">Chi nhánh Hà Nội (HN)</option>
              <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
            </select>
          </div>

          <div>
            <label className="block font-medium text-slate-400 mb-1">Kho Đích (Nhập)</label>
            <select
              value={dest}
              onChange={e => setDest(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
              <option value="HN">Chi nhánh Hà Nội (HN)</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-slate-400 mb-1">Sản Phẩm (SKU)</label>
            <select
              value={sku}
              onChange={e => setSku(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="LAPTOP-DELL-01">LAPTOP-DELL-01 (Dell XPS 15)</option>
              <option value="MACBOOK-AIR-M2">MACBOOK-AIR-M2 (MacBook Air)</option>
              <option value="CHUOT-LOGI-MX3">CHUOT-LOGI-MX3 (MX Master 3S)</option>
            </select>
          </div>

          <div>
            <label className="block font-medium text-slate-400 mb-1">Số Lượng Chuyển</label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={e => setQuantity(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-md shadow-indigo-950/40 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
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
