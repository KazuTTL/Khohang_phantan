// frontend/src/components/NetworkChaosSimulator.jsx
import React, { useState } from 'react';

export default function NetworkChaosSimulator() {
  const [activeScenario, setActiveScenario] = useState(null);

  const scenarios = [
    {
      id: 'local_autonomy',
      title: 'Tự trị Cục bộ khi Mất kết nối Trụ sở (Local Autonomy)',
      icon: 'fa-network-wired',
      badge: 'High Availability',
      desc: 'Khi Trụ sở chính (HQ 8000) hoặc Message Broker tạm dừng, Chi nhánh vẫn tiếp tục xuất bán và nhập hàng bình thường trên CSDL cục bộ. Biến động được lưu vào bảng Outbox_Events và tự động đẩy đi khi kết nối trở lại.',
      steps: [
        'Chi nhánh thực hiện xuất bán lẻ tại chỗ.',
        'CSDL ghi nhận trừ tồn và tạo bản ghi Outbox trong cùng Local Transaction.',
        'Dữ liệu an toàn tuyệt đối, không có hiện tượng treo luồng (Non-blocking).'
      ]
    },
    {
      id: 'node_crash',
      title: 'Khôi phục Kiện hàng sau khi Sập nguồn (Crash Recovery)',
      icon: 'fa-server',
      badge: 'Data Durability',
      desc: 'Kiện hàng điều chuyển từ kho nguồn được lưu bền vững vào bảng Incoming_Transfers của CSDL đích ngay khi tới. Nếu container chi nhánh bị crash/restart đột ngột, toàn bộ kiện hàng chờ duyệt vẫn nguyên vẹn.',
      steps: [
        'Lệnh CMD_IMPORT_TRANSFER gửi tới kho đích.',
        'Kho đích lập tức lưu bản ghi vào CSDL thay vì giữ trên bộ nhớ RAM tạm.',
        'Sau khi khởi động lại, danh sách chờ duyệt được nạp lại 100% từ CSDL.'
      ]
    },
    {
      id: 'saga_timeout',
      title: 'Cơ chế Hết hạn Giao dịch (Saga Coordinator Timeout)',
      icon: 'fa-stopwatch',
      badge: 'Self-Healing',
      desc: 'Nếu kho đích bị đứt cáp hoặc treo vô thời hạn không phản hồi, tiến trình Saga Timeout Worker tại Trụ sở sẽ tự động phát hiện và kích hoạt giao dịch bù trừ (Compensating Transaction) để giải phóng tồn kho.',
      steps: [
        'Đơn Saga chuyển trạng thái RESERVED_IN_TRANSIT.',
        'Saga Timeout Worker quét chu kỳ 5 giây phát hiện đơn quá hạn.',
        'Tự động gửi CMD_RELEASE_STOCK hoàn trả lại available_qty cho kho nguồn.'
      ]
    }
  ];

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-flask-vial text-indigo-400"></i>
            Bộ Giả Lập & Chứng Minh Đặc Tính Phân Tán (Distributed System Properties)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Minh họa trực quan các cơ chế chịu lỗi, tự phục hồi và tính nhất quán eventual consistency phục vụ bảo vệ đồ án.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarios.map(sc => (
          <div
            key={sc.id}
            onClick={() => setActiveScenario(activeScenario === sc.id ? null : sc.id)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              activeScenario === sc.id
                ? 'bg-indigo-950/40 border-indigo-500 shadow-md shadow-indigo-950/50'
                : 'bg-slate-900/50 border-slate-700/80 hover:border-slate-600'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-sm">
                <i className={`fa-solid ${sc.icon}`}></i>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {sc.badge}
              </span>
            </div>
            <h4 className="text-xs font-bold text-slate-100 mb-1.5">{sc.title}</h4>
            <p className="text-[11px] text-slate-400 leading-relaxed mb-3">{sc.desc}</p>
            {activeScenario === sc.id && (
              <div className="mt-3 pt-3 border-t border-indigo-500/30 text-[11px] text-indigo-200 space-y-1">
                <p className="font-semibold text-indigo-300">Quy trình thực tế:</p>
                {sc.steps.map((st, idx) => (
                  <p key={idx} className="flex items-start gap-1.5">
                    <span className="text-indigo-400 font-bold">{idx + 1}.</span>
                    <span>{st}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
