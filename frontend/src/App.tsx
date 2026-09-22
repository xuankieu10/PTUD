import { useState, useEffect } from 'react';
import { GraduationCap, Terminal, AlertTriangle, RefreshCw, FileText, Award } from 'lucide-react';
import { FileUploader } from './components/FileUploader';
import { ResultSummary } from './components/ResultSummary';
import { TranscriptTable } from './components/TranscriptTable';
import { VisualPreview } from './components/VisualPreview';
import { CertificateScanner } from './components/CertificateScanner';
import type { ProcessResponse, CertificateProcessResponse, OllamaHealth } from './types';

export function App() {
  const [activeTab, setActiveTab] = useState<'transcript' | 'certificate'>('transcript');
  const [health, setHealth] = useState<OllamaHealth | null>(null);

  // State cho Pipeline Bảng điểm
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // State cho Pipeline Chứng chỉ
  const [isCertLoading, setIsCertLoading] = useState(false);
  const [certResult, setCertResult] = useState<CertificateProcessResponse | null>(null);
  const [certError, setCertError] = useState<string | null>(null);

  // Hỗ trợ cấu hình Base URL linh hoạt khi deploy độc lập
  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || '';

  // Hàm bóc tách thông báo lỗi an toàn từ response backend
  const extractErrorMessage = (errorData: any, status: number): string => {
    if (typeof errorData?.detail === 'string') {
      return errorData.detail;
    }
    if (Array.isArray(errorData?.detail)) {
      return errorData.detail
        .map((item: any) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item)))
        .join('; ');
    }
    if (typeof errorData?.message === 'string') {
      return errorData.message;
    }
    return `Lỗi máy chủ (${status})`;
  };

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`);
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (e) {
      console.warn('Chưa kết nối được Backend:', e);
      setHealth(null);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleProcessFile = async (file: File, model: string) => {
    setIsLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', model);

    try {
      const res = await fetch(`${API_BASE_URL}/api/process`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, res.status));
      }

      const data: ProcessResponse = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Đã xảy ra lỗi trong quá trình xử lý bảng điểm.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleProcessCertificate = async (file: File, model: string) => {
    setIsCertLoading(true);
    setCertError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', model);

    try {
      const res = await fetch(`${API_BASE_URL}/api/certificate/process`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, res.status));
      }

      const data: CertificateProcessResponse = await res.json();
      setCertResult(data);
    } catch (err: any) {
      setCertError(err.message || 'Đã xảy ra lỗi trong quá trình xử lý chứng chỉ.');
    } finally {
      setIsCertLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 pb-16">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-100">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 leading-tight">
                Hệ Thống Xét Tốt Nghiệp & Trích Xuất Học Vụ AI
              </h1>
              <p className="text-xs text-slate-500">
                Pipeline cục bộ: Ollama Vision + OpenCV HSV + RapidFuzz
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchHealth}
              title="Làm mới trạng thái kết nối"
              className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 bg-slate-100 rounded-lg text-xs font-mono text-slate-600">
              <Terminal className="w-3.5 h-3.5" />
              <span>Local Pipeline</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="max-w-6xl mx-auto px-4 pt-1 flex items-center gap-2 border-t border-slate-100">
          <button
            onClick={() => setActiveTab('transcript')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition ${
              activeTab === 'transcript'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            1. Bảng Điểm & Lọc Môn Không Đạt
          </button>

          <button
            onClick={() => setActiveTab('certificate')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition ${
              activeTab === 'certificate'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Award className="w-4 h-4" />
            2. Quét & Đối Chiếu Chứng Chỉ Tốt Nghiệp
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto px-4 pt-6 space-y-6">
        {/* Offline Ollama Warning */}
        {health && !health.ollama.online && (
          <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
            <div className="text-xs text-rose-800 space-y-1">
              <p className="font-semibold">Ollama chưa được khởi chạy hoặc không phản hồi tại {health.ollama.host}!</p>
              <p>
                Vui lòng mở terminal và chạy: <code className="bg-white px-2 py-0.5 rounded border border-rose-200 font-mono">ollama serve</code> và kéo model <code className="bg-white px-2 py-0.5 rounded border border-rose-200 font-mono">ollama pull llama3.2-vision</code>
              </p>
            </div>
          </div>
        )}

        {/* TAB 1: BẢNG ĐIỂM HỌC TẬP (GIỮ NGUYÊN 100%) */}
        {activeTab === 'transcript' && (
          <div className="space-y-6">
            {/* Error message */}
            {error && (
              <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 flex items-center justify-between text-rose-700 text-sm">
                <span>{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-xs underline hover:text-rose-900 ml-4 font-medium"
                >
                  Đóng
                </button>
              </div>
            )}

            {/* Upload Component */}
            <FileUploader
              onProcess={handleProcessFile}
              isLoading={isLoading}
              health={health}
            />

            {/* Processing Results */}
            {result && (
              <div className="space-y-6 animate-in fade-in duration-300">
                {/* Statistics */}
                <ResultSummary summary={result.summary} />

                {/* Visualizer and Results Table */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Table */}
                  <div className={result.annotated_image ? 'lg:col-span-7' : 'lg:col-span-12'}>
                    <TranscriptTable
                      failedSubjects={result.failed_subjects}
                      allSubjects={result.all_subjects}
                      sessionId={result.session_id}
                    />
                  </div>

                  {/* OpenCV Visualizer */}
                  {result.annotated_image && (
                    <div className="lg:col-span-5">
                      <VisualPreview
                        annotatedImage={result.annotated_image}
                        filename={result.filename}
                      />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: QUÉT CHỨNG CHỈ TỐT NGHIỆP (TÍNH NĂNG MỚI) */}
        {activeTab === 'certificate' && (
          <CertificateScanner
            health={health}
            onProcess={handleProcessCertificate}
            isLoading={isCertLoading}
            result={certResult}
            error={certError}
            onReset={() => {
              setCertResult(null);
              setCertError(null);
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
