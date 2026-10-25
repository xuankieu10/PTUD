import React, { useState } from 'react';

interface LhuLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'full' | 'avatar';
  className?: string;
  withGlow?: boolean;
  alt?: string;
}

export const LhuLogo: React.FC<LhuLogoProps> = ({
  size = 'md',
  variant = 'avatar',
  className = '',
  withGlow = false,
  alt = 'Khoa Công nghệ Thông tin',
}) => {
  const [hasError, setHasError] = useState(false);

  // Size mapping for circular avatar
  const avatarSizeMap = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-14 h-14',
    xl: 'w-20 h-20',
  };

  // Size mapping for full horizontal logo
  const fullSizeMap = {
    sm: 'h-7 max-w-[120px]',
    md: 'h-9 max-w-[150px]',
    lg: 'h-16 max-w-[220px]',
    xl: 'h-24 max-w-[300px]',
  };

  if (variant === 'full') {
    return (
      <div
        className={`inline-flex items-center justify-center p-1 rounded-xl bg-white/90 dark:bg-white/10 backdrop-blur-xs shadow-xs border border-slate-200/60 dark:border-white/10 ${fullSizeMap[size]} ${className}`}
      >
        <img
          src="/fit-logo-transparent.png"
          alt={alt}
          className="h-full w-auto max-w-full object-contain select-none"
          loading="eager"
          onError={() => setHasError(true)}
        />
        {hasError && (
          <span className="text-xs font-bold text-[#1565C0] px-2 truncate">
            KHOA CNTT
          </span>
        )}
      </div>
    );
  }

  // Variant avatar (circle emblem from center of Khoa CNTT logo)
  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 rounded-full select-none overflow-hidden bg-white shadow-xs border border-blue-100 dark:border-blue-900/60 ${avatarSizeMap[size]} ${className}`}
      style={{
        boxShadow: withGlow
          ? '0 0 0 8px rgba(21, 101, 192, 0.12), 0 0 0 16px rgba(21, 101, 192, 0.05)'
          : '0 1px 3px rgba(0,0,0,0.08)',
      }}
    >
      <img
        src="/fit-avatar.png"
        alt={alt}
        className="w-full h-full object-cover rounded-full"
        loading="eager"
        onError={() => setHasError(true)}
      />
      {hasError && (
        <span className="text-[10px] font-bold text-[#1565C0] uppercase">
          IT
        </span>
      )}
    </div>
  );
};
