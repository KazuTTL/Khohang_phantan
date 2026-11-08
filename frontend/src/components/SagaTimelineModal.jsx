// frontend/src/components/SagaTimelineModal.jsx
import React, { useState, useEffect } from 'react';

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
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">INITIATED</span>;
      case 'RESERVED_IN_TRANSIT':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">IN_TRANSIT</span>;
      case 'COMPLETED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">COMPLETED</span>;
      case 'COMPENSATING':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200 animate-bounce">COMPENSATING</span>;
      case 'CANCELLED_ROLLED_BACK':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">ROLLED_BACK</span>;
      case 'FAILED':
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">FAILED</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 mt-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-slate-100 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-5 bg-purple-600 rounded-sm"></span>
            <h3 className="text-base font-bold text-slate-800">
              Tiến Trình Giao Dịch Phân Tán (Saga Orchestration Timeline)
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 ml-4">
            Theo dõi máy trạng thái và cơ chế bù trừ tự động (Compensating Transaction) khi xảy ra sự cố
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors flex items-center gap-1.5 self-start sm:self-auto font-medium"
        >
          <i className="fa-solid fa-arrows-rotate"></i> Làm mới
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Danh sách đơn điều chuyển */}
        <div className="lg:col-span-5 max-h-[460px] overflow-y-auto space-y-2 pr-1">
          {transfers.length === 0 ? (
            <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-100 text-xs text-slate-400">
              <i className="fa-solid fa-clipboard-list text-2xl mb-1 text-slate-300"></i>
              <p>Chưa có lệnh điều chuyển nào được khởi tạo.</p>
            </div>
          ) : (
            transfers.map(t => (
              <div
                key={t.transfer_id}
                onClick={() => setSelectedOrder(t)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  selectedOrder?.transfer_id === t.transfer_id
                    ? 'bg-blue-50/50 border-blue-400 shadow-xs'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-slate-800">
                      Kho {t.source_branch}
                    </span>
                    <i className="fa-solid fa-arrow-right text-[10px] text-blue-500"></i>
                    <span className="font-bold text-xs text-slate-800">
                      Kho {t.dest_branch}
                    </span>
                  </div>
                  {getStatusBadge(t.saga_status)}
                </div>

                <div className="flex items-center justify-between text-xs text-slate-600">
                  <span className="font-mono font-bold text-blue-600">{t.sku}</span>
                  <span className="font-bold text-slate-800">SL: {t.quantity}</span>
                </div>

                <div className="text-[10px] font-mono text-slate-400 mt-1.5 truncate">
                  ID: {t.transfer_id}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Cột Chi tiết Luồng Stepper */}
        <div className="lg:col-span-7 bg-slate-50/60 p-5 rounded-xl border border-slate-200/80">
          {selectedOrder ? (
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-200/80 mb-5">
                <div>
                  <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                    Mã Saga: <span className="text-blue-700 font-mono text-xs">{selectedOrder.transfer_id}</span>
                  </h4>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Chuyển {selectedOrder.quantity} {selectedOrder.sku} từ Kho {selectedOrder.source_branch} sang Kho {selectedOrder.dest_branch}
                  </p>
                </div>
                <div>{getStatusBadge(selectedOrder.saga_status)}</div>
              </div>

              {/* Sơ đồ Stepper trực quan 4 bước */}
              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {/* Bước 1: Khởi tạo */}
                <div className="relative">
                  <span className="absolute -left-6 top-0 w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center text-[9px] text-white font-bold ring-4 ring-white shadow-2xs">
                    1
                  </span>
                  <h5 className="text-xs font-bold text-slate-800">HQ: Khởi tạo Lệnh (INITIATED)</h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Lưu bản ghi vào <code className="text-blue-700 font-medium bg-white px-1 rounded border border-slate-200">DB_HQ</code>, phát lệnh <code className="text-blue-700 font-medium bg-white px-1 rounded border border-slate-200">cmd.transfer.reserve.{selectedOrder.source_branch}</code> qua RabbitMQ.
                  </p>
                </div>

                {/* Bước 2: Khóa giữ kho nguồn */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ring-4 ring-white shadow-2xs ${
                    ['RESERVED_IN_TRANSIT', 'COMPLETED', 'COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status)
                      ? 'bg-emerald-500'
                      : selectedOrder.saga_status === 'FAILED'
                      ? 'bg-rose-500'
                      : 'bg-slate-300'
                  }`}>
                    2
                  </span>
                  <h5 className="text-xs font-bold text-slate-800">
                    Kho {selectedOrder.source_branch}: Khóa Giữ Hàng (Reserve Stock)
                  </h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {selectedOrder.saga_status === 'FAILED' ? (
                      <span className="text-rose-600 font-semibold">
                        Thất bại: Không đủ tồn kho khả dụng để tạm giữ ({selectedOrder.error_reason || 'Hết hàng'}).
                      </span>
                    ) : ['RESERVED_IN_TRANSIT', 'COMPLETED', 'COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status) ? (
                      <span className="text-emerald-700 font-semibold">
                        Đã khóa thành công {selectedOrder.quantity} sản phẩm. Tồn khả dụng trừ {selectedOrder.quantity}, tạm giữ tăng {selectedOrder.quantity}.
                      </span>
                    ) : (
                      'Đang chờ kho nguồn xác nhận khóa hàng...'
                    )}
                  </p>
                </div>

                {/* Bước 3: Vận chuyển & Kho đích tiếp nhận */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ring-4 ring-white shadow-2xs ${
                    selectedOrder.saga_status === 'COMPLETED'
                      ? 'bg-emerald-500'
                      : ['COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status)
                      ? 'bg-purple-600'
                      : selectedOrder.saga_status === 'RESERVED_IN_TRANSIT'
                      ? 'bg-amber-500 animate-pulse'
                      : 'bg-slate-300'
                  }`}>
                    3
                  </span>
                  <h5 className="text-xs font-bold text-slate-800">
                    Kho {selectedOrder.dest_branch}: Tiếp Nhận & Phê Duyệt
                  </h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {selectedOrder.saga_status === 'COMPLETED' ? (
                      <span className="text-emerald-700 font-semibold">
                        Thủ kho đích đã bấm "Xác nhận nhận hàng". Tồn khả dụng tại kho {selectedOrder.dest_branch} đã tăng thêm {selectedOrder.quantity}!
                      </span>
                    ) : ['COMPENSATING', 'CANCELLED_ROLLED_BACK'].includes(selectedOrder.saga_status) ? (
                      <span className="text-rose-600 font-semibold">
                        Thủ kho đích từ chối nhận hàng ({selectedOrder.error_reason}). Kích hoạt chuỗi bù trừ.
                      </span>
                    ) : selectedOrder.saga_status === 'RESERVED_IN_TRANSIT' ? (
                      <span className="text-amber-700 font-semibold">
                        Kiện hàng đang chờ thủ kho {selectedOrder.dest_branch} bấm Xác nhận hoặc Từ chối tại mục "Kiện Hàng Đang Vận Chuyển Đến".
                      </span>
                    ) : (
                      'Chưa đến bước này'
                    )}
                  </p>
                </div>

                {/* Bước 4: Hoàn tất hoặc Bù trừ Rollback */}
                <div className="relative">
                  <span className={`absolute -left-6 top-0 w-4 h-4 rounded-full flex items-center justify-center text-[9px] text-white font-bold ring-4 ring-white shadow-2xs ${
                    selectedOrder.saga_status === 'COMPLETED'
                      ? 'bg-emerald-500'
                      : selectedOrder.saga_status === 'CANCELLED_ROLLED_BACK'
                      ? 'bg-rose-500'
                      : selectedOrder.saga_status === 'COMPENSATING'
                      ? 'bg-purple-500 animate-spin'
                      : 'bg-slate-300'
                  }`}>
                    4
                  </span>
                  <h5 className="text-xs font-bold text-slate-800">
                    Kết Thúc: Hoàn Tất hoặc Bù Trừ (Compensating Transaction)
                  </h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {selectedOrder.saga_status === 'COMPLETED' ? (
                      <span className="text-emerald-700 font-medium">
                        Giao dịch thành công hoàn hảo. Kho nguồn đã tất toán trừ hẳn số lượng tạm giữ.
                      </span>
                    ) : selectedOrder.saga_status === 'CANCELLED_ROLLED_BACK' ? (
                      <span className="text-rose-700 font-semibold">
                        GIAO DỊCH BÙ TRỪ THÀNH CÔNG: Đã phát lệnh <code className="bg-white px-1 rounded border border-rose-200">CMD_RELEASE_STOCK</code>, hoàn trả đầy đủ {selectedOrder.quantity} sản phẩm về lại kho {selectedOrder.source_branch}. Hệ thống nhất quán dữ liệu tuyệt đối!
                      </span>
                    ) : selectedOrder.saga_status === 'COMPENSATING' ? (
                      <span className="text-purple-700 animate-pulse font-semibold">
                        Đang phát lệnh bù trừ CMD_RELEASE_STOCK để hoàn trả hàng về kho nguồn...
                      </span>
                    ) : (
                      'Chưa kết thúc'
                    )}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-xs text-slate-400 py-16">
              <i className="fa-solid fa-hand-pointer text-2xl mb-2 text-slate-300"></i>
              <p>Chọn một đơn chuyển từ danh sách bên trái để theo dõi tiến trình Saga.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
