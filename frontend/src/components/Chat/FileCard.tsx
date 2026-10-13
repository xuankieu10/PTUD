import React from 'react';
import { FileText, Image as ImageIcon, FileCode, File, X, Loader2 } from 'lucide-react';
import type { AttachedFile } from '../../types';

interface FileCardProps {
  file: AttachedFile;
  onRemove?: () => void;
  isUploading?: boolean;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext || '')) {
    return <ImageIcon className="w-4 h-4 text-amber-500" />;
  }
  if (['pdf'].includes(ext || '')) {
    return <FileText className="w-4 h-4 text-rose-500" />;
  }
  if (['docx', 'doc'].includes(ext || '')) {
    return <FileText className="w-4 h-4 text-blue-500" />;
  }
  if (['txt'].includes(ext || '')) {
    return <FileCode className="w-4 h-4 text-emerald-500" />;
  }
  return <File className="w-4 h-4 text-gray-500" />;
}

export const FileCard: React.FC<FileCardProps> = ({ file, onRemove, isUploading = false }) => {
  return (
    <div className="relative group inline-flex items-center gap-2 px-3 py-2 bg-white border border-[#E5E7EB] rounded-2xl shadow-2xs text-xs text-[#1F1F1F] max-w-[240px] animate-fade-in select-none">
      <div className="shrink-0 p-1 bg-gray-50 rounded-lg">
        {getFileIcon(file.name)}
      </div>

      <div className="min-w-0 flex-1 pr-1">
        <p className="font-medium truncate text-xs" title={file.name}>
          {file.name}
        </p>
        <p className="text-[10px] text-[#8E8E93]">
          {formatFileSize(file.size)}
        </p>
      </div>

      {isUploading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400 shrink-0 ml-1" />
      ) : onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          className="p-1 rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition shrink-0"
          title="Bỏ tệp này"
          aria-label={`Bỏ tệp ${file.name}`}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      ) : null}
    </div>
  );
};
