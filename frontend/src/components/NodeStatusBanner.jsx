// frontend/src/components/NodeStatusBanner.jsx
import React from 'react';

export default function NodeStatusBanner({ nodesStatus }) {
  const nodes = [
    { id: 'hq', name: 'Node Trụ sở chính (HQ)', port: 8000, role: 'Saga Coordinator / Master DB', online: nodesStatus.hq },
    { id: 'hn', name: 'Chi nhánh Hà Nội (HN)', port: 8001, role: 'Branch Node 1 / DB_Branch_HN', online: nodesStatus.hn },
    { id: 'hcm', name: 'Chi nhánh TP.HCM (HCM)', port: 8002, role: 'Branch Node 2 / DB_Branch_HCM', online: nodesStatus.hcm },
  ];

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-4 mb-6 shadow-lg backdrop-blur">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase flex items-center gap-2">
          <i className="fa-solid fa-network-wired text-indigo-400"></i>
          Trạng thái Cụm Hệ thống Phân tán (Multi-Node Cluster)
        </h2>
        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-700/60 text-slate-300">
          Tự động cập nhật mỗi 3s
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {nodes.map(n => (
          <div 
            key={n.id} 
            className={`flex items-center justify-between p-3.5 rounded-lg border transition-all ${
              n.online 
                ? 'bg-slate-900/60 border-emerald-500/40 shadow-emerald-950/20 shadow-md' 
                : 'bg-red-950/20 border-red-500/30'
            }`}
          >
            <div>
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${n.online ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`}></span>
                <span className="font-semibold text-slate-200 text-sm">{n.name}</span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">{n.role}</p>
            </div>
            <div className="text-right">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                :{n.port}
              </span>
              <div className="mt-1">
                {n.online ? (
                  <span className="text-xs font-medium text-emerald-400">ONLINE</span>
                ) : (
                  <span className="text-xs font-medium text-red-400">DISCONNECTED</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
