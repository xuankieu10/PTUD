import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { 
  User, 
  Mail, 
  Lock, 
  Eye, 
  EyeOff, 
  GraduationCap, 
  ArrowLeft, 
  UserPlus, 
  CheckCircle2, 
  AlertCircle,
  Sparkles,
  ShieldCheck,
  BookOpen
} from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';

// Zod Schema Validation theo 4 trường chuẩn
const signUpSchema = z.object({
  fullName: z
    .string()
    .trim()
    .min(1, 'Vui lòng nhập họ và tên'),
  studentId: z
    .string()
    .trim()
    .regex(/^\d{9}$/, 'MSSV phải gồm đúng 9 chữ số'),
  email: z
    .string()
    .trim()
    .min(1, 'Email không hợp lệ')
    .email('Email không hợp lệ'),
  password: z
    .string()
    .min(1, 'Vui lòng nhập mật khẩu')
});

export type SignUpFormData = z.infer<typeof signUpSchema>;

interface SignUpPageProps {
  onBackToHome: () => void;
  onOpenLogin: () => void;
}

export const SignUpPage: React.FC<SignUpPageProps> = ({ onBackToHome, onOpenLogin }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors }
  } = useForm<SignUpFormData>({
    resolver: zodResolver(signUpSchema),
    defaultValues: {
      fullName: '',
      studentId: '',
      email: '',
      password: ''
    }
  });

  const onSubmit = async (data: SignUpFormData) => {
    setIsLoading(true);
    setServerError(null);

    try {
      // Giả lập cuộc gọi API đăng ký (mock delay)
      // TODO: Nối API backend POST /auth/register
      // Dữ liệu gửi đi gồm: fullName, studentId, email, password
      await new Promise((resolve) => setTimeout(resolve, 1200));

      console.log('Mock registration data:', {
        fullName: data.fullName,
        studentId: data.studentId,
        email: data.email,
        password: data.password
      });

      setIsSuccess(true);
    } catch {
      setServerError('Đã xảy ra lỗi khi tạo tài khoản. Vui lòng thử lại sau.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0F1B2D] text-slate-800 dark:text-slate-100 flex flex-col justify-center py-6 sm:py-12 px-4 sm:px-6 lg:px-8 transition-colors">
      
      {/* Top Header Return Bar */}
      <div className="max-w-5xl w-full mx-auto mb-6 flex items-center justify-between">
        <button
          onClick={onBackToHome}
          className="inline-flex items-center gap-2 text-xs sm:text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Quay lại Trang chủ
        </button>

        <div className="flex items-center gap-2">
          <LhuLogo size="sm" variant="avatar" />
          <span className="text-sm font-black text-[#1565C0] dark:text-[#4D8FE0]">HocVuAI</span>
        </div>
      </div>

      {/* Main 2-Column Card Container */}
      <div className="max-w-5xl w-full mx-auto rounded-3xl bg-white dark:bg-[#162338] border border-slate-200 dark:border-slate-700/80 shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12">
        
        {/* Left Column: Sign Up Form (7 cols on lg) */}
        <div className="p-6 sm:p-10 lg:p-12 lg:col-span-7 flex flex-col justify-center">
          <div>
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-[#1565C0] dark:bg-blue-900/40 dark:text-[#4D8FE0]">
                <UserPlus className="w-3.5 h-3.5" />
                Đăng Ký Tài Khoản Mới
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                Tạo Tài Khoản HocVuAI
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300">
                Nhập thông tin sinh viên để đồng bộ hồ sơ học vụ và chuẩn đầu ra.
              </p>
            </div>

            {/* Success Banner */}
            {isSuccess && (
              <div className="mt-6 p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 space-y-2 animate-in fade-in duration-200">
                <div className="flex items-center gap-2 font-bold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                  Đăng ký tài khoản thành công!
                </div>
                <p className="text-xs leading-relaxed">
                  Tài khoản sinh viên đã được khởi tạo. Bạn có thể đăng nhập ngay để bắt đầu theo dõi lộ trình học tập và kiểm tra tốt nghiệp.
                </p>
                <div className="pt-2">
                  <button
                    onClick={onOpenLogin}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl cursor-pointer shadow-xs"
                  >
                    Đăng nhập ngay
                  </button>
                </div>
              </div>
            )}

            {/* Error Banner */}
            {serverError && (
              <div className="mt-4 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                {serverError}
              </div>
            )}

            {/* Form 4 trường */}
            {!isSuccess && (
              <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4.5" noValidate>
                
                {/* 1. Họ và tên */}
                <div>
                  <label htmlFor="fullName" className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    Họ và tên <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      id="fullName"
                      type="text"
                      placeholder="Nguyễn Văn A"
                      {...register('fullName')}
                      className={`w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-[#1A2942] border ${
                        errors.fullName ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-200 dark:border-slate-700 focus:ring-blue-500'
                      } text-slate-900 dark:text-white focus:outline-none focus:ring-2 transition-all`}
                    />
                  </div>
                  {errors.fullName && (
                    <p className="mt-1 text-[11px] text-rose-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 inline shrink-0" />
                      {errors.fullName.message}
                    </p>
                  )}
                </div>

                {/* 2. Mã số sinh viên (MSSV - đúng 9 chữ số) */}
                <div>
                  <label htmlFor="studentId" className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    Mã số sinh viên (MSSV) <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <GraduationCap className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      id="studentId"
                      type="text"
                      inputMode="numeric"
                      maxLength={9}
                      placeholder="Nhập đúng 9 chữ số (ví dụ: 121000123)"
                      {...register('studentId', {
                        onChange: (e) => {
                          // Tự động loại bỏ ký tự không phải số và giới hạn 9 chữ số
                          const sanitized = e.target.value.replace(/\D/g, '').slice(0, 9);
                          e.target.value = sanitized;
                          setValue('studentId', sanitized, { shouldValidate: true });
                        }
                      })}
                      className={`w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-[#1A2942] border ${
                        errors.studentId ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-200 dark:border-slate-700 focus:ring-blue-500'
                      } text-slate-900 dark:text-white focus:outline-none focus:ring-2 font-mono transition-all`}
                    />
                  </div>
                  {errors.studentId && (
                    <p className="mt-1 text-[11px] text-rose-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 inline shrink-0" />
                      {errors.studentId.message}
                    </p>
                  )}
                </div>

                {/* 3. Email */}
                <div>
                  <label htmlFor="email" className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    Email <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      id="email"
                      type="email"
                      placeholder="nguyenvana@lhu.edu.vn"
                      {...register('email')}
                      className={`w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-[#1A2942] border ${
                        errors.email ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-200 dark:border-slate-700 focus:ring-blue-500'
                      } text-slate-900 dark:text-white focus:outline-none focus:ring-2 transition-all`}
                    />
                  </div>
                  {errors.email && (
                    <p className="mt-1 text-[11px] text-rose-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 inline shrink-0" />
                      {errors.email.message}
                    </p>
                  )}
                </div>

                {/* 4. Mật khẩu (chỉ cần không để trống, không áp đặt quy tắc) */}
                <div>
                  <label htmlFor="password" className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                    Mật khẩu <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      {...register('password')}
                      className={`w-full pl-10 pr-10 py-2.5 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-[#1A2942] border ${
                        errors.password ? 'border-rose-500 focus:ring-rose-500' : 'border-slate-200 dark:border-slate-700 focus:ring-blue-500'
                      } text-slate-900 dark:text-white focus:outline-none focus:ring-2 transition-all`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                      tabIndex={-1}
                      aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="mt-1 text-[11px] text-rose-500 font-medium flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 inline shrink-0" />
                      {errors.password.message}
                    </p>
                  )}
                </div>

                {/* Submit Button */}
                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3 px-4 text-sm font-bold text-white bg-gradient-to-r from-[#1565C0] to-[#3F51B5] hover:from-[#0D47A1] hover:to-[#303F9F] rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-70 active:scale-[0.99]"
                  >
                    {isLoading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Đang tạo tài khoản...
                      </>
                    ) : (
                      <>
                        <UserPlus className="w-4 h-4" />
                        Đăng Ký
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Footer Link */}
          <div className="mt-8 pt-4 border-t border-slate-100 dark:border-slate-800 text-center text-xs text-slate-500">
            Đã có tài khoản?{' '}
            <button
              onClick={onOpenLogin}
              className="text-[#1565C0] dark:text-[#4D8FE0] font-bold hover:underline cursor-pointer"
            >
              Đăng nhập
            </button>
          </div>
        </div>

        {/* Right Column: Hero Visual & Slogan (5 cols on lg, hidden on mobile) */}
        <div className="hidden lg:flex lg:col-span-5 p-10 bg-gradient-to-br from-[#0D47A1] via-[#1565C0] to-[#3949AB] text-white flex-col justify-between relative overflow-hidden">
          
          {/* Subtle Background Glows */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-400/15 rounded-full blur-2xl pointer-events-none" />

          {/* Top Brand */}
          <div className="relative z-10 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 flex items-center justify-center shadow-lg">
              <LhuLogo size="lg" variant="avatar" />
            </div>
            
            <h3 className="text-2xl font-black tracking-tight leading-snug">
              Đồng Hành Cùng Sinh Viên LHU Chinh Phục Tấm Bằng Tốt Nghiệp
            </h3>
            
            <p className="text-xs text-blue-100/90 leading-relaxed font-normal">
              Đăng ký để AI tự động theo dõi tiến độ tích lũy 150 tín chỉ và bảo vệ bạn khỏi các sai sót về quy chế học phần.
            </p>
          </div>

          {/* Core Values Bullet List */}
          <div className="relative z-10 space-y-3.5 my-8">
            <div className="p-3.5 rounded-2xl bg-white/10 backdrop-blur-xs border border-white/15 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-400/20 flex items-center justify-center shrink-0 text-blue-200 mt-0.5">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-bold text-white block">Đối soát chuẩn 150 tín chỉ</span>
                <span className="text-blue-100/80">Tự động phát hiện các môn bắt buộc chưa học hoặc nợ điểm.</span>
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-white/10 backdrop-blur-xs border border-white/15 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-400/20 flex items-center justify-center shrink-0 text-blue-200 mt-0.5">
                <BookOpen className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-bold text-white block">Quy chế Điều 27 & Thi lại lần 2</span>
                <span className="text-blue-100/80">Hướng dẫn làm đơn, link form trực tuyến và group Zalo hỗ trợ.</span>
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-white/10 backdrop-blur-xs border border-white/15 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-400/20 flex items-center justify-center shrink-0 text-blue-200 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="text-xs">
                <span className="font-bold text-white block">Bảo mật dữ liệu cá nhân</span>
                <span className="text-blue-100/80">Cô lập dữ liệu tuyệt đối theo tiêu chuẩn mã hóa JWT.</span>
              </div>
            </div>
          </div>

          {/* Bottom Trust Badge */}
          <div className="relative z-10 pt-4 border-t border-white/15 text-[11px] text-blue-200/90 flex items-center justify-between">
            <span>Trường Đại học Lạc Hồng</span>
            <span>Khoa Công nghệ Thông tin</span>
          </div>

        </div>

      </div>

    </div>
  );
};
