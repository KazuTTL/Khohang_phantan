// frontend/src/components/GlobalStockTable.jsx
import React, { useState } from 'react';
import { api } from '../api/client';

export default function GlobalStockTable({ globalStock, categories = [], loading, onRefresh, readOnly = false }) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  // Form Thêm mới
  const [sku, setSku] = useState('');
  const [barcode, setBarcode] = useState('');
  const [name, setName] = useState('');
  const [categoryId, setCategoryId] = useState(1);
  const [unit, setUnit] = useState('Chiếc');
  const [costPrice, setCostPrice] = useState(12000000);
  const [price, setPrice] = useState(15000000);
  const [stockHN, setStockHN] = useState(50);
  const [stockHCM, setStockHCM] = useState(30);
  const [minThreshold, setMinThreshold] = useState(10);
  const [maxThreshold, setMaxThreshold] = useState(200);

  // Form Chỉnh sửa
  const [editBarcode, setEditBarcode] = useState('');
  const [editName, setEditName] = useState('');
  const [editCategoryId, setEditCategoryId] = useState(1);
  const [editUnit, setEditUnit] = useState('');
  const [editCostPrice, setEditCostPrice] = useState(0);
  const [editPrice, setEditPrice] = useState(0);
  const [editMinTh, setEditMinTh] = useState(10);
  const [editMaxTh, setEditMaxTh] = useState(200);
  const [editStockHN, setEditStockHN] = useState(0);
  const [editStockHCM, setEditStockHCM] = useState(0);

  // Search & Filter
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState(null);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setMsg(null);
    const cleanSku = sku.trim().toUpperCase();
    try {
      await api.createProduct({
        sku: cleanSku,
        barcode: barcode.trim() || `BC-${cleanSku}`,
        product_name: name.trim(),
        category_id: parseInt(categoryId, 10) || 1,
        unit: unit.trim(),
        cost_price: parseFloat(costPrice) || 0,
        price: parseFloat(price) || 0,
        initial_stock: {
          HN: parseInt(stockHN, 10) || 0,
          HCM: parseInt(stockHCM, 10) || 0
        },
        min_threshold: parseInt(minThreshold, 10) || 10,
        max_threshold: parseInt(maxThreshold, 10) || 200
      });
      setMsg({
        type: 'success',
        text: `Đã tạo SKU '${cleanSku}' và đồng bộ danh mục + tồn đầu kỳ qua RabbitMQ!`
      });
      setSku('');
      setBarcode('');
      setName('');
      if (onRefresh) onRefresh();
      setTimeout(() => {
        setShowAddModal(false);
        setMsg(null);
      }, 1200);
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Lỗi khi tạo sản phẩm' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenEdit = (p) => {
    setEditingProduct(p);
    setEditBarcode(p.barcode || `BC-${p.sku}`);
    setEditName(p.product_name);
    setEditCategoryId(p.category_id || 1);
    setEditUnit(p.unit || 'Chiếc');
    setEditCostPrice(p.cost_price || 0);
    setEditPrice(p.price || 0);
    setEditMinTh(10);
    setEditMaxTh(200);
    setEditStockHN(p.branches?.HN?.available ?? 0);
    setEditStockHCM(p.branches?.HCM?.available ?? 0);
    setMsg(null);
  };

  const handleUpdateProduct = async (e) => {
    e.preventDefault();
    if (!editingProduct) return;
    setSubmitting(true);
    setMsg(null);
    try {
      await api.updateProduct(editingProduct.sku, {
        barcode: editBarcode.trim(),
        product_name: editName.trim(),
        category_id: parseInt(editCategoryId, 10) || 1,
        unit: editUnit.trim(),
        cost_price: parseFloat(editCostPrice) || 0,
        price: parseFloat(editPrice) || 0,
        min_threshold: parseInt(editMinTh, 10) || 10,
        max_threshold: parseInt(editMaxTh, 10) || 200,
        branch_stock: {
          HN: parseInt(editStockHN, 10) || 0,
          HCM: parseInt(editStockHCM, 10) || 0
        }
      });
      setMsg({
        type: 'success',
        text: `Đã cập nhật '${editingProduct.sku}' và đồng bộ xuống các chi nhánh!`
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
      alert(`Không thể xóa '${p.sku}' vì vẫn còn tồn kho (${totalQty}). Chỉ xóa được khi tồn kho tại mọi chi nhánh bằng 0.`);
      return;
    }
    if (!window.confirm(`Xác nhận xóa vĩnh viễn mặt hàng '${p.sku}' (${p.product_name})?`)) return;

    try {
      await api.deleteProduct(p.sku);
      setMsg({ type: 'success', text: `Đã xóa mặt hàng '${p.sku}' khỏi toàn bộ hệ thống.` });
      if (onRefresh) onRefresh();
      setTimeout(() => setMsg(null), 2500);
    } catch (err) {
      alert(err.message || 'Lỗi khi xóa sản phẩm');
    }
  };

  const filteredStock = globalStock.filter((p) => {
    const q = searchTerm.toLowerCase();
    const matchSearch =
      p.sku.toLowerCase().includes(q) ||
      p.product_name.toLowerCase().includes(q) ||
      (p.barcode || '').toLowerCase().includes(q);
    if (!matchSearch) return false;
    const hnAvail = p.branches?.HN?.available || 0;
    const hcmAvail = p.branches?.HCM?.available || 0;
    if (statusFilter === 'LOW') return hnAvail <= 10 || hcmAvail <= 10;
    if (statusFilter === 'RESERVED') return (p.total_reserved || 0) > 0;
    return true;
  });

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <i className="fa-solid fa-boxes-stacked text-indigo-600"></i>
            Danh mục Sản phẩm & Tổng hợp Tồn kho Toàn quốc (SAN_PHAM / TONG_HOP_TON_KHO)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Đồng bộ bất đồng bộ từ các chi nhánh về Trung tâm qua RabbitMQ & Outbox Pattern
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!readOnly && (
            <button
              onClick={() => {
                setShowAddModal(!showAddModal);
                setEditingProduct(null);
                setMsg(null);
              }}
              className="text-xs px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold flex items-center gap-1.5 shadow-xs"
            >
              <i className="fa-solid fa-plus"></i> Thêm Mặt Hàng
            </button>
          )}
          <button
            onClick={onRefresh}
            className="text-xs px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium flex items-center gap-1.5"
          >
            <i className={`fa-solid fa-arrows-rotate ${loading ? 'animate-spin' : ''}`}></i>
            Làm mới
          </button>
        </div>
      </div>

      {msg && (
        <div className={`p-3 rounded-lg text-xs mb-4 border ${
          msg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'
        }`}>
          <i className={`fa-solid ${msg.type === 'success' ? 'fa-circle-check' : 'fa-triangle-exclamation'} mr-1.5`}></i>
          {msg.text}
        </div>
      )}

      {/* Modal Thêm Sản Phẩm */}
      {!readOnly && showAddModal && (
        <div className="mb-5 p-4 bg-slate-50 border border-indigo-200 rounded-xl">
          <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-slate-200">
            <h4 className="text-xs font-bold text-indigo-800 flex items-center gap-1.5">
              <i className="fa-solid fa-box-open"></i> Khởi tạo Mặt hàng Mới & Phân bổ Tồn đầu kỳ
            </h4>
            <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-700">
              <i className="fa-solid fa-xmark"></i>
            </button>
          </div>
          <form onSubmit={handleCreateProduct} className="space-y-3 text-xs">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mã SKU (*)</label>
                <input type="text" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="VD: IPAD-PRO-M4" required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono uppercase focus:outline-none focus:border-indigo-600" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mã vạch (Barcode)</label>
                <input type="text" value={barcode} onChange={(e) => setBarcode(e.target.value)} placeholder="Tự sinh nếu để trống" className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono focus:outline-none focus:border-indigo-600" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-slate-700 font-semibold mb-1">Tên Sản Phẩm (*)</label>
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="VD: iPad Pro M4 11 inch" required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-600" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Ngành hàng (DANH_MUC_SP)</label>
                <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-600">
                  {categories.length > 0 ? categories.map((c) => (
                    <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
                  )) : <option value={1}>Điện tử - Laptop</option>}
                </select>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Đơn vị tính</label>
                <input type="text" value={unit} onChange={(e) => setUnit(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-600" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Giá vốn (VNĐ)</label>
                <input type="number" min="0" step="10000" value={costPrice} onChange={(e) => setCostPrice(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums focus:outline-none focus:border-indigo-600" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Giá bán niêm yết (VNĐ)</label>
                <input type="number" min="0" step="10000" value={price} onChange={(e) => setPrice(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums focus:outline-none focus:border-indigo-600" />
              </div>
              <div>
                <label className="block text-sky-700 font-semibold mb-1">Tồn đầu Kho HN</label>
                <input type="number" min="0" value={stockHN} onChange={(e) => setStockHN(e.target.value)} className="w-full bg-white border border-sky-300 rounded-lg px-2.5 py-1.5 font-bold text-sky-700 tabular-nums" />
              </div>
              <div>
                <label className="block text-violet-700 font-semibold mb-1">Tồn đầu Kho HCM</label>
                <input type="number" min="0" value={stockHCM} onChange={(e) => setStockHCM(e.target.value)} className="w-full bg-white border border-violet-300 rounded-lg px-2.5 py-1.5 font-bold text-violet-700 tabular-nums" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Định mức Min</label>
                <input type="number" min="0" value={minThreshold} onChange={(e) => setMinThreshold(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Định mức Max</label>
                <input type="number" min="1" value={maxThreshold} onChange={(e) => setMaxThreshold(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowAddModal(false)} className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700">Hủy</button>
              <button type="submit" disabled={submitting} className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50">
                <i className="fa-solid fa-paper-plane mr-1"></i> {submitting ? 'Đang lưu...' : 'Tạo & Đồng Bộ Chi Nhánh'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Modal Chỉnh sửa Sản Phẩm */}
      {!readOnly && editingProduct && (
        <div className="mb-5 p-4 bg-amber-50/50 border border-amber-300 rounded-xl">
          <div className="flex items-center justify-between pb-2.5 mb-3 border-b border-amber-200">
            <h4 className="text-xs font-bold text-amber-800 flex items-center gap-1.5">
              <i className="fa-solid fa-pen-to-square"></i> Chỉnh sửa Mặt hàng [{editingProduct.sku}]
            </h4>
            <button onClick={() => setEditingProduct(null)} className="text-slate-400 hover:text-slate-700">
              <i className="fa-solid fa-xmark"></i>
            </button>
          </div>
          <form onSubmit={handleUpdateProduct} className="space-y-3 text-xs">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Mã vạch</label>
                <input type="text" value={editBarcode} onChange={(e) => setEditBarcode(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 font-mono" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-slate-700 font-semibold mb-1">Tên Sản Phẩm (*)</label>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Ngành hàng</label>
                <select value={editCategoryId} onChange={(e) => setEditCategoryId(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5">
                  {categories.length > 0 ? categories.map((c) => (
                    <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
                  )) : <option value={1}>Điện tử - Laptop</option>}
                </select>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Đơn vị tính</label>
                <input type="text" value={editUnit} onChange={(e) => setEditUnit(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Giá vốn (VNĐ)</label>
                <input type="number" min="0" step="10000" value={editCostPrice} onChange={(e) => setEditCostPrice(e.target.value)} className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums" />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Giá bán (VNĐ)</label>
                <input type="number" min="0" step="10000" value={editPrice} onChange={(e) => setEditPrice(e.target.value)} required className="w-full bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 tabular-nums" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-sky-700 font-semibold mb-1">Tồn HN</label>
                  <input type="number" min="0" value={editStockHN} onChange={(e) => setEditStockHN(e.target.value)} className="w-full bg-white border border-sky-300 rounded-lg px-2 py-1.5 font-bold text-sky-700 tabular-nums" />
                </div>
                <div>
                  <label className="block text-violet-700 font-semibold mb-1">Tồn HCM</label>
                  <input type="number" min="0" value={editStockHCM} onChange={(e) => setEditStockHCM(e.target.value)} className="w-full bg-white border border-violet-300 rounded-lg px-2 py-1.5 font-bold text-violet-700 tabular-nums" />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setEditingProduct(null)} className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700">Hủy</button>
              <button type="submit" disabled={submitting} className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold disabled:opacity-50">
                <i className="fa-solid fa-check mr-1"></i> {submitting ? 'Đang cập nhật...' : 'Lưu Thay Đổi & Đồng Bộ'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-4 text-xs">
        <div className="relative w-full sm:w-80">
          <i className="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400"></i>
          <input
            type="text"
            placeholder="Tìm theo SKU, mã vạch hoặc tên..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-slate-900 focus:outline-none focus:bg-white focus:border-indigo-500"
          />
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">Tất cả ({globalStock.length})</option>
            <option value="LOW">Cảnh báo tồn thấp</option>
            <option value="RESERVED">Đang có hàng tạm giữ</option>
          </select>
          <span className="text-slate-500">Hiển thị {filteredStock.length}/{globalStock.length}</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 text-[11px] uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">SKU / Mã vạch</th>
              <th className="py-2.5 px-3">Sản phẩm & Ngành hàng</th>
              <th className="py-2.5 px-3 text-right">Giá vốn / Giá bán</th>
              <th className="py-2.5 px-3 text-center">Tổng Khả dụng</th>
              <th className="py-2.5 px-3 text-center">Kho HN</th>
              <th className="py-2.5 px-3 text-center">Kho HCM</th>
              <th className="py-2.5 px-3 text-center">Trạng thái</th>
              {!readOnly && <th className="py-2.5 px-3 text-right">Thao tác</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-xs">
            {filteredStock.length === 0 ? (
              <tr>
                <td colSpan={readOnly ? 7 : 8} className="py-8 text-center text-slate-400">
                  Không tìm thấy sản phẩm nào.
                </td>
              </tr>
            ) : (
              filteredStock.map((p) => {
                const hnAvail = p.branches?.HN?.available ?? 0;
                const hnRes = p.branches?.HN?.reserved ?? 0;
                const hcmAvail = p.branches?.HCM?.available ?? 0;
                const hcmRes = p.branches?.HCM?.reserved ?? 0;
                const isLow = hnAvail <= 10 || hcmAvail <= 10;

                return (
                  <tr key={p.sku} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-3">
                      <div className="font-mono font-bold text-indigo-700">{p.sku}</div>
                      <div className="font-mono text-[10px] text-slate-400">{p.barcode || `BC-${p.sku}`}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-900">{p.product_name}</div>
                      <div className="text-[11px] text-slate-500">
                        {p.category_name || 'Chưa phân loại'} • {p.unit}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums">
                      <div className="text-slate-900 font-semibold">{(p.price || 0).toLocaleString('vi-VN')} đ</div>
                      <div className="text-[10px] text-slate-400">Vốn: {(p.cost_price || 0).toLocaleString('vi-VN')} đ</div>
                    </td>
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      <span className="text-sm font-extrabold text-emerald-700">{p.total_available}</span>
                      {(p.total_reserved || 0) > 0 && (
                        <div className="text-[10px] text-amber-600 font-medium">Khóa: {p.total_reserved}</div>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      <span className="font-bold text-sky-700">{hnAvail}</span>
                      {hnRes > 0 && <span className="block text-[10px] text-amber-600">({hnRes} khóa)</span>}
                    </td>
                    <td className="py-2.5 px-3 text-center tabular-nums">
                      <span className="font-bold text-violet-700">{hcmAvail}</span>
                      {hcmRes > 0 && <span className="block text-[10px] text-amber-600">({hcmRes} khóa)</span>}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {isLow ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                          Tồn thấp
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          An toàn
                        </span>
                      )}
                    </td>
                    {!readOnly && (
                      <td className="py-2.5 px-3 text-right whitespace-nowrap space-x-1.5">
                        <button
                          onClick={() => handleOpenEdit(p)}
                          className="px-2.5 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 text-[11px] font-semibold"
                        >
                          <i className="fa-solid fa-pen mr-1"></i> Sửa
                        </button>
                        <button
                          onClick={() => handleDeleteProduct(p)}
                          className="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-[11px] font-semibold"
                        >
                          <i className="fa-solid fa-trash"></i>
                        </button>
                      </td>
                    )}
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
