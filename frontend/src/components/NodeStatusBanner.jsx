// frontend/src/components/NodeStatusBanner.jsx
import React from 'react';

export default function NodeStatusBanner({ nodesStatus }) {
  const nodes = [
    {
      id: 'hq',
      name: 'Site 1: Trụ sở chính (HQ)',
      port: 8000,
      role: 'LB-HQ-Central -> Central-API-1/2',
      db: 'DB_HQ (Primary + Replica)',
      online: nodesStatus.hq,
      icon: 'fa-building-columns',
      color: 'indigo',
    },
    {
      id: 'hn',
      name: 'Site 2: Kho Hà Nội (HN)',
      port: 8001,
      role: 'LB-HN-North -> Local-App-1/2 HN',
      db: 'TON_KHO_HN (Primary + Replica)',
      online: nodesStatus.hn,
      icon: 'fa-warehouse',
      color: 'sky',
    },
    {
      id: 'hcm',
      name: 'Site 3: Kho TP.HCM (HCM)',
      port: 8002,
      role: 'LB-HCM-South -> Local-App-1/2 HCM',
      db: 'TON_KHO_HCM (Primary + Replica)',
      online: nodesStatus.hcm,
      icon: 'fa-warehouse',
      color: 'violet',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {nodes.map((n) => (
        <div
          key={n.id}
          className={`p-4 rounded-xl border bg-white shadow-xs transition-all ${
            n.online ? 'border-slate-200' : 'border-rose-200 bg-rose-50/40'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                n.online ? 'bg-indigo-50 text-indigo-600' : 'bg-rose-100 text-rose-600'
              }`}>
                <i className={`fa-solid ${n.icon} text-sm`}></i>
              </div>
              <div className="min-w-0">
                <h3 className="text-xs font-bold text-slate-900 truncate">{n.name}</h3>
                <p className="text-[11px] text-slate-500 font-mono truncate">{n.role}</p>
              </div>
            </div>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1 shrink-0 border ${
              n.online
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-rose-50 text-rose-700 border-rose-200'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${n.online ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
              {n.online ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
            <span className="font-mono truncate">{n.db}</span>
            <span className="font-mono font-semibold text-slate-700">:{n.port}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
