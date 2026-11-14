import React from 'react';
import { LhuLogo } from '../Common/LhuLogo';
import { MapPin, Phone, Mail, Globe, Shield, ExternalLink } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-900 text-slate-300 pt-16 pb-12 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10">
          
          {/* Col 1: Brand & Intro */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <LhuLogo size="md" variant="avatar" className="shadow-xs" />
              <div className="flex flex-col">
                <span className="text-xl font-black text-white tracking-tight">
                  HocVu<span className="text-blue-400">AI</span>
                </span>
                <span className="text-xs text-slate-400 font-medium">
                  Đại học Lạc Hồng (LHU)
                </span>
              </div>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Hệ thống trợ lý AI tư vấn quy chế đào tạo tín chỉ, đối soát chuẩn đầu ra 150 tín chỉ và hỗ trợ kế hoạch học tập cá nhân hóa cho sinh viên LHU.
            </p>
          </div>

          {/* Col 2: Quick Links */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider">
              Liên Kết Nhanh
            </h4>
            <ul className="space-y-2 text-xs sm:text-sm">
              <li>
                <a href="#features" className="hover:text-blue-400 transition-colors">
                  Tính năng hệ thống
                </a>
              </li>
              <li>
                <a href="#how-it-works" className="hover:text-blue-400 transition-colors">
                  Hướng dẫn 3 bước sử dụng
                </a>
              </li>
              <li>
                <a href="#stats" className="hover:text-blue-400 transition-colors">
                  Chuẩn đầu ra 150 tín chỉ
                </a>
              </li>
              <li>
                <a href="#faq" className="hover:text-blue-400 transition-colors">
                  Câu hỏi thường gặp
                </a>
              </li>
            </ul>
          </div>

          {/* Col 3: Cổng Thông Tin LHU */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider">
              Cổng Thông Tin ĐH Lạc Hồng
            </h4>
            <ul className="space-y-2 text-xs sm:text-sm">
              <li>
                <a 
                  href="https://cs.lhu.edu.vn" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-blue-400 inline-flex items-center gap-1.5 transition-colors"
                >
                  <Globe className="w-3.5 h-3.5" />
                  Khoa CNTT (cs.lhu.edu.vn)
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
              </li>
              <li>
                <a 
                  href="https://nnth.lhu.edu.vn" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-blue-400 inline-flex items-center gap-1.5 transition-colors"
                >
                  <Globe className="w-3.5 h-3.5" />
                  Trung tâm Ngoại ngữ - Tin học
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
              </li>
              <li>
                <a 
                  href="https://calen.lhu.edu.vn" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-blue-400 inline-flex items-center gap-1.5 transition-colors"
                >
                  <Globe className="w-3.5 h-3.5" />
                  Cổng tra cứu lịch học & lịch thi
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
              </li>
              <li>
                <a 
                  href="https://graduate.lhu.edu.vn" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="hover:text-blue-400 inline-flex items-center gap-1.5 transition-colors"
                >
                  <Globe className="w-3.5 h-3.5" />
                  Cổng nộp hồ sơ tốt nghiệp
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
              </li>
            </ul>
          </div>

          {/* Col 4: Liên Hệ Giáo Vụ */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-white uppercase tracking-wider">
              Văn Phòng Khoa CNTT
            </h4>
            <div className="space-y-2.5 text-xs text-slate-400">
              <div className="flex items-start gap-2">
                <MapPin className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <span>Phòng B301 - B302, Cơ sở 1, Số 10 Huỳnh Văn Nghệ, P. Bửu Long, Biên Hòa, Đồng Nai</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-blue-400 shrink-0" />
                <span>02513.952.251</span>
              </div>
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-blue-400 shrink-0" />
                <span>cntt@lhu.edu.vn</span>
              </div>
              <div className="pt-1 text-[11px] text-slate-500">
                Giờ làm việc: Thứ Hai - Thứ Sáu (7h30–11h30 | 13h00–16h30)
              </div>
            </div>
          </div>

        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© 2026 HocVuAI • Dự án Trợ lý Tư vấn Học vụ Đại học Lạc Hồng. Bảo lưu mọi quyền.</p>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1 text-slate-400">
              <Shield className="w-3.5 h-3.5 text-blue-400" />
              Bảo mật dữ liệu cá nhân chuẩn giáo dục
            </span>
          </div>
        </div>

      </div>
    </footer>
  );
};

