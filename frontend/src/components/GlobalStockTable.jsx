// frontend/src/components/GlobalStockTable.jsx
import React, { useState } from 'react';
import { api } from '../api/client';

export default function GlobalStockTable({ globalStock, loading, onRefresh }) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  // Form Thêm mới
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('Chiếc');
  const [price, setPrice] = useState(15000000);
  const [category, setCategory] = useState('Điện tử');
  const [stockHN, setStockHN] = useState(50);
  const [stockHCM, setStockHCM] = useState(30);
  const [minThreshold, setMinThreshold] = useState(10);
  const [maxThreshold, setMaxThreshold] = useState(200);

  // Form Chỉnh sửa
  const [editName, setEditName] = useState('');
  const [editUnit, setEditUnit] = useState('');
  const [editPrice, setEditPrice] = useState(0);
  const [editMinTh, setEditMinTh] = useState(10);
  const [editMaxTh, setEditMaxTh] = useState(200);

  // Search & Filter
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState(null);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setMsg(null);
    try {
      await api.createProduct({
        sku: sku.trim().toUpperCase(),
        product_name: name.trim(),
        unit: unit.trim(),
        price: parseFloat(price) || 0,
        category,
        initial_stock: {
          HN: parseInt(stockHN, 10) || 0,
          HCM: parseInt(stockHCM, 10) || 0
        },
        min_threshold: parseInt(minThreshold, 10) || 10,
        max_threshold: parseInt(maxThreshold, 10) || 200
      });
      setMsg({
        type: 'success',
        text: `Đã tạo SKU '${sku}', phân bổ tồn đầu kỳ (HN: ${stockHN}, HCM: ${stockHCM}) và phát tín hiệu đồng bộ qua RabbitMQ!`
      });
      setSku('');
      setName('');
      if (onRefresh) onRefresh();
      setTimeout(() => {
        setShowAddModal(false);
        setMsg(null);
      }, 1500);
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Lỗi khi tạo sản phẩm' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenEdit = (p) => {
    setEditingProduct(p);
    setEditName(p.product_name);
    setEditUnit(p.unit || 'Chiếc');
    setEditPrice(p.price || 0);
    setEditMinTh(10);
    setEditMaxTh(200);
    setMsg(null);
  };

  const handleUpdateProduct = async (e) => {
    e.preventDefault();
    if (!editingProduct) return;
    setSubmitting(true);
    setMsg(null);
    try {
      await api.updateProduct(editingProduct.sku, {
        product_name: editName.trim(),
        unit: editUnit.trim(),
        price: parseFloat(editPrice) || 0,
        min_threshold: parseInt(editMinTh, 10) || 10,
        max_threshold: parseInt(editMaxTh, 10) || 200
      });
      setMsg({
        type: 'success',
        text: `Đã cập nhật sản phẩm '${editingProduct.sku}' và đồng bộ thành công tới các chi nhánh!`
      });
      if (onRefresh) onRefresh();
      setTimeout(() => {
        setEditingProduct(null);
        setMsg(null);
      }, 1200);
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Lỗi khi cập nhật sản phẩm' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteProduct = async (p) => {
    const totalQty = (p.total_available || 0) + (p.total_reserved || 0);
    if (totalQty > 0) {
      alert(`Không thể xóa mặt hàng '${p.sku}' vì vẫn còn tồn kho (${totalQty} sản phẩm). Theo nguyên tắc toàn vẹn hệ thống phân tán, sản phẩm chỉ được xóa khi tồn kho ở tất cả chi nhánh bằng 0.`);
      return;
    }

    if (!window.confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn mặt hàng '${p.sku}' (${p.product_name}) khỏi toàn bộ hệ thống?`)) {
      return;
    }

    setLoadingState(true);
    try {
      await api.deleteProduct(p.sku);
      setMsg({ type: 'success', text: `Đã xóa mặt hàng '${p.sku}' và phát tín hiệu đồng bộ xóa tới toàn bộ chi nhánh!` });
      if (onRefresh) onRefresh();
      setTimeout(() => setMsg(null), 3000);
    } catch (err) {
      alert(err.message || 'Lỗi khi xóa sản phẩm');
    } finally {
      setLoadingState(false);
    }
  };

  // Helper để hiển thị loading cục bộ
  const [loadingState, setLoadingState] = useState(false);

  // Lọc sản phẩm
  const filteredStock = globalStock.filter(p => {
    const matchSearch =
      p.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.product_name.toLowerCase().includes(searchTerm.toLowerCase());

    const isLow = (p.total_available || 0) <= 20;
    if (statusFilter === 'LOW') return matchSearch && isLow;
    if (statusFilter === 'SAFE') return matchSearch && !isLow;
    return matchSearch;
  });

  return (
    <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-boxes-stacked text-amber-400"></i>
            Tồn kho Toàn cục Hệ thống (HQ Read-Model Snapshot)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Đồng bộ bất đồng bộ từ các chi nhánh thông qua RabbitMQ Broker (Eventual Consistency)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setShowAddModal(true);
              setEditingProduct(null);
              setMsg(null);
            }}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors flex items-center gap-1.5 shadow-md shadow-indigo-950/40"
          >
            <i className="fa-solid fa-plus"></i>
            Thêm Mặt Hàng Mới
          </button>
          <button
            onClick={onRefresh}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors flex items-center gap-1.5"
          >
            <i className={`fa-solid fa-rotate-right ${loading || loadingState ? 'animate-spin' : ''}`}></i>
            Làm mới
          </button>
        </div>
      </div>

      {/* Thông báo thao tác */}
      {msg && (
        <div className={`p-3 rounded-lg text-xs mb-4 flex items-center justify-between ${
          msg.type === 'success'
            ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/40'
            : 'bg-red-950/60 text-red-300 border border-red-500/40'
        }`}>
          <div className="flex items-center gap-2">
            <i className={`fa-solid ${msg.type === 'success' ? 'fa-circle-check text-emerald-400' : 'fa-circle-exclamation text-red-400'}`}></i>
            <span>{msg.text}</span>
          </div>
          <button onClick={() => setMsg(null)} className="text-slate-400 hover:text-white">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>
      )}

      {/* Modal Thêm Sản Phẩm Mới */}
      {showAddModal && (
        <div className="mb-5 p-4 bg-slate-900/95 border border-indigo-500/50 rounded-xl animate-fade-in shadow-xl">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-700">
            <h4 className="text-sm font-bold text-indigo-300 flex items-center gap-2">
              <i className="fa-solid fa-cart-plus"></i>
              Thêm Mặt Hàng Mới & Khởi Tạo Phân Bổ Tồn Kho Chi Nhánh
            </h4>
            <button
              onClick={() => setShowAddModal(false)}
              className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded"
            >
              <i className="fa-solid fa-xmark text-sm"></i>
            </button>
          </div>

          <form onSubmit={handleCreateProduct} className="space-y-3 text-xs">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              1. Thông tin hàng hóa (Master Data)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-slate-400 mb-1">Mã SKU (*)</label>
                <input
                  type="text"
                  placeholder="VD: LAPTOP-DELL-XPS15"
                  value={sku}
                  onChange={e => setSku(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-slate-400 mb-1">Tên Hàng Hóa (*)</label>
                <input
                  type="text"
                  placeholder="VD: Laptop Dell XPS 15 9530 Core i7/16GB/512GB"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Đơn vị tính</label>
                <input
                  type="text"
                  placeholder="Chiếc, Hộp, Bộ..."
                  value={unit}
                  onChange={e => setUnit(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-slate-400 mb-1">Đơn giá (VNĐ)</label>
                <input
                  type="number"
                  min="0"
                  step="10000"
                  value={price}
                  onChange={e => setPrice(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Danh mục</label>
                <input
                  type="text"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Định mức Min</label>
                <input
                  type="number"
                  min="0"
                  value={minThreshold}
                  onChange={e => setMinThreshold(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Định mức Max</label>
                <input
                  type="number"
                  min="1"
                  value={maxThreshold}
                  onChange={e => setMaxThreshold(e.target.value)}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider pt-2 border-t border-slate-800">
              2. Chỉ định Tồn Kho Đầu Kỳ cho từng Chi Nhánh (Initial Stock Allocation)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 bg-slate-800/60 rounded-lg border border-slate-700">
              <div>
                <label className="block text-indigo-300 font-semibold mb-1 flex items-center gap-1.5">
                  <i className="fa-solid fa-warehouse text-indigo-400"></i>
                  Tồn đầu kỳ Kho Hà Nội (HN)
                </label>
                <input
                  type="number"
                  min="0"
                  value={stockHN}
                  onChange={e => setStockHN(e.target.value)}
                  className="w-full bg-slate-900 border border-indigo-500/40 rounded-lg px-2.5 py-1.5 text-indigo-200 font-bold focus:outline-none focus:border-indigo-400"
                />
              </div>
              <div>
                <label className="block text-violet-300 font-semibold mb-1 flex items-center gap-1.5">
                  <i className="fa-solid fa-warehouse text-violet-400"></i>
                  Tồn đầu kỳ Kho TP.HCM (HCM)
                </label>
                <input
                  type="number"
                  min="0"
                  value={stockHCM}
                  onChange={e => setStockHCM(e.target.value)}
                  className="w-full bg-slate-900 border border-violet-500/40 rounded-lg px-2.5 py-1.5 text-violet-200 font-bold focus:outline-none focus:border-violet-400"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Hủy bỏ
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold disabled:opacity-50 flex items-center gap-1.5"
              >
                <i className="fa-solid fa-paper-plane"></i>
                {submitting ? 'Đang phát tán đồng bộ...' : 'Tạo & Đồng Bộ Toàn Bộ Chi Nhánh'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal Chỉnh Sửa Sản Phẩm */}
      {editingProduct && (
        <div className="mb-5 p-4 bg-slate-900/95 border border-amber-500/50 rounded-xl animate-fade-in shadow-xl">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-700">
            <h4 className="text-sm font-bold text-amber-300 flex items-center gap-2">
              <i className="fa-solid fa-pen-to-square"></i>
              Chỉnh Sửa Mặt Hàng [{editingProduct.sku}]
            </h4>
            <button
              onClick={() => setEditingProduct(null)}
              className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded"
            >
              <i className="fa-solid fa-xmark text-sm"></i>
            </button>
          </div>

          <form onSubmit={handleUpdateProduct} className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Mã SKU (Cố định)</label>
              <input
                type="text"
                value={editingProduct.sku}
                disabled
                className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-400 font-mono cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Tên Hàng Hóa (*)</label>
              <input
                type="text"
                value={editName}
                onChange={e => setEditName(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Đơn vị tính</label>
              <input
                type="text"
                value={editUnit}
                onChange={e => setEditUnit(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Đơn giá (VNĐ)</label>
              <input
                type="number"
                min="0"
                step="10000"
                value={editPrice}
                onChange={e => setEditPrice(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Định mức Min</label>
              <input
                type="number"
                min="0"
                value={editMinTh}
                onChange={e => setEditMinTh(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Định mức Max</label>
              <input
                type="number"
                min="1"
                value={editMaxTh}
                onChange={e => setEditMaxTh(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div className="md:col-span-2 flex items-end justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingProduct(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Hủy
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold disabled:opacity-50 flex items-center gap-1.5"
              >
                <i className="fa-solid fa-check"></i>
                {submitting ? 'Đang cập nhật...' : 'Lưu Thay Đổi & Đồng Bộ'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Thanh Tìm Kiếm & Bộ Lọc */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-3 text-xs">
        <div className="relative w-full sm:w-72">
          <i className="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400"></i>
          <input
            type="text"
            placeholder="Tìm theo SKU hoặc tên hàng hóa..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <span className="text-slate-400 text-xs">Trạng thái:</span>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">Tất cả ({globalStock.length})</option>
            <option value="SAFE">Mức an toàn</option>
            <option value="LOW">Cảnh báo tồn thấp</option>
          </select>
          <span className="text-slate-500 font-mono text-[11px] ml-1">
            Hiển thị: {filteredStock.length}/{globalStock.length}
          </span>
        </div>
      </div>

      {/* Bảng Dữ Liệu Tồn Kho */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-700">
            <tr>
              <th className="py-3 px-3">Mã SKU</th>
              <th className="py-3 px-3">Tên Hàng Hóa</th>
              <th className="py-3 px-2 text-center">ĐVT</th>
              <th className="py-3 px-3 text-right">Đơn Giá</th>
              <th className="py-3 px-3 text-center">Tổng Khả Dụng</th>
              <th className="py-3 px-3 text-center">Tổng Tạm Khóa</th>
              <th className="py-3 px-3 text-center">Trạng Thái Kho</th>
              <th className="py-3 px-3 bg-indigo-950/30 text-indigo-300 text-center border-l border-slate-700">
                Kho Hà Nội (HN)
              </th>
              <th className="py-3 px-3 bg-violet-950/30 text-violet-300 text-center border-l border-slate-700">
                Kho TP.HCM (HCM)
              </th>
              <th className="py-3 px-3 text-center border-l border-slate-700">Thao Tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/60 font-sans">
            {filteredStock.length === 0 ? (
              <tr>
                <td colSpan="10" className="py-8 text-center text-slate-500">
                  {searchTerm ? 'Không tìm thấy mặt hàng nào phù hợp với từ khóa.' : 'Chưa có dữ liệu tồn kho snapshot.'}
                </td>
              </tr>
            ) : (
              filteredStock.map(p => {
                const hn = p.branches?.HN || { available: 0, reserved: 0 };
                const hcm = p.branches?.HCM || { available: 0, reserved: 0 };
                const isLow = (p.total_available || 0) <= 20;

                return (
                  <tr key={p.sku} className="hover:bg-slate-700/30 transition-colors">
                    <td className="py-3 px-3 font-mono font-medium text-amber-300 text-xs">{p.sku}</td>
                    <td className="py-3 px-3 font-semibold text-slate-100">{p.product_name}</td>
                    <td className="py-3 px-2 text-center text-slate-400 text-xs">{p.unit}</td>
                    <td className="py-3 px-3 text-right text-slate-300 font-mono text-xs">
                      {p.price ? Number(p.price).toLocaleString('vi-VN') + ' đ' : '0 đ'}
                    </td>
                    <td className="py-3 px-3 text-center font-bold text-emerald-400 text-base">
                      {p.total_available}
                    </td>
                    <td className="py-3 px-3 text-center font-medium text-amber-400">
                      {p.total_reserved > 0 ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs">
                          {p.total_reserved}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-xs">0</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {isLow ? (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30">
                          Cảnh báo tồn thấp
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          Mức an toàn
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center border-l border-slate-700 bg-indigo-950/10">
                      <span className="font-semibold text-indigo-300">{hn.available}</span>
                      {hn.reserved > 0 && (
                        <span className="ml-1 text-xs text-amber-400">({hn.reserved} khóa)</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center border-l border-slate-700 bg-violet-950/10">
                      <span className="font-semibold text-violet-300">{hcm.available}</span>
                      {hcm.reserved > 0 && (
                        <span className="ml-1 text-xs text-amber-400">({hcm.reserved} khóa)</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-center border-l border-slate-700">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => handleOpenEdit(p)}
                          title="Chỉnh sửa thông tin mặt hàng"
                          className="px-2 py-1 rounded bg-slate-700/60 hover:bg-amber-600/30 text-amber-300 text-xs transition-colors flex items-center gap-1"
                        >
                          <i className="fa-solid fa-pen-to-square"></i>
                          <span>Sửa</span>
                        </button>
                        <button
                          onClick={() => handleDeleteProduct(p)}
                          title="Xóa mặt hàng khỏi hệ thống"
                          className="px-2 py-1 rounded bg-slate-700/60 hover:bg-red-600/30 text-red-300 text-xs transition-colors flex items-center gap-1"
                        >
                          <i className="fa-solid fa-trash-can"></i>
                          <span>Xóa</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}