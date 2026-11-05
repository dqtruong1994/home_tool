import React, { useState, useMemo } from 'react';
import { 
  Upload, FileSpreadsheet, Download, ExternalLink, Search, Filter, 
  ArrowUpDown, RefreshCw, CheckCircle2, AlertCircle, Sparkles, Building2, Globe,
  Presentation, Layers, Image as ImageIcon, Sliders, Check
} from 'lucide-react';
import { parseExcelClientSide, exportToExcelClientSide, EXCHANGE_RATE_DEFAULT } from './catalog';
import { extractImagesFromPptx, generateRemasteredPptx } from './pptRemaster';

export default function App() {
  const [activeTab, setActiveTab] = useState('compare'); // 'compare' | 'ppt'

  // ==========================================
  // STATE: PRICE COMPARATOR
  // ==========================================
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fileName, setFileName] = useState('');
  const [exchangeRate, setExchangeRate] = useState(EXCHANGE_RATE_DEFAULT);
  
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [sortField, setSortField] = useState('stt');
  const [sortAsc, setSortAsc] = useState(true);

  // ==========================================
  // STATE: PPT REMASTER
  // ==========================================
  const [pptFile, setPptFile] = useState(null);
  const [pptLoading, setPptLoading] = useState(false);
  const [pptExtracted, setPptExtracted] = useState([]);
  const [pptSuccess, setPptSuccess] = useState(null);
  const [pptError, setPptError] = useState(null);
  
  const [pptTitle, setPptTitle] = useState("Handcrafted Navy & Natural Resin Collection");
  const [pptSubtitle, setPptSubtitle] = useState("Presentation for Pan Home // 11.2026");
  const [pptMaterialNote, setPptMaterialNote] = useState("Material: Resin wicker, iron frame // Render artwork");
  const [pptTargetPerSlide, setPptTargetPerSlide] = useState(4);

  // ------------------------------------------
  // Handlers: Price Comparator
  // ------------------------------------------
  const handleFileUpload = async (file) => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setFileName(file.name);

    try {
      let result = null;
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('rate', exchangeRate);

        const res = await fetch('http://localhost:8000/api/compare', {
          method: 'POST',
          body: formData
        });
        if (res.ok) {
          result = await res.json();
        }
      } catch (backendErr) {
        console.log('Using client-side engine');
      }

      if (!result) {
        const buffer = await file.arrayBuffer();
        result = parseExcelClientSide(buffer, exchangeRate);
      }

      setData(result);
    } catch (err) {
      console.error(err);
      setError('Lỗi khi đọc file Excel. Vui lòng kiểm tra định dạng file .xlsx.');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (!data || !data.items || data.items.length === 0) return;
    try {
      const res = await fetch('http://localhost:8000/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: data.items,
          exchange_rate: exchangeRate
        })
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Ket_qua_so_sanh_gia_Pan_Home.xlsx';
        a.click();
        return;
      }
    } catch (e) {
      console.log('Using client-side export');
    }

    exportToExcelClientSide(data.items, exchangeRate);
  };

  const filteredItems = useMemo(() => {
    if (!data || !data.items) return [];

    return data.items
      .filter(item => {
        const matchSearch = 
          item.ref.toLowerCase().includes(searchTerm.toLowerCase()) ||
          item.desc.toLowerCase().includes(searchTerm.toLowerCase()) ||
          item.mat_color.toLowerCase().includes(searchTerm.toLowerCase()) ||
          item.matched_title.toLowerCase().includes(searchTerm.toLowerCase());

        const matchCat = 
          selectedCategory === 'ALL' || item.category === selectedCategory;

        return matchSearch && matchCat;
      })
      .sort((a, b) => {
        let valA = a[sortField];
        let valB = b[sortField];
        if (typeof valA === 'string') {
          return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return sortAsc ? valA - valB : valB - valA;
      });
  }, [data, searchTerm, selectedCategory, sortField, sortAsc]);

  const categories = useMemo(() => {
    if (!data || !data.items) return [];
    const set = new Set(data.items.map(i => i.category));
    return ['ALL', ...Array.from(set)];
  }, [data]);

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  // ------------------------------------------
  // Handlers: PPT Remaster
  // ------------------------------------------
  const handlePptUpload = async (file) => {
    if (!file) return;
    setPptFile(file);
    setPptLoading(true);
    setPptError(null);
    setPptSuccess(null);

    try {
      const extracted = await extractImagesFromPptx(file);
      if (extracted.length === 0) {
        setPptError("Không tìm thấy hình ảnh sản phẩm hợp lệ trong file PowerPoint này.");
      } else {
        setPptExtracted(extracted);
      }
    } catch (err) {
      console.error(err);
      setPptError("Lỗi khi bóc tách file PPT. Vui lòng kiểm tra định dạng .pptx.");
    } finally {
      setPptLoading(false);
    }
  };

  const handleGeneratePpt = async () => {
    if (pptExtracted.length === 0) return;
    setPptLoading(true);
    setPptError(null);

    try {
      const result = await generateRemasteredPptx(pptExtracted, {
        collectionTitle: pptTitle,
        subtitle: pptSubtitle,
        materialNote: pptMaterialNote,
        targetPerSlide: pptTargetPerSlide
      });
      setPptSuccess(result);
    } catch (err) {
      console.error(err);
      setPptError("Lỗi khi xuất file PPT mới: " + err.message);
    } finally {
      setPptLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-700 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">Home Tool</h1>
              <p className="text-xs text-slate-500">Personal Merchandising & Productivity Suite // Benchmark & PPT Remaster</p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setActiveTab('compare')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'compare'
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>1. So Sánh Giá Pan Home</span>
            </button>
            <button
              onClick={() => setActiveTab('ppt')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'ppt'
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Presentation className="w-4 h-4" />
              <span>2. Dàn Trang PPT (Uniform Height)</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* ==================================================== */}
        {/* TAB 1: PRICE COMPARATOR */}
        {/* ==================================================== */}
        {activeTab === 'compare' && (
          <div className="space-y-6">
            {/* Top Control Bar */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Upload Card */}
              <div className="md:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900 mb-2 flex items-center gap-2">
                  <FileSpreadsheet className="w-5 h-5 text-blue-600" />
                  Tải lên file báo giá nội bộ (Excel)
                </h2>
                <p className="text-xs text-slate-500 mb-4">
                  Kéo thả file báo giá gốc (FOB Hải Phòng). Hệ thống tự làm sạch kích thước và đối chuẩn với Pan Home UAE.
                </p>

                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                      handleFileUpload(e.dataTransfer.files[0]);
                    }
                  }}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                    loading ? 'bg-slate-50 border-blue-400' : 'border-slate-300 hover:border-blue-500 hover:bg-blue-50/30'
                  }`}
                  onClick={() => document.getElementById('excelFileInput').click()}
                >
                  <input
                    id="excelFileInput"
                    type="file"
                    accept=".xlsx,.xls"
                    className="hidden"
                    onChange={(e) => e.target.files && handleFileUpload(e.target.files[0])}
                  />
                  {loading ? (
                    <div className="flex flex-col items-center justify-center space-y-2 py-4">
                      <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
                      <p className="text-sm font-medium text-slate-700">Đang phân tích bảng giá và đối chuẩn Pan Home...</p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center space-y-2 py-2">
                      <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
                        <Upload className="w-6 h-6" />
                      </div>
                      <p className="text-sm font-medium text-slate-700">
                        {fileName ? (
                          <span className="text-blue-600 font-semibold">{fileName}</span>
                        ) : (
                          <>Nhấp để chọn file hoặc kéo thả vào đây</>
                        )}
                      </p>
                      <p className="text-xs text-slate-400">Định dạng hỗ trợ: .xlsx, .xls</p>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>

              {/* Rate & Config Card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <h2 className="text-base font-semibold text-slate-900 mb-2 flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-indigo-600" />
                    Cấu hình đối chuẩn
                  </h2>
                  <p className="text-xs text-slate-500 mb-4">
                    Tỷ giá neo cố định của Ngân hàng Trung ương UAE: 1 USD = 3.6725 AED.
                  </p>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">
                        Tỷ giá quy đổi (1 USD = ? AED)
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        value={exchangeRate}
                        onChange={(e) => setExchangeRate(parseFloat(e.target.value) || EXCHANGE_RATE_DEFAULT)}
                        className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      />
                    </div>
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs space-y-1">
                      <div className="flex justify-between text-slate-500">
                        <span>Website đối chiếu:</span>
                        <span className="font-semibold text-slate-700">panhomestores.com</span>
                      </div>
                      <div className="flex justify-between text-slate-500">
                        <span>Tiêu chuẩn giá:</span>
                        <span className="font-semibold text-slate-700">Regular Price (Giá gốc)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {data && (
                  <button
                    onClick={handleExport}
                    className="w-full mt-4 flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium py-2.5 px-4 rounded-xl shadow-md shadow-blue-500/20 text-sm transition-all"
                  >
                    <Download className="w-4 h-4" />
                    Xuất File Excel (.xlsx) Kèm Link
                  </button>
                )}
              </div>
            </div>

            {/* Results Table & Summary Cards */}
            {data && data.items && (
              <div className="space-y-6">
                {/* Metric Summary Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Tổng số sản phẩm</p>
                    <p className="text-2xl font-bold text-slate-900 mt-1">{data.summary.total_items} SP</p>
                    <p className="text-xs text-emerald-600 mt-1 font-medium">Đối chuẩn thành công 100%</p>
                  </div>
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Tổng giá FOB nội bộ</p>
                    <p className="text-2xl font-bold text-blue-700 mt-1">${data.summary.total_fob_usd.toLocaleString()} USD</p>
                    <p className="text-xs text-slate-400 mt-1">Giá xuất khẩu Hải Phòng</p>
                  </div>
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Tổng giá niêm yết Pan Home</p>
                    <p className="text-2xl font-bold text-indigo-700 mt-1">${data.summary.total_retail_usd.toLocaleString()} USD</p>
                    <p className="text-xs text-slate-400 mt-1">({data.summary.total_retail_aed.toLocaleString()} AED)</p>
                  </div>
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Tỷ lệ Bán lẻ / FOB TB</p>
                    <p className="text-2xl font-bold text-amber-600 mt-1">{data.summary.avg_markup_ratio}x</p>
                    <p className="text-xs text-slate-400 mt-1">Hệ số biên độ thị trường UAE</p>
                  </div>
                </div>

                {/* Table Filter & Search */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                  <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row gap-3 items-center justify-between bg-slate-50/50">
                    <div className="relative w-full sm:w-80">
                      <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Tìm theo mã SKU, mô tả, vật liệu..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      />
                    </div>

                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      <Filter className="w-4 h-4 text-slate-400" />
                      <div className="flex gap-1 overflow-x-auto py-1">
                        {categories.map(cat => (
                          <button
                            key={cat}
                            onClick={() => setSelectedCategory(cat)}
                            className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                              selectedCategory === cat 
                                ? 'bg-blue-600 text-white shadow-sm'
                                : 'bg-slate-200/60 text-slate-600 hover:bg-slate-200'
                            }`}
                          >
                            {cat}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-3 px-3 cursor-pointer" onClick={() => toggleSort('stt')}>
                            <div className="flex items-center gap-1">STT <ArrowUpDown className="w-3 h-3 text-slate-400" /></div>
                          </th>
                          <th className="py-3 px-3">Mã SKU</th>
                          <th className="py-3 px-4">Mô tả sản phẩm nội bộ</th>
                          <th className="py-3 px-3">Vật liệu & Màu</th>
                          <th className="py-3 px-3">Kích thước</th>
                          <th className="py-3 px-3 text-right cursor-pointer" onClick={() => toggleSort('fob_price')}>
                            <div className="flex items-center justify-end gap-1">FOB (USD) <ArrowUpDown className="w-3 h-3 text-slate-400" /></div>
                          </th>
                          <th className="py-3 px-4">SP tương đương Pan Home</th>
                          <th className="py-3 px-3 text-right">Giá gốc (AED)</th>
                          <th className="py-3 px-3 text-right cursor-pointer" onClick={() => toggleSort('retail_usd')}>
                            <div className="flex items-center justify-end gap-1">Giá gốc (USD) <ArrowUpDown className="w-3 h-3 text-slate-400" /></div>
                          </th>
                          <th className="py-3 px-3 text-right cursor-pointer" onClick={() => toggleSort('markup_ratio')}>
                            <div className="flex items-center justify-end gap-1">Tỷ lệ x <ArrowUpDown className="w-3 h-3 text-slate-400" /></div>
                          </th>
                          <th className="py-3 px-3 text-center">Link Pan Home</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredItems.map((item, idx) => (
                          <tr key={idx} className="hover:bg-blue-50/40 transition-colors">
                            <td className="py-3 px-3 text-slate-400 font-medium">{item.stt}</td>
                            <td className="py-3 px-3 font-bold text-slate-900">{item.ref}</td>
                            <td className="py-3 px-4 text-slate-700 max-w-xs">{item.desc}</td>
                            <td className="py-3 px-3 text-slate-600">{item.mat_color}</td>
                            <td className="py-3 px-3 text-slate-600 font-mono text-[11px]">{item.size}</td>
                            <td className="py-3 px-3 text-right font-bold text-slate-900">${item.fob_price.toFixed(2)}</td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-blue-900">{item.matched_title}</div>
                              <div className="text-[11px] text-slate-500">{item.matched_specs}</div>
                            </td>
                            <td className="py-3 px-3 text-right font-mono text-slate-700">{item.retail_aed.toLocaleString()} AED</td>
                            <td className="py-3 px-3 text-right font-bold text-indigo-700">${item.retail_usd.toFixed(2)}</td>
                            <td className="py-3 px-3 text-right font-bold text-amber-600">{item.markup_ratio}x</td>
                            <td className="py-3 px-3 text-center">
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200 text-[11px] font-medium transition-colors"
                              >
                                Xem SP <ExternalLink className="w-3 h-3" />
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ==================================================== */}
        {/* TAB 2: PPT REMASTER ENGINE */}
        {/* ==================================================== */}
        {activeTab === 'ppt' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Upload Card */}
              <div className="md:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h2 className="text-base font-semibold text-slate-900 mb-2 flex items-center gap-2">
                  <Presentation className="w-5 h-5 text-indigo-600" />
                  Tải lên PowerPoint nhà máy (PPT 1)
                </h2>
                <p className="text-xs text-slate-500 mb-4">
                  Hệ thống tự bóc tách ảnh từ các sheet, lọc rác, gom nhóm theo tông màu và dàn trang <b>Uniform Height 100%</b> chuẩn A5 Landscape.
                </p>

                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                      handlePptUpload(e.dataTransfer.files[0]);
                    }
                  }}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                    pptLoading ? 'bg-slate-50 border-indigo-400' : 'border-slate-300 hover:border-indigo-500 hover:bg-indigo-50/30'
                  }`}
                  onClick={() => document.getElementById('pptFileInput').click()}
                >
                  <input
                    id="pptFileInput"
                    type="file"
                    accept=".pptx"
                    className="hidden"
                    onChange={(e) => e.target.files && handlePptUpload(e.target.files[0])}
                  />
                  {pptLoading ? (
                    <div className="flex flex-col items-center justify-center space-y-2 py-4">
                      <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
                      <p className="text-sm font-medium text-slate-700">Đang bóc tách hình ảnh và phân tích màu sắc...</p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center space-y-2 py-2">
                      <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center">
                        <Upload className="w-6 h-6" />
                      </div>
                      <p className="text-sm font-medium text-slate-700">
                        {pptFile ? (
                          <span className="text-indigo-600 font-semibold">{pptFile.name}</span>
                        ) : (
                          <>Nhấp để chọn file .pptx hoặc kéo thả vào đây</>
                        )}
                      </p>
                      <p className="text-xs text-slate-400">File PPT nhà máy (hàng chục đến hàng trăm sheet)</p>
                    </div>
                  )}
                </div>

                {pptError && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{pptError}</span>
                  </div>
                )}
              </div>

              {/* Settings Card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <h2 className="text-base font-semibold text-slate-900 mb-2 flex items-center gap-2">
                    <Sliders className="w-5 h-5 text-indigo-600" />
                    Bố cục & Tiêu đề
                  </h2>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Tiêu đề bộ sưu tập:</label>
                      <input
                        type="text"
                        value={pptTitle}
                        onChange={(e) => setPptTitle(e.target.value)}
                        className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Khách hàng / Thời gian:</label>
                      <input
                        type="text"
                        value={pptSubtitle}
                        onChange={(e) => setPptSubtitle(e.target.value)}
                        className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Ghi chú vật liệu (Footer):</label>
                      <input
                        type="text"
                        value={pptMaterialNote}
                        onChange={(e) => setPptMaterialNote(e.target.value)}
                        className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Số sản phẩm mỗi slide:</label>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setPptTargetPerSlide(4)}
                          className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                            pptTargetPerSlide === 4
                              ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                              : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                          }`}
                        >
                          4 SP (Lưới 2x2)
                        </button>
                        <button
                          type="button"
                          onClick={() => setPptTargetPerSlide(3)}
                          className={`py-2 text-xs font-semibold rounded-xl border transition-all ${
                            pptTargetPerSlide === 3
                              ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                              : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                          }`}
                        >
                          3 SP (Hàng 1x3)
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {pptExtracted.length > 0 && (
                  <button
                    onClick={handleGeneratePpt}
                    disabled={pptLoading}
                    className="w-full mt-4 flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-blue-700 hover:from-indigo-700 hover:to-blue-800 text-white font-medium py-2.5 px-4 rounded-xl shadow-md shadow-indigo-500/20 text-sm transition-all"
                  >
                    <Download className="w-4 h-4" />
                    Xuất File PPT 2 Chuẩn A5
                  </button>
                )}
              </div>
            </div>

            {/* Extracted Images & Result Section */}
            {pptExtracted.length > 0 && (
              <div className="space-y-6">
                {/* Metric Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Sản phẩm bóc tách</p>
                    <p className="text-2xl font-bold text-slate-900 mt-1">{pptExtracted.length} ảnh</p>
                    <p className="text-xs text-indigo-600 mt-1 font-medium">Đã phân cụm tông màu</p>
                  </div>
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Slide thành phẩm A5</p>
                    <p className="text-2xl font-bold text-indigo-700 mt-1">
                      {Math.ceil(pptExtracted.length / pptTargetPerSlide) + 1} slides
                    </p>
                    <p className="text-xs text-slate-400 mt-1">Bao gồm 1 slide bìa + nội dung</p>
                  </div>
                  <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <p className="text-xs font-semibold text-slate-400 uppercase">Thuộc tính Height</p>
                    <p className="text-2xl font-bold text-emerald-600 mt-1 flex items-center gap-1">
                      <Check className="w-5 h-5" /> Đồng bộ 100%
                    </p>
                    <p className="text-xs text-slate-400 mt-1">Đáy và đỉnh ảnh thẳng tắp</p>
                  </div>
                </div>

                {/* Preview Gallery */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <ImageIcon className="w-4 h-4 text-indigo-600" />
                      Xem trước {pptExtracted.length} hình ảnh sản phẩm đã gom nhóm
                    </h3>
                    <span className="text-xs text-slate-400">Tự động sắp xếp theo sắc thái màu sắc</span>
                  </div>

                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
                    {pptExtracted.map((item, idx) => (
                      <div key={idx} className="group relative bg-slate-50 rounded-xl border border-slate-200 p-2 flex flex-col items-center">
                        <img
                          src={item.dataUrl}
                          alt={`SP ${idx + 1}`}
                          className="w-full h-24 object-contain rounded-lg"
                        />
                        <span className="mt-1 text-[10px] text-slate-400 font-mono">
                          #{idx + 1} ({item.ratio.toFixed(2)})
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
        Home Tool // Hosted on Cloudflare Pages // Pan Home Benchmark & PPT Remaster
      </footer>
    </div>
  );
}
