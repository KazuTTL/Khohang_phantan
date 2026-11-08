// frontend/src/components/NodeStatusBanner.jsx
import React from 'react';

export default function NodeStatusBanner({ nodesStatus, onRefresh }) {
  const nodes = [
    { 
      id: 'hq', 
      name: 'Trụ sở chính (HQ Node)', 
      port: 8000, 
      role: 'Saga Coordinator • Master DB', 
      online: nodesStatus.hq,
      icon: 'fa-building-columns',
      color: 'blue'
    },
    { 
      id: 'hn', 
      name: 'Chi nhánh Hà Nội (Branch HN)', 
      port: 8001, 
      role: 'Node 1 • CSDL Local HN • Outbox', 
      online: nodesStatus.hn,
      icon: 'fa-warehouse',
      color: 'indigo'
    },
    { 
      id: 'hcm', 
      name: 'Chi nhánh TP.HCM (Branch HCM)', 
      port: 8002, 
      role: 'Node 2 • CSDL Local HCM • Outbox', 
      online: nodesStatus.hcm,
      icon: 'fa-truck-ramp-box',
      color: 'cyan'
    },
  ];

  const onlineCount = Object.values(nodesStatus).filter(Boolean).length;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-4 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-3 border-b border-slate-100 gap-2">
        <div className="flex items-center gap-2.5">
          <span className="flex h-2.5 w-2.5 relative">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${onlineCount === 3 ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${onlineCount === 3 ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
          </span>
          <h2 className="text-sm font-bold text-slate-800 tracking-tight flex items-center gap-2">
            Trạng thái Hạ tầng Cụm Phân tán (Multi-Node Cluster)
          </h2>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            {onlineCount}/3 Nodes Hoạt động
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Tự động đồng bộ mỗi 3s</span>
          {onRefresh && (
            <button 
              onClick={onRefresh}
              className="text-slate-500 hover:text-blue-600 p-1.5 rounded-lg hover:bg-slate-50 transition-colors"
              title="Làm mới trạng thái"
            >
              <i className="fa-solid fa-arrows-rotate text-xs"></i>
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {nodes.map(n => (
          <div 
            key={n.id} 
            className={`flex items-center justify-between p-3.5 rounded-lg border transition-all ${
              n.online 
                ? 'bg-white border-slate-200 hover:border-blue-300 hover:shadow-sm' 
                : 'bg-rose-50/40 border-rose-200'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                n.online ? 'bg-blue-50 text-blue-600' : 'bg-rose-100 text-rose-600'
              }`}>
                <i className={`fa-solid ${n.icon} text-sm`}></i>
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-800 text-xs sm:text-sm">{n.name}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">{n.role}</p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold border border-slate-200">
                :{n.port}
              </span>
              <div className="mt-1">
                {n.online ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                    ONLINE
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                    OFFLINE
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
