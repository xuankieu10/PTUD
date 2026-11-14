import React from 'react';
import { Award, BookCheck, ShieldAlert, Cpu } from 'lucide-react';

export const StatsSection: React.FC = () => {
  const stats = [
    {
      icon: Award,
      value: '150',
      unit: 'Tín chỉ',
      label: 'Chuẩn đầu ra tốt nghiệp',
      desc: 'Áp dụng cho chương trình đào tạo đại học chính quy 8 học kỳ tại LHU.'
    },
    {
      icon: BookCheck,
      value: '100%',
      unit: 'Chính xác',
      label: 'Trích dẫn quy chế đào tạo',
      desc: 'Toàn bộ nội dung tư vấn đều đính kèm điều khoản, văn bản và số hiệu xác thực.'
    },
    {
      icon: Cpu,
      value: '202',
      unit: 'Test Cases',
      label: 'Kiểm định chất lượng',
      desc: 'Hệ thống vượt qua 100% các ca kiểm thử bảo mật, chống bịa và phân quyền sinh viên.'
    },
    {
      icon: ShieldAlert,
      value: '3 Nhánh',
      unit: 'Phân loại',
      label: 'Xử lý môn chưa đạt',
      desc: 'Phân biệt minh bạch giữa cấm thi (học lại), được thi lần 2 và xác nhận giáo vụ.'
    }
  ];

  return (
    <section id="stats" className="py-16 md:py-20 bg-gradient-to-r from-[#1565C0] via-[#283593] to-[#3949AB] text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {stats.map((s, i) => {
            const Icon = s.icon;
            return (
              <div 
                key={i}
                className="p-6 rounded-2xl bg-white/10 backdrop-blur-md border border-white/15 flex flex-col justify-between"
              >
                <div>
                  <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center mb-4">
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-3xl sm:text-4xl font-black tracking-tight">{s.value}</span>
                    <span className="text-sm font-semibold text-blue-200">{s.unit}</span>
                  </div>

                  <h4 className="mt-2 text-base font-bold text-white">
                    {s.label}
                  </h4>
                  <p className="mt-1 text-xs text-blue-100/80 leading-relaxed">
                    {s.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

