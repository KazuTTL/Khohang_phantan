// frontend/src/components/IncomingTransfersTable.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function IncomingTransfersTable({ currentBranch, onActionSuccess }) {
  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
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
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg mt-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-truck-ramp-box text-cyan-400"></i>
            Kiện Hàng Chờ Nhập Kho Tại {currentBranch === 'HN' ? 'Kho Hà Nội' : 'Kho TP.HCM'}
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Các kiện hàng điều chuyển do Saga điều phối đang trên đường đến chi nhánh hiện tại.
          </p>
        </div>
        <button
          onClick={fetchIncoming}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
        >
          <i className="fa-solid fa-rotate-right mr-1"></i> Làm mới
        </button>
      </div>

      {incoming.length === 0 ? (
        <div className="py-8 text-center bg-slate-900/40 rounded-lg border border-slate-700/50">
          <i className="fa-solid fa-circle-check text-slate-600 text-3xl mb-2"></i>
          <p className="text-sm text-slate-400">Hiện không có kiện hàng nào đang chờ xử lý tại chi nhánh này.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-3 px-4">Mã Điều Chuyển</th>
                <th className="py-3 px-4">Kho Xuất Phát</th>
                <th className="py-3 px-4">Hàng Hóa (SKU)</th>
                <th className="py-3 px-4 text-center">Số Lượng</th>
                <th className="py-3 px-4 text-center">Trạng Thái</th>
                <th className="py-3 px-4 text-center">Thao Tác Phân Tán</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60 font-sans">
              {incoming.map(item => (
                <tr key={item.transfer_id} className="hover:bg-slate-700/30">
                  <td className="py-3 px-4 font-mono text-xs text-cyan-300">{item.transfer_id.substring(0, 13)}...</td>
                  <td className="py-3 px-4 font-semibold text-slate-200">Kho {item.source_branch}</td>
                  <td className="py-3 px-4 font-mono font-medium text-amber-300">{item.sku}</td>
                  <td className="py-3 px-4 text-center font-bold text-white text-base">{item.quantity}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-950/60 text-cyan-300 border border-cyan-500/30 animate-pulse">
                      CHỜ PHÊ DUYỆT
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => handleConfirm(item.transfer_id)}
                        disabled={loadingId === item.transfer_id}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-all flex items-center gap-1"
                      >
                        <i className="fa-solid fa-check"></i>
                        Xác nhận Nhận hàng
                      </button>
                      <button
                        onClick={() => setRejectModalId(item.transfer_id)}
                        disabled={loadingId === item.transfer_id}
                        className="px-3 py-1.5 rounded-lg bg-rose-700 hover:bg-rose-600 text-white text-xs font-semibold shadow-md transition-all flex items-center gap-1"
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

      {/* Modal xác nhận Từ chối */}
      {rejectModalId && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 max-w-md w-full shadow-2xl">
            <h4 className="text-base font-bold text-rose-400 mb-2 flex items-center gap-2">
              <i className="fa-solid fa-triangle-exclamation"></i>
              Kích hoạt Giao dịch Bù trừ (Saga Rollback)
            </h4>
            <p className="text-xs text-slate-300 mb-3">
              Khi từ chối nhận hàng, hệ thống sẽ phát lệnh <code className="bg-slate-900 px-1 py-0.5 rounded text-rose-300">CMD_RELEASE_STOCK</code> để hoàn trả toàn bộ số hàng bị tạm giữ về kho nguồn.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-medium text-slate-400 mb-1">Lý do từ chối:</label>
              <input
                type="text"
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-rose-500"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setRejectModalId(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs text-slate-300"
              >
                Hủy bỏ
              </button>
              <button
                onClick={() => handleReject(rejectModalId)}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-xs font-semibold text-white shadow-lg"
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
