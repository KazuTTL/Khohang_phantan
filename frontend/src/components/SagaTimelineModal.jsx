// frontend/src/components/SagaTimelineModal.jsx
import React, { useState } from 'react';

export default function SagaTimelineModal({ transfers, onRefresh }) {
  const [selectedSaga, setSelectedSaga] = useState(null);

  const getStatusBadge = (status) => {
    const map = {
      INITIATED: { text: 'Khởi tạo', cls: 'bg-sky-50 text-sky-700 border-sky-200', icon: 'fa-hourglass-start' },
      RESERVED_IN_TRANSIT: { text: 'Đang vận chuyển (Tạm khóa)', cls: 'bg-amber-50 text-amber-700 border-amber-200', icon: 'fa-truck-fast' },
      COMPLETED: { text: 'Hoàn tất (COMPLETED)', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: 'fa-circle-check' },
      COMPENSATING: { text: 'Đang bù trừ hoàn tác', cls: 'bg-orange-50 text-orange-700 border-orange-200', icon: 'fa-rotate-left' },
      CANCELLED_ROLLED_BACK: { text: 'Đã hủy & Bù trừ hoàn tồn', cls: 'bg-rose-50 text-rose-700 border-rose-200', icon: 'fa-shield-halved' },
      FAILED: { text: 'Thất bại', cls: 'bg-rose-50 text-rose-700 border-rose-200', icon: 'fa-circle-xmark' }
    };
    const meta = map[status] || { text: status, cls: 'bg-slate-100 text-slate-700 border-slate-200', icon: 'fa-circle-info' };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border inline-flex items-center gap-1 ${meta.cls}`}>
        <i className={`fa-solid ${meta.icon}`}></i> {meta.text}
      </span>
    );
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <i className="fa-solid fa-diagram-project text-indigo-600"></i>
            Nhật ký Giao dịch Điều chuyển Phân tán (Saga Orchestration Log)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Theo dõi vòng đời giao dịch phân tán và tự động hoàn tác bù trừ khi kho đích từ chối hoặc quá hạn 60s
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium flex items-center gap-1.5"
        >
          <i className="fa-solid fa-rotate"></i> Làm mới
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">Mã Điều chuyển</th>
              <th className="py-2.5 px-3">Tuyến Kho</th>
              <th className="py-2.5 px-3">SKU</th>
              <th className="py-2.5 px-3 text-center">Số lượng</th>
              <th className="py-2.5 px-3">Trạng thái Saga</th>
              <th className="py-2.5 px-3">Chi tiết / Bù trừ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-xs">
            {transfers.length === 0 ? (
              <tr>
                <td colSpan="6" className="py-8 text-center text-slate-400">
                  Chưa có giao dịch điều chuyển nào được tạo.
                </td>
              </tr>
            ) : (
              transfers.map((t) => (
                <tr
                  key={t.transfer_id}
                  onClick={() => setSelectedSaga(t)}
                  className={`cursor-pointer transition-colors ${
                    selectedSaga?.transfer_id === t.transfer_id ? 'bg-indigo-50/70' : 'hover:bg-slate-50'
                  }`}
                >
                  <td className="py-2.5 px-3 font-mono text-slate-500 text-[11px]">
                    {t.transfer_id.slice(0, 8)}...
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-slate-800">
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px]">{t.source_branch}</span>
                    <i className="fa-solid fa-arrow-right text-[10px] text-slate-400 mx-1.5"></i>
                    <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 text-[11px]">{t.dest_branch}</span>
                  </td>
                  <td className="py-2.5 px-3 font-mono font-semibold text-indigo-700">{t.sku}</td>
                  <td className="py-2.5 px-3 text-center font-bold text-slate-900 tabular-nums">{t.quantity}</td>
                  <td className="py-2.5 px-3">{getStatusBadge(t.saga_status)}</td>
                  <td className="py-2.5 px-3 text-[11px] text-slate-500 max-w-xs truncate">
                    {t.error_reason || 'Đồng bộ bình thường'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedSaga && (
        <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
          <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-slate-200">
            <h4 className="text-xs font-bold text-slate-800">
              Tiến trình Saga: <span className="font-mono text-indigo-700">{selectedSaga.transfer_id}</span>
            </h4>
            <button onClick={() => setSelectedSaga(null)} className="text-slate-400 hover:text-slate-700 text-xs">
              <i className="fa-solid fa-xmark"></i> Đóng
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className={`p-3 rounded-lg border ${
              ['RESERVED_IN_TRANSIT', 'COMPLETED', 'CANCELLED_ROLLED_BACK', 'COMPENSATING'].includes(selectedSaga.saga_status)
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-white border-slate-200 text-slate-500'
            }`}>
              <p className="font-bold">1. Tạm khóa tại {selectedSaga.source_branch}</p>
              <p className="text-[11px] mt-1">CMD_RESERVE_STOCK &rarr; Giữ {selectedSaga.quantity} sp</p>
            </div>

            <div className={`p-3 rounded-lg border ${
              selectedSaga.saga_status === 'RESERVED_IN_TRANSIT'
                ? 'bg-amber-50 border-amber-200 text-amber-800'
                : selectedSaga.saga_status === 'COMPLETED'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : ['CANCELLED_ROLLED_BACK', 'COMPENSATING'].includes(selectedSaga.saga_status)
                    ? 'bg-rose-50 border-rose-200 text-rose-800'
                    : 'bg-white border-slate-200 text-slate-500'
            }`}>
              <p className="font-bold">2. Chờ duyệt tại {selectedSaga.dest_branch}</p>
              <p className="text-[11px] mt-1">
                {selectedSaga.saga_status === 'COMPLETED'
                  ? 'Kho đích đã xác nhận nhập kho'
                  : selectedSaga.saga_status === 'CANCELLED_ROLLED_BACK'
                    ? `Bị từ chối / Timeout: ${selectedSaga.error_reason || ''}`
                    : 'Đang chờ Trưởng kho đích xác nhận'}
              </p>
            </div>

            <div className={`p-3 rounded-lg border ${
              selectedSaga.saga_status === 'COMPLETED'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : selectedSaga.saga_status === 'CANCELLED_ROLLED_BACK'
                  ? 'bg-rose-50 border-rose-200 text-rose-800'
                  : 'bg-white border-slate-200 text-slate-500'
            }`}>
              <p className="font-bold">3. Tất toán / Bù trừ</p>
              <p className="text-[11px] mt-1">
                {selectedSaga.saga_status === 'COMPLETED'
                  ? 'Đã hoàn tất trừ kho nguồn & cộng kho đích'
                  : selectedSaga.saga_status === 'CANCELLED_ROLLED_BACK'
                    ? 'CMD_RELEASE_STOCK -> Hoàn lại kho nguồn'
                    : 'Đang đợi kết quả bước 2'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
