// frontend/src/components/TransferOrderForm.jsx
import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export default function TransferOrderForm({ products = [], prefill = null, onTransferCreated }) {
  const [source, setSource] = useState('HN');
  const [dest, setDest] = useState('HCM');
  const [sku, setSku] = useState('');
  const [quantity, setQuantity] = useState(20);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (prefill) {
      if (prefill.source) setSource(prefill.source);
      if (prefill.dest) setDest(prefill.dest);
      if (prefill.sku) setSku(prefill.sku);
      if (prefill.quantity) setQuantity(prefill.quantity);
    }
  }, [prefill]);

  useEffect(() => {
    if (products && products.length > 0) {
      if (!sku || !products.some((p) => p.sku === sku)) {
        setSku(products[0].sku);
      }
    }
  }, [products, sku]);

  const selectedProduct = products.find((p) => p.sku === sku);
  const sourceAvail = selectedProduct?.branches?.[source]?.available ?? 0;
  const sourceReserved = selectedProduct?.branches?.[source]?.reserved ?? 0;
  const destAvail = selectedProduct?.branches?.[dest]?.available ?? 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (source === dest) {
      alert('Kho nguồn và kho đích không được trùng nhau.');
      return;
    }
    if (!sku) return;
    setLoading(true);
    setResult(null);

    try {
      const res = await api.createTransfer({
        source_branch: source,
        dest_branch: dest,
        sku,
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
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
          <i className="fa-solid fa-dolly text-sm"></i>
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">Phát Lệnh Điều Chuyển Liên Chi Nhánh</h3>
          <p className="text-[11px] text-slate-500">Điều phối bất đồng bộ qua RabbitMQ & Saga Pattern</p>
        </div>
      </div>

      {result && (
        <div className={`p-3 rounded-lg text-xs my-3 border ${
          result.type === 'success'
            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
            : 'bg-rose-50 text-rose-800 border-rose-200'
        }`}>
          {result.type === 'success' ? (
            <div>
              <p className="font-semibold flex items-center gap-1.5">
                <i className="fa-solid fa-circle-check text-emerald-600"></i>
                Đã khởi tạo lệnh điều chuyển Saga thành công!
              </p>
              <p className="mt-1 font-mono text-[11px] text-slate-600">
                Mã: {result.data.transfer_id.slice(0, 8)}... | Trạng thái: <span className="font-bold text-amber-700">{result.data.saga_status}</span>
              </p>
            </div>
          ) : (
            <p><i className="fa-solid fa-triangle-exclamation mr-1.5"></i>{result.message}</p>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3.5 text-xs mt-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Kho Nguồn (Xuất)</label>
            <select
              value={source}
              onChange={(e) => {
                const newSrc = e.target.value;
                setSource(newSrc);
                if (newSrc === dest) setDest(newSrc === 'HN' ? 'HCM' : 'HN');
              }}
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
            >
              <option value="HN">Chi nhánh Hà Nội (HN)</option>
              <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
            </select>
          </div>
          <div>
            <label className="block font-semibold text-slate-700 mb-1">Kho Đích (Nhập)</label>
            <select
              value={dest}
              onChange={(e) => setDest(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
            >
              <option value="HCM">Chi nhánh TP.HCM (HCM)</option>
              <option value="HN">Chi nhánh Hà Nội (HN)</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <label className="block font-semibold text-slate-700 mb-1">
              Mặt hàng ({products.length} SKU)
            </label>
            <select
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              required
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
            >
              {products.length > 0 ? (
                products.map((p) => {
                  const pAvail = p.branches?.[source]?.available ?? 0;
                  return (
                    <option key={p.sku} value={p.sku}>
                      {p.sku} - {p.product_name} (Tồn {source}: {pAvail})
                    </option>
                  );
                })
              ) : (
                <option value="">-- Đang tải danh mục --</option>
              )}
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">Số lượng</label>
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 font-bold tabular-nums focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
              required
            />
          </div>
        </div>

        {selectedProduct && (
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <div>
              <span className="text-slate-500">Khả dụng tại <strong className="text-indigo-700">{source}</strong>: </span>
              <span className={`font-mono font-bold ${sourceAvail >= quantity ? 'text-emerald-700' : 'text-amber-700'}`}>
                {sourceAvail} {selectedProduct.unit}
              </span>
              {sourceReserved > 0 && (
                <span className="ml-1.5 text-amber-600">(Tạm giữ: {sourceReserved})</span>
              )}
            </div>
            <div>
              <span className="text-slate-500">Tồn tại <strong className="text-violet-700">{dest}</strong>: </span>
              <span className="font-mono font-bold text-slate-800">{destAvail} {selectedProduct.unit}</span>
            </div>
          </div>
        )}

        {selectedProduct && sourceAvail < parseInt(quantity, 10) && (
          <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] flex items-center gap-1.5">
            <i className="fa-solid fa-triangle-exclamation text-amber-600"></i>
            <span>Số lượng chuyển ({quantity}) lớn hơn tồn khả dụng ({sourceAvail}) tại {source}.</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !sku}
          className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-xs transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {loading ? (
            <>
              <i className="fa-solid fa-spinner animate-spin"></i> Đang khởi tạo Saga...
            </>
          ) : (
            <>
              <i className="fa-solid fa-paper-plane"></i> Phát Lệnh Điều Chuyển (Start Saga)
            </>
          )}
        </button>
      </form>
    </div>
  );
}
