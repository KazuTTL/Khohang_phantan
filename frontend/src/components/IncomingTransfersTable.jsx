// frontend/src/components/IncomingTransfersTable.jsx
import React, { useState, useEffect } from 'react';
import { api, HN_URL, HCM_URL } from '../api/client';

export default function IncomingTransfersTable({ currentBranch, currentUser, onActionSuccess }) {
  const [incoming, setIncoming] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rejectId, setRejectId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [actionMsg, setActionMsg] = useState(null);

  const branchUrl = currentBranch === 'HN' ? HN_URL : HCM_URL;
  const isStaffOnly = currentUser?.role === 'BRANCH_STAFF';

  const fetchIncoming = async () => {
    try {
      const data = await api.getIncomingTransfers(branchUrl);
      setIncoming(data);
    } catch (err) {
      console.error('Lỗi tải kiện hàng đến:', err);
    }
  };

  useEffect(() => {
    fetchIncoming();
    const timer = setInterval(fetchIncoming, 3000);
    return () => clearInterval(timer);
  }, [currentBranch]);

  const handleConfirm = async (transferId) => {
    setLoading(true);
    setActionMsg(null);
    try {
      const res = await api.confirmTransfer(branchUrl, transferId);
      setActionMsg({ type: 'success', text: res.message });
      fetchIncoming();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (e) => {
    e.preventDefault();
    if (!rejectId) return;
    setLoading(true);
    setActionMsg(null);
    try {
      const res = await api.rejectTransfer(branchUrl, rejectId, rejectReason || 'Kho đích từ chối nhận hàng');
      setActionMsg({ type: 'warning', text: res.message });
      setRejectId(null);
      setRejectReason('');
      fetchIncoming();
      if (onActionSuccess) onActionSuccess();
    } catch (err) {
      setActionMsg({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <i className="fa-solid fa-truck-ramp-box text-amber-600"></i>
            Kiện hàng Điều chuyển Chờ Nhập Kho ({currentBranch})
            {incoming.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-[11px] font-bold">
                {incoming.length} chờ duyệt
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Xác nhận nhận hàng để tất toán Saga, hoặc Từ chối để kích hoạt hoàn tác bù trừ về kho xuất
          </p>
        </div>
        <button
          onClick={fetchIncoming}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium"
        >
          <i className="fa-solid fa-rotate mr-1"></i> Làm mới
        </button>
      </div>

      {isStaffOnly && (
        <div className="mb-3 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center gap-2">
          <i className="fa-solid fa-lock text-amber-600"></i>
          <span>Tài khoản <strong>Thủ kho (BRANCH_STAFF)</strong> chỉ được xem trạng thái. Chỉ <strong>Trưởng kho (BRANCH_MANAGER)</strong> mới có thẩm quyền Phê duyệt hoặc Từ chối kiện hàng Saga.</span>
        </div>
      )}

      {actionMsg && (
        <div className={`p-3 rounded-lg text-xs mb-4 border ${
          actionMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
          actionMsg.type === 'warning' ? 'bg-amber-50 text-amber-800 border-amber-200' :
          'bg-rose-50 text-rose-800 border-rose-200'
        }`}>
          {actionMsg.text}
        </div>
      )}

      {rejectId && (
        <form onSubmit={handleReject} className="mb-4 p-4 rounded-xl bg-rose-50 border border-rose-200">
          <p className="text-xs font-bold text-rose-800 mb-2">
            Nhập lý do từ chối nhận kiện hàng {rejectId.slice(0, 8)}... (Kích hoạt Saga Rollback):
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="VD: Bao bì hư hỏng, kho quá tải kệ..."
              className="flex-1 min-w-[200px] bg-white border border-rose-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:border-rose-500"
              required
            />
            <button type="submit" disabled={loading} className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold">
              Xác nhận Từ chối
            </button>
            <button type="button" onClick={() => setRejectId(null)} className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs">
              Hủy
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">Mã Kiện Hàng</th>
              <th className="py-2.5 px-3">Từ Kho Nguồn</th>
              <th className="py-2.5 px-3">SKU</th>
              <th className="py-2.5 px-3 text-center">Số lượng</th>
              <th className="py-2.5 px-3 text-right">Thao tác Phê duyệt</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-xs">
            {incoming.length === 0 ? (
              <tr>
                <td colSpan="5" className="py-8 text-center text-slate-400">
                  Hiện không có kiện hàng nào đang chuyển đến kho {currentBranch}.
                </td>
              </tr>
            ) : (
              incoming.map((item) => (
                <tr key={item.transfer_id} className="hover:bg-slate-50">
                  <td className="py-2.5 px-3 font-mono text-slate-600">{item.transfer_id.slice(0, 8)}...</td>
                  <td className="py-2.5 px-3 font-semibold text-slate-800">{item.source_branch}</td>
                  <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">{item.sku}</td>
                  <td className="py-2.5 px-3 text-center font-bold text-slate-900 tabular-nums">{item.quantity}</td>
                  <td className="py-2.5 px-3 text-right space-x-2">
                    <button
                      onClick={() => handleConfirm(item.transfer_id)}
                      disabled={loading || isStaffOnly}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-[11px] disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <i className="fa-solid fa-check mr-1"></i> Xác nhận Nhập kho
                    </button>
                    <button
                      onClick={() => setRejectId(item.transfer_id)}
                      disabled={loading || isStaffOnly}
                      className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold text-[11px] disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <i className="fa-solid fa-xmark mr-1"></i> Từ chối
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
