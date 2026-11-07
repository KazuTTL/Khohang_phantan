// frontend/src/components/GlobalStockTable.jsx
import React from 'react';

export default function GlobalStockTable({ globalStock, loading, onRefresh }) {
  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-boxes-stacked text-amber-400"></i>
            Tồn kho Toàn cục Hệ thống (HQ Read-Model Snapshot)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Đồng bộ bất đồng bộ từ các chi nhánh thông qua RabbitMQ Broker (Eventual Consistency)
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors flex items-center gap-1.5"
        >
          <i className={`fa-solid fa-rotate-right ${loading ? 'animate-spin' : ''}`}></i>
          Làm mới
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-700">
            <tr>
              <th className="py-3 px-4">Mã SKU</th>
              <th className="py-3 px-4">Tên Hàng Hóa</th>
              <th className="py-3 px-4 text-center">ĐVT</th>
              <th className="py-3 px-4 text-center">Tổng Khả Dụng</th>
              <th className="py-3 px-4 text-center">Tổng Tạm Khóa</th>
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
                <td colSpan="7" className="py-8 text-center text-slate-500">
                  Chưa có dữ liệu snapshot hoặc HQ Service đang offline.
                </td>
              </tr>
            ) : (
              globalStock.map(p => {
                const hn = p.branches?.HN || { available: 0, reserved: 0 };
                const hcm = p.branches?.HCM || { available: 0, reserved: 0 };

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
