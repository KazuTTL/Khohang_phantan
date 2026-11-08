// frontend/src/components/GlobalStockTable.jsx
import React, { useState } from 'react';

export default function GlobalStockTable({ globalStock, loading, onRefresh }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredStock = globalStock.filter(p => 
    p.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sku.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 overflow-hidden">
      {/* Table Header Controls */}
      <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-5 bg-blue-600 rounded-sm"></span>
            <h3 className="text-base font-bold text-slate-800">
              Bảng Tồn Kho Toàn Cục (HQ Snapshot)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 ml-4">
            Dữ liệu tổng hợp từ các chi nhánh qua Message Broker (Eventual Consistency)
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="relative">
            <i className="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
            <input 
              type="text" 
              placeholder="Tìm kiếm SKU, tên hàng..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white w-48 sm:w-60 transition-all"
            />
          </div>
          <button
            onClick={onRefresh}
            className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors flex items-center gap-1.5 shadow-2xs font-medium"
          >
            <i className={`fa-solid fa-rotate-right ${loading ? 'animate-spin' : ''}`}></i>
            <span className="hidden sm:inline">Làm mới</span>
          </button>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs sm:text-sm text-slate-600">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 font-bold border-b border-slate-200">
            <tr>
              <th className="py-3 px-4">Mã SKU</th>
              <th className="py-3 px-4">Tên Hàng Hóa</th>
              <th className="py-3 px-3 text-center">ĐVT</th>
              <th className="py-3 px-4 text-center">Tổng Khả Dụng</th>
              <th className="py-3 px-4 text-center">Tạm Khóa (Saga)</th>
              <th className="py-3 px-4 bg-blue-50/50 text-blue-800 text-center border-l border-slate-200">
                Kho Hà Nội (HN)
              </th>
              <th className="py-3 px-4 bg-indigo-50/50 text-indigo-800 text-center border-l border-slate-200">
                Kho TP.HCM (HCM)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredStock.length === 0 ? (
              <tr>
                <td colSpan="7" className="py-12 text-center text-slate-400">
                  <i className="fa-solid fa-box-open text-3xl mb-2 text-slate-300"></i>
                  <p>Không tìm thấy sản phẩm nào phù hợp.</p>
                </td>
              </tr>
            ) : (
              filteredStock.map(p => {
                const hn = p.branches?.HN || { available: 0, reserved: 0 };
                const hcm = p.branches?.HCM || { available: 0, reserved: 0 };

                return (
                  <tr key={p.sku} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-blue-600">{p.sku}</td>
                    <td className="py-3.5 px-4 font-semibold text-slate-800">{p.product_name}</td>
                    <td className="py-3.5 px-3 text-center text-slate-500 text-xs">{p.unit}</td>
                    <td className="py-3.5 px-4 text-center">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {p.total_available}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {p.total_reserved > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          {p.total_reserved}
                        </span>
                      ) : (
                        <span className="text-slate-400 font-medium">0</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center border-l border-slate-100 bg-blue-50/10">
                      <span className="font-bold text-slate-700">{hn.available}</span>
                      {hn.reserved > 0 && (
                        <span className="ml-1 text-[11px] font-semibold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          {hn.reserved} giữ
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center border-l border-slate-100 bg-indigo-50/10">
                      <span className="font-bold text-slate-700">{hcm.available}</span>
                      {hcm.reserved > 0 && (
                        <span className="ml-1 text-[11px] font-semibold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          {hcm.reserved} giữ
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      
      {/* Table Footer Summary */}
      <div className="p-3 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 px-4">
        <span>Hiển thị {filteredStock.length} mặt hàng</span>
        <span className="font-medium">Hệ thống phân tán đồng bộ tự động qua RabbitMQ</span>
      </div>
    </div>
  );
}
