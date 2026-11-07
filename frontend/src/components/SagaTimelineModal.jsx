// frontend/src/components/SagaTimelineModal.jsx
import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export default function SagaTimelineModal({ transfers, onRefresh }) {
  const [selectedOrder, setSelectedOrder] = useState(null);

  useEffect(() => {
    if (transfers.length > 0 && !selectedOrder) {
      setSelectedOrder(transfers[0]);
    } else if (selectedOrder) {
      const updated = transfers.find(t => t.transfer_id === selectedOrder.transfer_id);
      if (updated) setSelectedOrder(updated);
    }
  }, [transfers]);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'INITIATED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-950/80 text-blue-300 border border-blue-500/30">INITIATED</span>;
      case 'RESERVED_IN_TRANSIT':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/80 text-amber-300 border border-amber-500/30 animate-pulse">IN_TRANSIT</span>;
      case 'COMPLETED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">COMPLETED</span>;
      case 'COMPENSATING':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-purple-950/80 text-purple-300 border border-purple-500/30 animate-bounce">COMPENSATING</span>;
      case 'CANCELLED_ROLLED_BACK':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-950/80 text-rose-300 border border-rose-500/30">ROLLED_BACK</span>;
      case 'FAILED':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-red-950/80 text-red-300 border border-red-500/30">FAILED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-400">{status}</span>;
    }
  };

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg mt-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-timeline text-purple-400"></i>
            Tiến Trình Giao Dịch Phân Tán (Saga Orchestration Timeline)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Mô hình hóa vòng đời trạng thái và cơ chế bù trừ tự động (Compensating Transaction) khi phát sinh lỗi
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
        >
          <i className="fa-solid fa-arrows-rotate mr-1"></i> Làm mới đơn
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Danh sách đơn chuyển */}
        <div className="lg:col-span-5 max-h-96 overflow-y-auto space-y-2 pr-1">
          {transfers.length === 0 ? (
            <p className="p-4 text-center text-xs text-slate-500 bg-slate-900/40 rounded-lg">
              Chưa có đơn chuyển nào được tạo.
            </p>
          ) : (
            transfers.map(t => (
              <div
                key={t.transfer_id}
                onClick={() => setSelectedOrder(t)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedOrder?.transfer_id === t.transfer_id
                    ? 'bg-purple-950/30 border-purple-500 shadow-md shadow-purple-950/30'
                    : 'bg-slate-900/40 border-slate-700/60 hover:bg-slate-700/30'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-semibold text-slate-200">
                    {t.source_branch} ➔ {t.dest_branch}
                  </span>
                  {getStatusBadge(t.saga_status)}
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span className="font-mono text-amber-300/90">{t.sku}</span>
                  <span className="font-bold text-white">SL: {t.quantity}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1 truncate">
                  ID: {t.transfer_id}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Thanh trực quan tiến trình Saga */}
        <div className="lg:col-span-7 bg-slate-900/70 p-5 rounded-xl border border-slate-700/80 flex flex-col justify-between">
          {selectedOrder ? (
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-700/80 mb-4">
                <div>
                  <h4 className="text-sm font-bold text-white">
                    Chi tiết Luồng Saga: <span className="text-purple-300 font-mono">{selectedOrder.transfer_id.substring(0, 16)}...</span>
                  </h4>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Chuyển {selectedOrder.quantity} {selectedOrder.sku} từ Kho {selectedOrder.source_branch} sang Kho {selectedOrder.dest_branch}
                  </p>
                </div>
                <div>{getStatusBadge(selectedOrder.saga_status)}</div>
              </div>

              {/* Sơ đồ trạng thái từng bước */}
              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-700">
                {/* Bước 1: Khởi tạo */}
                <div className="relative">
                  <span className="absolute -left-6 top-0 w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center text-[9px] text-white font-bold">
                    1
                  </span>
                  <h5 className="text-xs font-bold text-slate-200">HQ: Khởi tạo Lệnh (INITIATED)</h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Lưu bản ghi vào <code className="text-indigo-300">DB_HQ</code>, phát <code className="text-amber-300">cmd.transfer.reserve.{selectedOrder.source_branch}</code> qua RabbitMQ.
                  </p>
                </div>

                {/* Bước 2: Khóa giữ kho nguồn */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ${
                    ['RESERVED_IN_TRANSIT', 'COMPLETED', 'COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status)
                      ? 'bg-emerald-500'
                      : selectedOrder.saga_status === 'FAILED'
                      ? 'bg-red-500'
                      : 'bg-slate-600'
                  }`}>
                    2
                  </span>
                  <h5 className="text-xs font-bold text-slate-200">
                    Kho {selectedOrder.source_branch}: Khóa Giữ Hàng (Reserve Stock)
                  </h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {selectedOrder.saga_status === 'FAILED' ? (
                      <span className="text-red-400 font-semibold">
                        Thất bại: Không đủ tồn kho khả dụng để tạm giữ ({selectedOrder.error_reason || 'Out of stock'}).
                      </span>
                    ) : ['RESERVED_IN_TRANSIT', 'COMPLETED', 'COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status) ? (
                      <span className="text-emerald-400 font-semibold">
                        Đã khóa thành công {selectedOrder.quantity} sản phẩm. Tồn khả dụng giảm, tạm giữ tăng.
                      </span>
                    ) : (
                      'Đang chờ kho nguồn xác nhận khóa hàng...'
                    )}
                  </p>
                </div>

                {/* Bước 3: Vận chuyển & Kho đích tiếp nhận */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ${
                    selectedOrder.saga_status === 'COMPLETED'
                      ? 'bg-emerald-500'
                      : ['COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status)
                      ? 'bg-purple-500'
                      : selectedOrder.saga_status === 'RESERVED_IN_TRANSIT'
                      ? 'bg-amber-400 animate-pulse'
                      : 'bg-slate-600'
                  }`}>
                    3
                  </span>
                  <h5 className="text-xs font-bold text-slate-200">
                    Kho {selectedOrder.dest_branch}: Tiếp Nhận & Phê Duyệt
                  </h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {selectedOrder.saga_status === 'COMPLETED' ? (
                      <span className="text-emerald-400 font-semibold">
                        Thủ kho đích đã bấm "Xác nhận nhận hàng". Tồn khả dụng tại kho {selectedOrder.dest_branch} đã tăng thêm {selectedOrder.quantity}!
                      </span>
                    ) : ['COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status) ? (
                      <span className="text-rose-400 font-semibold">
                        Thủ kho đích đã bấm "Từ chối nhận hàng" ({selectedOrder.error_reason}).
                      </span>
                    ) : selectedOrder.saga_status === 'RESERVED_IN_TRANSIT' ? (
                      <span className="text-amber-300 font-semibold">
                        Kiện hàng đang chờ thủ kho {selectedOrder.dest_branch} bấm Xác nhận hoặc Từ chối tại mục "Kiện Hàng Chờ Nhập Kho".
                      </span>
                    ) : (
                      'Chưa đến bước này'
                    )}
                  </p>
                </div>

                {/* Bước 4: Hoàn tất hoặc Bù trừ Rollback */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ${
                    selectedOrder.saga_status === 'COMPLETED'
                      ? 'bg-emerald-500'
                      : selectedOrder.saga_status === 'CANCELLED_ROLLED_BACK'
                      ? 'bg-rose-500'
                      : selectedOrder.saga_status === 'COMPENSATING'
                      ? 'bg-purple-500 animate-spin'
                      : 'bg-slate-600'
                  }`}>
                    4
                  </span>
                  <h5 className="text-xs font-bold text-slate-200">
                    Kết Thúc Chuỗi Saga: Hoàn Tất hoặc Bù Trừ (Compensating Transaction)
                  </h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {selectedOrder.saga_status === 'COMPLETED' ? (
                      <span className="text-emerald-300">
                        Giao dịch thành công hoàn hảo. Kho nguồn đã tất toán trừ hẳn hàng tạm giữ.
                      </span>
                    ) : selectedOrder.saga_status === 'CANCELLED_ROLLED_BACK' ? (
                      <span className="text-rose-300 font-semibold">
                        GIAO DỊCH BÙ TRỪ THÀNH CÔNG: Đã phát lệnh CMD_RELEASE_STOCK, hoàn trả lại đầy đủ {selectedOrder.quantity} sản phẩm cho kho {selectedOrder.source_branch}. Hệ thống nhất quán dữ liệu tuyệt đối!
                      </span>
                    ) : selectedOrder.saga_status === 'COMPENSATING' ? (
                      <span className="text-purple-300 animate-pulse font-semibold">
                        Đang phát lệnh bù trừ CMD_RELEASE_STOCK để hoàn trả hàng về kho nguồn...
                      </span>
                    ) : (
                      'Chưa hoàn tất'
                    )}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-center text-xs text-slate-500 py-12">
              Vui lòng chọn 1 đơn chuyển từ danh sách bên trái để theo dõi tiến trình.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
