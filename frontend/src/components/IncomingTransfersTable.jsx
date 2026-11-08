// frontend/src/components/IncomingTransfersTable.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function IncomingTransfersTable({ currentBranch, onActionSuccess }) {
  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const branchName = currentBranch === 'HN' ? 'Kho Hà Nội' : 'Kho TP.HCM';

  const [incoming, setIncoming] = useState([]);
  const [loadingId, setLoadingId] = useState(null);
  const [rejectReason, setRejectReason] = useState('Kho đầy hoặc hàng không đúng quy cách');
  const [rejectModalId, setRejectModalId] = useState(null);

  const fetchIncoming = async () => {
    try {
      const data = await api.getIncomingTransfers(branchUrl);
      setIncoming(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchIncoming();
    const timer = setInterval(fetchIncoming, 2500);
    return () => clearInterval(timer);
  }, [currentBranch]);

  const handleConfirm = async (transferId) => {
    setLoadingId(transferId);
    try {
      await api.confirmTransfer(branchUrl, transferId);
      await fetchIncoming();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      alert(`Lỗi phê duyệt: ${err.message}`);
    } finally {
      setLoadingId(null);
    }
  };

  const handleReject = async (transferId) => {
    setLoadingId(transferId);
    try {
      await api.rejectTransfer(branchUrl, transferId, rejectReason);
      setRejectModalId(null);
      await fetchIncoming();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      alert(`Lỗi từ chối: ${err.message}`);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-5 mt-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-slate-100 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-5 bg-cyan-600 rounded-sm"></span>
            <h3 className="text-base font-bold text-slate-800">
              Kiện Hàng Đang Vận Chuyển Đến ({branchName})
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 ml-4">
            Các kiện hàng điều chuyển từ chi nhánh khác chờ thủ kho phê duyệt hoặc từ chối để kích hoạt Rollback
          </p>
        </div>
        <button
          onClick={fetchIncoming}
          className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors flex items-center gap-1.5 self-start sm:self-auto font-medium"
        >
          <i className="fa-solid fa-arrows-rotate"></i> Làm mới
        </button>
      </div>

      {incoming.length === 0 ? (
        <div className="py-10 text-center bg-slate-50/60 rounded-xl border border-slate-100">
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-2 text-xl">
            <i className="fa-solid fa-check"></i>
          </div>
          <p className="text-sm font-semibold text-slate-700">Không có kiện hàng nào đang chờ xử lý</p>
          <p className="text-xs text-slate-400 mt-0.5">Mọi đơn điều chuyển gửi tới {branchName} đã được tiếp nhận hoàn tất.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm text-slate-600">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500 font-bold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">Mã Điều Chuyển</th>
                <th className="py-3 px-4">Kho Xuất</th>
                <th className="py-3 px-4">Sản Phẩm (SKU)</th>
                <th className="py-3 px-4 text-center">Số Lượng</th>
                <th className="py-3 px-4 text-center">Trạng Thái</th>
                <th className="py-3 px-4 text-center">Hành Động Phân Tán</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-sans">
              {incoming.map(item => (
                <tr key={item.transfer_id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-blue-600 text-xs">
                    {item.transfer_id.substring(0, 13)}...
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-800">
                    Kho {item.source_branch}
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-slate-700">{item.sku}</td>
                  <td className="py-3.5 px-4 text-center font-bold text-slate-800 text-base">
                    {item.quantity}
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-cyan-50 text-cyan-700 border border-cyan-200 animate-pulse">
                      CHỜ DUYỆT
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => handleConfirm(item.transfer_id)}
                        disabled={loadingId === item.transfer_id}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-2xs transition-all flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <i className="fa-solid fa-check"></i>
                        Nhận hàng
                      </button>
                      <button
                        onClick={() => setRejectModalId(item.transfer_id)}
                        disabled={loadingId === item.transfer_id}
                        className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-2xs transition-all flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <i className="fa-solid fa-xmark"></i>
                        Từ chối (Rollback)
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal xác nhận Từ chối / Rollback */}
      {rejectModalId && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mb-3 text-xl">
              <i className="fa-solid fa-triangle-exclamation"></i>
            </div>
            <h4 className="text-base font-bold text-slate-800 mb-1">
              Kích hoạt Giao dịch Bù trừ (Saga Rollback)
            </h4>
            <p className="text-xs text-slate-500 mb-4">
              Khi từ chối nhận hàng, hệ thống phát lệnh <code className="bg-slate-100 text-slate-700 font-mono px-1 py-0.5 rounded">CMD_RELEASE_STOCK</code> để tự động hoàn trả toàn bộ số hàng bị tạm giữ về kho nguồn ban đầu.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Lý do từ chối:</label>
              <input
                type="text"
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-rose-500 focus:bg-white"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setRejectModalId(null)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50"
              >
                Hủy bỏ
              </button>
              <button
                onClick={() => handleReject(rejectModalId)}
                className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-xs font-bold text-white shadow-sm"
              >
                Xác nhận Từ Chối & Hoàn Tác
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
