// frontend/src/components/TransferOrderForm.jsx
import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export default function TransferOrderForm({ products = [], onTransferCreated }) {
  const [source, setSource] = useState('HN');
  const [dest, setDest] = useState('HCM');
  const [sku, setSku] = useState('');
  const [quantity, setQuantity] = useState(20);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Tự động chọn sản phẩm đầu tiên khi danh sách sản phẩm thay đổi
  useEffect(() => {
    if (products && products.length > 0) {
      if (!sku || !products.some(p => p.sku === sku)) {
        setSku(products[0].sku);
      }
    }
  }, [products, sku]);

  // Thông tin sản phẩm được chọn
  const selectedProduct = products.find(p => p.sku === sku);
  const sourceAvail = selectedProduct?.branches?.[source]?.available ?? 0;
  const sourceReserved = selectedProduct?.branches?.[source]?.reserved ?? 0;
  const destAvail = selectedProduct?.branches?.[dest]?.available ?? 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (source === dest) {
      alert('Kho nguồn và kho đích không được trùng nhau!');
      return;
    }
    if (!sku) {
      alert('Vui lòng chọn một sản phẩm cần điều chuyển!');
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
                const newSource = e.target.value;
                setSource(newSource);
                if (newSource === dest) setDest(newSource === 'HN' ? 'HCM' : 'HN');
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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block font-medium text-slate-400 mb-1">
              Sản Phẩm (SKU) ({products.length} mặt hàng)
            </label>
            <select
              value={sku}
              onChange={e => setSku(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono text-xs"
            >
              {products && products.length > 0 ? (
                products.map(p => {
                  const pAvail = p.branches?.[source]?.available ?? 0;
                  return (
                    <option key={p.sku} value={p.sku}>
                      {p.sku} - {p.product_name} (Tồn {source}: {pAvail} {p.unit || 'cái'})
                    </option>
                  );
                })
              ) : (
                <option value="">-- Đang nạp danh mục --</option>
              )}
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

        {/* Live Stock Status Preview */}
        {selectedProduct && (
          <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-700/80 flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">
                Tồn khả dụng kho nguồn <strong className="text-indigo-300">[{source}]</strong>:
              </span>
              <span className={`font-mono font-bold ${sourceAvail >= quantity ? 'text-emerald-400' : 'text-amber-400'}`}>
                {sourceAvail} {selectedProduct.unit || 'cái'}
              </span>
              {sourceReserved > 0 && (
                <span className="text-amber-400/80 text-[10px]">
                  (Tạm khóa: {sourceReserved})
                </span>
              )}
            </div>
            <div className="text-slate-400">
              Tồn kho đích <strong className="text-violet-300">[{dest}]</strong>: <span className="font-mono text-slate-200 font-bold">{destAvail} {selectedProduct.unit || 'cái'}</span>
            </div>
          </div>
        )}

        {selectedProduct && sourceAvail < parseInt(quantity, 10) && (
          <p className="text-[11px] text-amber-400 flex items-center gap-1.5 bg-amber-950/30 p-2 rounded-lg border border-amber-500/30">
            <i className="fa-solid fa-triangle-exclamation"></i>
            <span>Cảnh báo: Số lượng chuyển ({quantity}) vượt quá tồn khả dụng ({sourceAvail}) tại kho xuất {source}. Saga có thể bị từ chối nếu không đủ tồn.</span>
          </p>
        )}

        <button
          type="submit"
          disabled={loading || !sku}
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
