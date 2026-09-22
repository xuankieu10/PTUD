import { useState, useRef } from 'react';
import type { FC, ChangeEvent, DragEvent } from 'react';
import {
  Award,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  FileText,
  User,
  Calendar,
  ShieldAlert,
  Sparkles,
  Bot,
  Save,
  Check,
  RefreshCw,
  Languages,
  Laptop,
  Shield,
  Dumbbell,
  HelpCircle
} from 'lucide-react';
import type { CertificateProcessResponse, OllamaHealth } from '../types';

interface CertificateScannerProps {
  health: OllamaHealth | null;
  onProcess: (file: File, model: string) => Promise<void>;
  isLoading: boolean;
  result: CertificateProcessResponse | null;
  error: string | null;
  onReset: () => void;
}

const REQUIRED_CATEGORIES = [
  { id: 'Ngoại ngữ', label: 'Chuẩn Ngoại ngữ (TOEIC, IELTS, VSTEP...)', icon: Languages, color: 'text-blue-600 bg-blue-50' },
  { id: 'Tin học', label: 'Chuẩn Tin học (MOS, IC3, CNTT...)', icon: Laptop, color: 'text-emerald-600 bg-emerald-50' },
  { id: 'Quốc phòng', label: 'GD Quốc phòng & An ninh (GDQP)', icon: Shield, color: 'text-amber-600 bg-amber-50' },
  { id: 'Thể chất', label: 'Giáo dục Thể chất (GDTC)', icon: Dumbbell, color: 'text-purple-600 bg-purple-50' },
];

export const CertificateScanner: FC<CertificateScannerProps> = ({
  health,
  onProcess,
  isLoading,
  result,
  error,
  onReset
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [isSaved, setIsSaved] = useState(false);
  const [manualCategory, setManualCategory] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const availableModels = health?.ollama?.models || [];
  const currentModel = selectedModel || health?.ollama?.recommended_model || availableModels[0] || 'llama3.2-vision';

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setIsSaved(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      setIsSaved(false);
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;
    setIsSaved(false);
    await onProcess(selectedFile, currentModel);
  };

  const handleSaveToDb = () => {
    setIsSaved(true);
  };

  const getCategoryIcon = (categoryName: string | null) => {
    switch (categoryName) {
      case 'Ngoại ngữ':
        return <Languages className="w-5 h-5 text-blue-600" />;
      case 'Tin học':
        return <Laptop className="w-5 h-5 text-emerald-600" />;
      case 'Quốc phòng':
        return <Shield className="w-5 h-5 text-amber-600" />;
      case 'Thể chất':
        return <Dumbbell className="w-5 h-5 text-purple-600" />;
      default:
        return <HelpCircle className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Khối upload chứng chỉ */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Award className="w-5 h-5 text-indigo-600" />
              Tải lên Chứng chỉ Tốt nghiệp
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Hỗ trợ ảnh chứng chỉ Ngoại ngữ (TOEIC, IELTS), Tin học (MOS), GDQP & GDTC
            </p>
          </div>

          {/* Model Selector */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-100 text-xs font-medium text-slate-700">
              <Bot className="w-3.5 h-3.5 text-indigo-500" />
              <select
                value={currentModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-transparent border-none outline-none text-xs font-semibold cursor-pointer text-slate-800"
              >
                {availableModels.length > 0 ? (
                  availableModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                ) : (
                  <option value="llama3.2-vision">llama3.2-vision (mặc định)</option>
                )}
              </select>
            </div>
          </div>
        </div>

        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-indigo-500 bg-indigo-50/50 scale-[0.99]'
              : 'border-slate-300 hover:border-indigo-400 bg-slate-50/50 hover:bg-white'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="flex flex-col items-center justify-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center shadow-inner">
              <UploadCloud className="w-7 h-7" />
            </div>
            {selectedFile ? (
              <div>
                <p className="text-sm font-semibold text-slate-800">{selectedFile.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {(selectedFile.size / 1024).toFixed(1)} KB — Nhấp hoặc kéo thả để đổi file khác
                </p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-semibold text-slate-700">
                  Kéo thả ảnh chứng chỉ vào đây hoặc <span className="text-indigo-600 underline">duyệt file</span>
                </p>
                <p className="text-xs text-slate-400 mt-1">Định dạng JPG, PNG (ảnh chụp hoặc bản scan sắc nét)</p>
              </div>
            )}
          </div>
        </div>

        {/* Action Button */}
        <div className="mt-5 flex items-center justify-between">
          <p className="text-xs text-slate-500">
            {health?.ollama?.online ? (
              <span className="text-emerald-600 font-medium">● Ollama Online ({currentModel})</span>
            ) : (
              <span className="text-amber-600 font-medium">● Kiểm tra kết nối Ollama...</span>
            )}
          </p>

          <div className="flex items-center gap-3">
            {result && (
              <button
                onClick={onReset}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Quét chứng chỉ khác
              </button>
            )}

            <button
              onClick={handleSubmit}
              disabled={!selectedFile || isLoading}
              className={`px-6 py-2.5 rounded-xl text-xs font-bold text-white shadow-sm flex items-center gap-2 transition ${
                !selectedFile || isLoading
                  ? 'bg-slate-300 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95'
              }`}
            >
              {isLoading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Đang phân tích chứng chỉ...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Xác Thực & Đối Chiếu Chuẩn Tốt Nghiệp
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Thông báo lỗi nếu có */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-rose-800">Không thể xử lý chứng chỉ</h4>
            <p className="text-xs text-rose-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Hiển thị kết quả trích xuất & đối chiếu */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cột trái: Ảnh preview chứng chỉ */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col items-center">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 self-start">
              Ảnh Chứng Chỉ Đã Quét
            </h3>
            {result.preview_image ? (
              <div className="w-full rounded-xl overflow-hidden border border-slate-200 bg-slate-100">
                <img
                  src={result.preview_image}
                  alt="Ảnh chứng chỉ"
                  className="w-full h-auto max-h-80 object-contain mx-auto"
                />
              </div>
            ) : (
              <div className="w-full h-48 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 text-xs">
                Không có ảnh xem trước
              </div>
            )}
            <p className="text-xs text-slate-400 mt-2 text-center">{result.filename}</p>
          </div>

          {/* Cột giữa & phải: Thông tin trích xuất & So khớp */}
          <div className="lg:col-span-2 space-y-5">
            {/* Card Trạng thái Cập Nhật Tốt Nghiệp */}
            <div
              className={`rounded-2xl p-5 border ${
                result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất'
                  ? 'bg-emerald-50/70 border-emerald-200'
                  : 'bg-amber-50/70 border-amber-200'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3.5">
                  <div
                    className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                      result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất'
                        ? 'bg-emerald-600 text-white shadow-emerald-200 shadow-lg'
                        : 'bg-amber-500 text-white shadow-amber-200 shadow-lg'
                    }`}
                  >
                    {result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất' ? (
                      <CheckCircle2 className="w-6 h-6" />
                    ) : (
                      <ShieldAlert className="w-6 h-6" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold uppercase tracking-wide px-2.5 py-0.5 rounded-full ${
                          result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        Trạng thái: {result.matching_result.trang_thai_cap_nhat}
                      </span>
                      {result.matching_result.tu_dong_cap_nhat && (
                        <span className="text-[11px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md font-semibold">
                          Tự động phê duyệt
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mt-1">
                      {result.matching_result.muc_tot_nghiep_khop
                        ? `Khớp điều kiện: ${result.matching_result.muc_tot_nghiep_khop}`
                        : 'Chưa xác định được điều kiện tốt nghiệp phù hợp'}
                    </h3>
                    <p className="text-xs text-slate-600 mt-1">{result.matching_result.ly_do}</p>
                  </div>
                </div>

                {/* Nút lưu hoặc xác nhận thủ công */}
                <div className="shrink-0">
                  {isSaved ? (
                    <div className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow-sm">
                      <Check className="w-4 h-4" />
                      Đã ghi nhận vào CSDL
                    </div>
                  ) : (
                    <button
                      onClick={handleSaveToDb}
                      className={`px-4 py-2 rounded-xl text-xs font-bold shadow-sm flex items-center gap-1.5 transition ${
                        result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất'
                          ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                          : 'bg-amber-600 hover:bg-amber-700 text-white'
                      }`}
                    >
                      <Save className="w-4 h-4" />
                      {result.matching_result.trang_thai_cap_nhat === 'Đã hoàn tất'
                        ? 'Đồng ý & Cập nhật CSDL'
                        : 'Xác nhận gán thủ công'}
                    </button>
                  )}
                </div>
              </div>

              {/* Nếu cần xác nhận thủ công: Dropdown cho phép chọn gán lại mục */}
              {result.matching_result.trang_thai_cap_nhat !== 'Đã hoàn tất' && !isSaved && (
                <div className="mt-4 pt-4 border-t border-amber-200/80 flex flex-wrap items-center gap-3">
                  <span className="text-xs font-semibold text-slate-700">Chọn gán thủ công vào:</span>
                  <select
                    value={manualCategory || result.matching_result.muc_tot_nghiep_khop || ''}
                    onChange={(e) => setManualCategory(e.target.value)}
                    className="text-xs font-semibold bg-white border border-slate-300 rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500"
                  >
                    <option value="">-- Chọn chuẩn tốt nghiệp --</option>
                    {REQUIRED_CATEGORIES.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                  <span className="text-[11px] text-slate-500">
                    (Cán bộ đào tạo hoặc sinh viên có thể chọn mục chính xác để ghi nhận)
                  </span>
                </div>
              )}
            </div>

            {/* Chi tiết thông tin trích xuất từ AI */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">
                Thông Tin Trích Xuất Chi Tiết Từ Chứng Chỉ
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                {/* Tên chứng chỉ */}
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Tên chứng chỉ cụ thể</span>
                    <p className="font-bold text-slate-800 text-sm mt-0.5">
                      {result.extracted_data.ten_chung_chi_cu_the || 'Chưa rõ'}
                    </p>
                  </div>
                </div>

                {/* Nhóm phân loại */}
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                    {getCategoryIcon(result.matching_result.muc_tot_nghiep_khop)}
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Nhóm danh mục nhận diện</span>
                    <p className="font-bold text-slate-800 text-sm mt-0.5">
                      {result.extracted_data.loai_chung_chi}
                    </p>
                  </div>
                </div>

                {/* Người được cấp */}
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                    <User className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Người được cấp</span>
                    <p className="font-bold text-slate-800 text-sm mt-0.5">
                      {result.extracted_data.ten_nguoi_duoc_cap || 'Không ghi rõ trên ảnh'}
                    </p>
                  </div>
                </div>

                {/* Ngày cấp */}
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Ngày cấp</span>
                    <p className="font-bold text-slate-800 text-sm mt-0.5">
                      {result.extracted_data.ngay_cap || 'Không ghi rõ trên ảnh'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Footer điểm tương đồng và độ tin cậy */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 font-medium">Độ tin cậy OCR:</span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full font-bold ${
                      result.extracted_data.do_tin_cay === 'cao'
                        ? 'bg-emerald-100 text-emerald-700'
                        : result.extracted_data.do_tin_cay === 'trung binh'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-rose-100 text-rose-700'
                    }`}
                  >
                    {result.extracted_data.do_tin_cay === 'cao'
                      ? 'Cao (Rõ nét)'
                      : result.extracted_data.do_tin_cay === 'trung binh'
                      ? 'Trung bình'
                      : 'Thấp (Cần xem lại)'}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-slate-500 font-medium">Độ tương đồng Fuzzy:</span>
                  <span className="font-mono font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                    {result.matching_result.do_tuong_dong}%
                  </span>
                  <span className="text-slate-400">({result.matching_result.phuong_thuc_khop})</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
