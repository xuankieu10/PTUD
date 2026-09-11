import { useRef, useState, useEffect } from 'react';
import type { FC, DragEvent, ChangeEvent, FormEvent } from 'react';
import { UploadCloud, FileText, Image as ImageIcon, Loader2, Cpu, CheckCircle2 } from 'lucide-react';
import type { OllamaHealth } from '../types';

interface FileUploaderProps {
  onProcess: (file: File, model: string) => void;
  isLoading: boolean;
  health: OllamaHealth | null;
}

export const FileUploader: FC<FileUploaderProps> = ({ onProcess, isLoading, health }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('llama3.2-vision');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Tự động chọn model đã cài đặt nếu llama3.2-vision chưa được tải về
  useEffect(() => {
    if (health?.ollama?.models && health.ollama.models.length > 0) {
      const models = health.ollama.models;
      if (!models.includes('llama3.2-vision')) {
        // Ưu tiên model vision như qwen2.5vl
        const fallbackVision = models.find((m) => m.toLowerCase().includes('vl') || m.toLowerCase().includes('vision')) || models[0];
        setSelectedModel(fallbackVision);
      }
    }
  }, [health]);

  const handleDrag = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    const validExtensions = ['.jpg', '.jpeg', '.png', '.pdf'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (validExtensions.includes(ext)) {
      setSelectedFile(file);
    } else {
      alert('Vui lòng chọn file ảnh (.jpg, .png) hoặc file .pdf.');
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    onProcess(selectedFile, selectedModel);
  };

  const availableModels = health?.ollama.models || [];

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-lg font-bold text-slate-800">Tải lên Bảng điểm</h2>
          <p className="text-sm text-slate-500">Chấp nhận file ảnh (PNG, JPG) hoặc file PDF học tập</p>
        </div>

        {/* Model selection and Ollama connection status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 text-xs font-medium text-slate-700">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                health?.ollama.online ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span>{health?.ollama.online ? 'Ollama Online' : 'Ollama Offline'}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-slate-500" />
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-800 font-medium focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="llama3.2-vision">llama3.2-vision (Khuyên dùng)</option>
              {availableModels
                .filter((m) => m !== 'llama3.2-vision')
                .map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
            </select>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
            dragActive
              ? 'border-indigo-500 bg-indigo-50/50'
              : selectedFile
              ? 'border-emerald-400 bg-emerald-50/20'
              : 'border-slate-300 hover:border-slate-400 bg-slate-50/50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            onChange={handleChange}
            className="hidden"
          />

          <div className="flex flex-col items-center justify-center space-y-3">
            {selectedFile ? (
              <>
                <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                  {selectedFile.name.endsWith('.pdf') ? (
                    <FileText className="w-7 h-7" />
                  ) : (
                    <ImageIcon className="w-7 h-7" />
                  )}
                </div>
                <div>
                  <p className="font-semibold text-slate-800 text-sm">{selectedFile.name}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {(selectedFile.size / 1024).toFixed(1)} KB — Nhấp để đổi file khác
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="w-14 h-14 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <div>
                  <p className="font-semibold text-slate-700 text-sm">
                    Kéo thả file vào đây, hoặc <span className="text-indigo-600 underline">duyệt từ máy</span>
                  </p>
                  <p className="text-xs text-slate-400 mt-1">Hỗ trợ JPG, PNG, PDF (Scan hoặc Text)</p>
                </div>
              </>
            )}
          </div>
        </div>

        <button
          type="submit"
          disabled={!selectedFile || isLoading}
          className={`w-full py-3.5 px-4 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition shadow-sm ${
            !selectedFile || isLoading
              ? 'bg-indigo-100 text-indigo-400 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-200'
          }`}
        >
          {isLoading ? (
            <div className="flex flex-col items-center py-1">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                <span className="font-semibold text-indigo-700">
                  Đang phân tích bảng điểm bằng Ollama Vision & OpenCV...
                </span>
              </div>
              <span className="text-[11px] text-indigo-500 mt-1">
                Mô hình Vision chạy offline trên CPU (thường mất 30-60s) - Vui lòng đợi trong giây lát...
              </span>
            </div>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" />
              <span>Bắt đầu Quét & Lọc Môn Không Đạt</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
