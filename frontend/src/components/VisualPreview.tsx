import type { FC } from 'react';
import { Eye } from 'lucide-react';

interface VisualPreviewProps {
  annotatedImage: string | null;
  filename: string;
}

export const VisualPreview: FC<VisualPreviewProps> = ({ annotatedImage, filename }) => {
  if (!annotatedImage) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Eye className="w-5 h-5 text-indigo-600" />
          <h3 className="font-bold text-slate-800 text-sm">Hình ảnh Giám sát & Vùng Đỏ (OpenCV)</h3>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 border-2 border-red-600 inline-block rounded-xs" />
            Vùng màu đỏ OpenCV
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 border-2 border-amber-500 inline-block rounded-xs" />
            Môn học bị gắn cờ
          </span>
        </div>
      </div>

      <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-900/5 flex items-center justify-center p-2 max-h-[600px]">
        <img
          src={annotatedImage}
          alt={`Annotated preview for ${filename}`}
          className="max-h-[580px] w-auto object-contain rounded-lg shadow-sm"
        />
      </div>
      <p className="text-center text-xs text-slate-400 mt-3">
        Hình ảnh được phân tích bởi OpenCV HSV Thresholding kết hợp Bounding Box Matching với dòng text.
      </p>
    </div>
  );
};
