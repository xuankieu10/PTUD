import React from 'react';

interface LhuLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  withGlow?: boolean;
}

export const LhuLogo: React.FC<LhuLogoProps> = ({
  size = 'md',
  className = '',
  withGlow = false,
}) => {
  const sizeMap = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-14 h-14 text-xl',
    xl: 'w-20 h-20 text-3xl',
  };

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 rounded-full font-bold select-none transition-transform ${sizeMap[size]} ${className}`}
      style={{
        background: 'linear-gradient(135deg, #FFD000 0%, #F5B800 50%, #E69D00 100%)',
        boxShadow: withGlow
          ? '0 0 0 6px rgba(245, 184, 0, 0.15), 0 8px 24px -4px rgba(245, 184, 0, 0.4)'
          : '0 2px 6px rgba(245, 184, 0, 0.25)',
      }}
    >
      {/* Subtle inner highlight */}
      <div className="absolute inset-0.5 rounded-full border border-white/40 pointer-events-none" />

      {/* SVG Icon / Emblem */}
      <svg
        className="w-3/5 h-3/5 text-[#1F1F1F]"
        viewBox="0 0 24 24"
        fill="currentColor"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="M12 2L2 7L12 12L22 7L12 2Z" />
        <path
          d="M2 17L12 22L22 17"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M2 12L12 17L22 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};
