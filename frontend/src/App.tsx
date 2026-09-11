import { useState, useEffect } from 'react';
import { GraduationCap, Terminal, AlertTriangle, RefreshCw } from 'lucide-react';
import { FileUploader } from './components/FileUploader';
import { ResultSummary } from './components/ResultSummary';
import { TranscriptTable } from './components/TranscriptTable';
import { VisualPreview } from './components/VisualPreview';
import type { ProcessResponse, OllamaHealth } from './types';

export function App() {
  const [health, setHealth] = useState<OllamaHealth | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health');
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
      const res = await fetch('/api/process', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Lỗi máy chủ (${res.status})`);
      }

      const data: ProcessResponse = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Đã xảy ra lỗi trong quá trình xử lý bảng điểm.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 pb-16">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-100">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 leading-tight">
                Hệ Thống Trích Xuất & Lọc Môn Không Đạt
              </h1>
              <p className="text-xs text-slate-500">
                Pipeline cục bộ: Ollama Vision (<span className="font-mono">llama3.2-vision</span>) + OpenCV HSV
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
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto px-4 pt-8 space-y-6">
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
      </main>
    </div>
  );
}

export default App;
