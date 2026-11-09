// frontend/src/components/GlobalStockTable.jsx
import React, { useState } from 'react';
import { api } from '../api/client';

export default function GlobalStockTable({ globalStock, loading, onRefresh }) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('Chiếc');
  const [price, setPrice] = useState(1000000);
  const [category, setCategory] = useState('Điện tử');
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState(null);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setMsg(null);
    try {
      await api.createProduct({
        sku: sku.trim().toUpperCase(),
        product_name: name.trim(),
        unit: unit.trim(),
        price: parseFloat(price),
        category
      });
      setMsg({ type: 'success', text: `Đã tạo SKU '${sku}' và phát tín hiệu đồng bộ tới toàn bộ chi nhánh!` });
      setSku('');
      setName('');
      if (onRefresh) onRefresh();
      setTimeout(() => {
        setShowAddModal(false);
        setMsg(null);
      }, 1500);
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Lỗi khi tạo sản phẩm' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-boxes-stacked text-amber-400"></i>
            Tồn kho Toàn cục Hệ thống (HQ Read-Model Snapshot)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Đồng bộ bất đồng bộ từ các chi nhánh thông qua RabbitMQ Broker (Eventual Consistency)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-950/40"
          >
            <i className="fa-solid fa-plus"></i>
            Thêm Mặt Hàng Mới
          </button>
          <button
            onClick={onRefresh}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors flex items-center gap-1.5"
          >
            <i className={`fa-solid fa-rotate-right ${loading ? 'animate-spin' : ''}`}></i>
            Làm mới
          </button>
        </div>
      </div>

      {/* Modal Thêm Sản Phẩm Mới */}
      {showAddModal && (
        <div className="mb-5 p-4 bg-slate-900/90 border border-indigo-500/50 rounded-xl animate-fade-in shadow-xl">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-700">
            <h4 className="text-sm font-bold text-indigo-300 flex items-center gap-2">
              <i className="fa-solid fa-cart-plus"></i>
              Thêm Mặt Hàng Mới vào Master Data Catalog (Trụ sở chính)
            </h4>
            <button
              onClick={() => setShowAddModal(false)}
              className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded"
            >
              <i className="fa-solid fa-xmark text-sm"></i>
            </button>
          </div>

          {msg && (
            <div className={`p-2.5 rounded-lg text-xs mb-3 ${
              msg.type === 'success'
                ? 'bg-emerald-950/50 text-emerald-300 border border-emerald-500/30'
                : 'bg-red-950/50 text-red-300 border border-red-500/30'
            }`}>
              {msg.text}
            </div>
          )}

          <form onSubmit={handleCreateProduct} className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Mã SKU</label>
              <input
                type="text"
                placeholder="VD: TAI-NGHE-SONY"
                value={sku}
                onChange={e => setSku(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Tên Hàng Hóa</label>
              <input
                type="text"
                placeholder="VD: Tai nghe chống ồn Sony WH-1000XM5"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Đơn vị tính</label>
              <input
                type="text"
                placeholder="Chiếc, Hộp, Bộ..."
                value={unit}
                onChange={e => setUnit(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Đơn giá (VNĐ)</label>
              <input
                type="number"
                min="0"
                step="10000"
                value={price}
                onChange={e => setPrice(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="md:col-span-4 flex justify-end gap-2 mt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-50"
              >
                {submitting ? 'Đang phát tán đồng bộ...' : 'Tạo & Đồng Bộ Toàn Bộ Chi Nhánh'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-700">
            <tr>
              <th className="py-3 px-4">Mã SKU</th>
              <th className="py-3 px-4">Tên Hàng Hóa</th>
              <th className="py-3 px-4 text-center">ĐVT</th>
              <th className="py-3 px-4 text-center">Tổng Khả Dụng</th>
              <th className="py-3 px-4 text-center">Tổng Tạm Khóa</th>
              <th className="py-3 px-4 text-center">Trạng Thái Kho</th>
              <th className="py-3 px-4 bg-indigo-950/30 text-indigo-300 text-center border-l border-slate-700">
                Kho Hà Nội (HN)
              </th>
              <th className="py-3 px-4 bg-violet-950/30 text-violet-300 text-center border-l border-slate-700">
                Kho TP.HCM (HCM)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/60 font-sans">
            {globalStock.length === 0 ? (
              <tr>
                <td colSpan="8" className="py-8 text-center text-slate-500">
                  Chưa có dữ liệu snapshot hoặc HQ Service đang offline.
                </td>
              </tr>
            ) : (
              globalStock.map(p => {
                const hn = p.branches?.HN || { available: 0, reserved: 0 };
                const hcm = p.branches?.HCM || { available: 0, reserved: 0 };
                const isLow = p.total_available <= 20;

                return (
                  <tr key={p.sku} className="hover:bg-slate-700/30 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-amber-300">{p.sku}</td>
                    <td className="py-3 px-4 font-semibold text-slate-100">{p.product_name}</td>
                    <td className="py-3 px-4 text-center text-slate-400">{p.unit}</td>
                    <td className="py-3 px-4 text-center font-bold text-emerald-400 text-base">
                      {p.total_available}
                    </td>
                    <td className="py-3 px-4 text-center font-medium text-amber-400">
                      {p.total_reserved > 0 ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          {p.total_reserved}
                        </span>
                      ) : (
                        <span className="text-slate-500">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {isLow ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30">
                          Cảnh báo tồn thấp
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          Mức an toàn
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center border-l border-slate-700 bg-indigo-950/10">
                      <span className="font-semibold text-indigo-300">{hn.available}</span>
                      {hn.reserved > 0 && (
                        <span className="ml-1 text-xs text-amber-400">({hn.reserved} khóa)</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center border-l border-slate-700 bg-violet-950/10">
                      <span className="font-semibold text-violet-300">{hcm.available}</span>
                      {hcm.reserved > 0 && (
                        <span className="ml-1 text-xs text-amber-400">({hcm.reserved} khóa)</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
