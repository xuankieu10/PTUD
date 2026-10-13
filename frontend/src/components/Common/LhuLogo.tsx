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
    sm: 'w-6 h-6',
    md: 'w-7 h-7',
    lg: 'w-11 h-11',
    xl: 'w-16 h-16',
  };

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 rounded-full select-none ${sizeMap[size]} ${className}`}
      style={{
        background: 'linear-gradient(135deg, #FFC837 0%, #F5B800 45%, #E59800 100%)',
        boxShadow: withGlow
          ? '0 0 0 10px rgba(245, 184, 0, 0.12), 0 0 0 20px rgba(245, 184, 0, 0.05)'
          : '0 1px 3px rgba(0,0,0,0.1)',
      }}
    >
      {/* Golden Shutter / Aperture / Spiral Swirl Emblem exactly like LHU AI screenshot */}
      <svg
        className="w-[62%] h-[62%]"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Swirl / Shutter blades in white */}
        <path
          d="M12 2C8.5 2 5.5 3.8 3.8 6.5L7.5 10.2C8.2 8.3 10 7 12 7C12.3 7 12.6 7 12.9 7.1L15.4 3.3C14.3 2.5 13.2 2 12 2Z"
          fill="white"
          fillOpacity="0.95"
        />
        <path
          d="M20.2 6.5C18.5 3.8 15.5 2 12 2V6C13.8 6 15.3 7 16.2 8.5L20.2 6.5Z"
          fill="white"
          fillOpacity="0.8"
        />
        <path
          d="M21.7 10.5L17.2 11.8C17 12.7 16.5 13.5 15.8 14.2L18.7 18C20.5 16 21.6 13.4 21.7 10.5Z"
          fill="white"
          fillOpacity="0.95"
        />
        <path
          d="M15.8 14.2C14.8 15.3 13.5 16 12 16L12 20.5C14.6 20.5 17 19.5 18.7 18L15.8 14.2Z"
          fill="white"
          fillOpacity="0.85"
        />
        <path
          d="M8.2 14.2L5.3 18C7 19.5 9.4 20.5 12 20.5V16C10.5 16 9.2 15.3 8.2 14.2Z"
          fill="white"
          fillOpacity="0.95"
        />
        <path
          d="M2.3 10.5C2.4 13.4 3.5 16 5.3 18L8.2 14.2C7.5 13.5 7 12.7 6.8 11.8L2.3 10.5Z"
          fill="white"
          fillOpacity="0.85"
        />
        <circle cx="12" cy="11.5" r="2.2" fill="#E59800" />
      </svg>
    </div>
  );
};
