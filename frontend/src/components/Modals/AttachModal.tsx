import React, { useState } from 'react';
import { X, FileText, Award, Upload, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import type { OllamaHealth } from '../../types';

interface AttachModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFileProcessedText?: (text: string) => void;
  health: OllamaHealth | null;
}

export const AttachModal: React.FC<AttachModalProps> = ({
  isOpen,
  onClose,
  onFileProcessedText,
}) => {
  const [activeTab, setActiveTab] = useState<'transcript' | 'certificate'>('transcript');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setProcessResult(null);
      setErrorMessage(null);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) return;
    setIsProcessing(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('model', 'llama3.2-vision');

    const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || '';
    const endpoint =
      activeTab === 'transcript'
        ? `${API_BASE_URL}/api/process`
        : `${API_BASE_URL}/api/certificate/process`;

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `Lỗi khi xử lý file (${res.status})`);
      }

      const data = await res.json();
      let summaryText = '';

      if (activeTab === 'transcript') {
        const s = data.summary;
        summaryText = `Đã phân tích bảng điểm "${selectedFile.name}":\n- Tổng số môn: ${s.total_subjects}\n- Số môn đạt: ${s.passed_count}\n- Môn chưa đạt: ${s.failed_count}\n- Vùng đỏ đánh dấu: ${s.red_regions_count}`;
      } else {
        const ext = data.extracted_data;
        const match = data.matching_result;
        summaryText = `Đã phân tích chứng chỉ "${selectedFile.name}":\n- Loại chứng chỉ: ${ext.loai_chung_chi}\n- Tên chứng chỉ: ${ext.ten_chung_chi_cu_the}\n- Trạng thái khớp: ${match.trang_thai_cap_nhat} (${match.muc_tot_nghiep_khop || 'Không'})`;
      }

      setProcessResult(summaryText);
      if (onFileProcessedText) {
        onFileProcessedText(summaryText);
      }
    } catch (e: any) {
      setErrorMessage(e.message || 'Xử lý file thất bại. Vui lòng thử lại.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-2xs animate-fade-in">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-gray-100">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <h3 className="text-base font-bold text-[#1F1F1F]">
            Đính kèm & Phân tích tài liệu học vụ
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab switch */}
        <div className="flex gap-2 mt-4 p-1 bg-[#F4F4F5] rounded-xl">
          <button
            type="button"
            onClick={() => {
              setActiveTab('transcript');
              setSelectedFile(null);
              setProcessResult(null);
            }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition ${
              activeTab === 'transcript'
                ? 'bg-white text-[#1F1F1F] shadow-2xs'
                : 'text-[#6B6B6B] hover:text-[#1F1F1F]'
            }`}
          >
            <FileText className="w-4 h-4 text-[#F5B800]" />
            <span>Bảng Điểm Học Tập</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('certificate');
              setSelectedFile(null);
              setProcessResult(null);
            }}
            className={`flex-1 py-2 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition ${
              activeTab === 'certificate'
                ? 'bg-white text-[#1F1F1F] shadow-2xs'
                : 'text-[#6B6B6B] hover:text-[#1F1F1F]'
            }`}
          >
            <Award className="w-4 h-4 text-[#F5B800]" />
            <span>Chứng Chỉ Tốt Nghiệp</span>
          </button>
        </div>

        {/* Upload area */}
        <div className="mt-4 border-2 border-dashed border-gray-200 hover:border-[#F5B800] rounded-2xl p-6 text-center transition-colors">
          <input
            type="file"
            id="modal-file-upload"
            accept=".png,.jpg,.jpeg,.pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          <label htmlFor="modal-file-upload" className="cursor-pointer block">
            <Upload className="w-8 h-8 text-[#9CA3AF] mx-auto mb-2" />
            <p className="text-xs font-medium text-[#1F1F1F]">
              {selectedFile ? selectedFile.name : 'Nhấp để chọn ảnh chụp hoặc PDF'}
            </p>
            <p className="text-[11px] text-[#9CA3AF] mt-1">Hỗ trợ PNG, JPG, PDF</p>
          </label>
        </div>

        {/* Error */}
        {errorMessage && (
          <div className="mt-3 p-3 bg-rose-50 text-rose-700 text-xs rounded-xl flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Success */}
        {processResult && (
          <div className="mt-3 p-3 bg-emerald-50 text-emerald-800 text-xs rounded-xl flex items-start gap-2 whitespace-pre-line">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
            <span>{processResult}</span>
          </div>
        )}

        {/* Footer */}
        <div className="mt-5 flex items-center justify-end gap-2 pt-2 border-t border-gray-100">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-gray-100 rounded-xl transition"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={handleUploadAndAnalyze}
            disabled={!selectedFile || isProcessing}
            className={`px-4 py-2 text-xs font-semibold rounded-xl text-white flex items-center gap-1.5 transition ${
              selectedFile && !isProcessing
                ? 'bg-[#1F1F1F] hover:bg-black cursor-pointer'
                : 'bg-gray-300 cursor-not-allowed'
            }`}
          >
            {isProcessing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{isProcessing ? 'Đang trích xuất AI...' : 'Phân tích file'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
