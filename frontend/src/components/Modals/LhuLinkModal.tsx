import React, { useState, useEffect } from 'react';
import {
  X,
  Link2,
  Unlink,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Award,
  BookOpen,
  Clock,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import type { UserProfile } from '../../types';
import { lhuApi, type LhuLinkStatus } from '../../services/api';

interface LhuLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile | null;
  onLinkedSuccess?: () => void;
}

export const LhuLinkModal: React.FC<LhuLinkModalProps> = ({
  isOpen,
  onClose,
  user,
  onLinkedSuccess,
}) => {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingData, setIsFetchingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<LhuLinkStatus | null>(null);
  const [transcript, setTranscript] = useState<any | null>(null);
  const [certificates, setCertificates] = useState<any[] | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'courses' | 'certificates'>('overview');

  // Khởi tạo và kiểm tra trạng thái liên kết
  useEffect(() => {
    if (!isOpen || !user) return;

    if (!studentId && (user.student_code || user.username)) {
      setStudentId(user.student_code || user.username);
    }

    checkStatusAndLoadData();
  }, [isOpen, user]);

  const checkStatusAndLoadData = async () => {
    setIsFetchingData(true);
    setError(null);
    try {
      const linkStatus = await lhuApi.getStatus();
      setStatus(linkStatus);

      if (linkStatus.linked) {
        // Tải bảng điểm và chứng chỉ
        const [transData, certsData] = await Promise.allSettled([
          lhuApi.getTranscript(),
          lhuApi.getCertificates(),
        ]);

        if (transData.status === 'fulfilled') {
          setTranscript(transData.value);
        }
        if (certsData.status === 'fulfilled') {
          setCertificates(certsData.value);
        }
      } else {
        setTranscript(null);
        setCertificates(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Không thể kiểm tra trạng thái liên kết LHU.');
    } finally {
      setIsFetchingData(false);
    }
  };

  const handleLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId.trim() || !password) {
      setError('Vui lòng nhập đầy đủ Mã số sinh viên và Mật khẩu.');
      return;
    }

    const currentPwd = password;
    // RÀNG BUỘC BẢO MẬT: Xóa ngay lập tức ô mật khẩu khỏi state trước/khi gửi
    setPassword('');
    setError(null);
    setIsLoading(true);

    try {
      await lhuApi.link(studentId.trim(), currentPwd);
      await checkStatusAndLoadData();
      if (onLinkedSuccess) {
        onLinkedSuccess();
      }
    } catch (err: any) {
      setError(err?.message || 'Đã xảy ra lỗi khi liên kết tài khoản LHU.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnlink = async () => {
    if (!window.confirm('Bạn có chắc chắn muốn hủy liên kết tài khoản LHU? Token trong RAM và dữ liệu tạm thời sẽ bị xóa.')) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await lhuApi.unlink();
      setStatus({ linked: false, student_id: null });
      setTranscript(null);
      setCertificates(null);
    } catch (err: any) {
      setError(err?.message || 'Không thể hủy liên kết tài khoản.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const isLinked = Boolean(status?.linked);
  const remainingMinutes = status?.expires_in_seconds ? Math.max(1, Math.round(status.expires_in_seconds / 60)) : 0;
  const coursesList = transcript?.courses || [];
  const passedCourses = coursesList.filter((c: any) => c.status === 'passed' || c.dat === true);
  const failedCourses = coursesList.filter((c: any) => c.status === 'failed' || c.is_failed === true);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in select-none">
      <div className="bg-white dark:bg-[#162338] rounded-3xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-700 max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header Modal */}
        <div className="flex items-center justify-between pb-3.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1565C0] dark:text-[#4D8FE0] flex items-center justify-center border border-blue-200 dark:border-blue-800">
              <Link2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <span>Liên kết tài khoản LHU</span>
                {isLinked && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800">
                    <CheckCircle2 className="w-3 h-3" />
                    Đã liên kết
                  </span>
                )}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Lấy trực tiếp bảng điểm và chứng chỉ từ Cổng trường LHU (dkmh.lhu.edu.vn)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Thông báo lỗi nếu có */}
        {error && (
          <div className="mt-3.5 p-3 rounded-2xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 shrink-0">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">Lỗi liên kết:</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Nội dung chính cuộn dọc */}
        <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-4">
          {/* CAM KẾT BẢO MẬT & ĐỒNG Ý RÕ RÀNG */}
          <div className="p-3.5 rounded-2xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/60 text-amber-900 dark:text-amber-200 text-xs flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold text-amber-800 dark:text-amber-300">
                Cam kết An toàn & Bảo mật:
              </p>
              <p className="leading-relaxed">
                Mật khẩu chỉ dùng để đăng nhập một lần, <span className="font-semibold underline">không được lưu</span> trên hệ thống máy chủ, cơ sở dữ liệu hay trình duyệt. Mã phiên (Token) chỉ lưu tạm trong bộ nhớ RAM và tự động hủy sau 30 phút.
              </p>
            </div>
          </div>

          {/* TRƯỜNG HỢP 1: CHƯA LIÊN KẾT HOẶC PHIÊN ĐÃ HẾT HẠN */}
          {!isLinked && (
            <form onSubmit={handleLink} className="space-y-3.5 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-2xl border border-slate-200/70 dark:border-slate-700">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Mã số sinh viên (MSSV)
                </label>
                <input
                  type="text"
                  required
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  placeholder="Ví dụ: 123000969"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 text-xs focus:outline-hidden focus:ring-2 focus:ring-[#1565C0] transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Mật khẩu cổng trường LHU
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu tài khoản cổng trường..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 text-xs focus:outline-hidden focus:ring-2 focus:ring-[#1565C0] transition"
                />
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  Mật khẩu sẽ được tự động xóa khỏi bộ nhớ ngay khi gửi đi.
                </p>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 px-4 rounded-xl bg-[#1565C0] hover:bg-[#0D47A1] text-white text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer shadow-sm disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Đang kết nối cổng trường...</span>
                  </>
                ) : (
                  <>
                    <Link2 className="w-4 h-4" />
                    <span>Liên kết tài khoản LHU</span>
                  </>
                )}
              </button>
            </form>
          )}

          {/* TRƯỜNG HỢP 2: ĐÃ LIÊN KẾT THÀNH CÔNG */}
          {isLinked && (
            <div className="space-y-4">
              {/* Thẻ trạng thái & Thời gian phiên */}
              <div className="p-3.5 rounded-2xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/80 flex items-center justify-between">
                <div>
                  <p className="font-bold text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span>Đã kết nối tài khoản MSSV: {status?.student_id}</span>
                  </p>
                  <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5 flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Phiên làm việc còn: {remainingMinutes} phút (tự động hết hạn để bảo mật)</span>
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={checkStatusAndLoadData}
                    disabled={isFetchingData}
                    title="Làm mới dữ liệu từ cổng trường"
                    className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isFetchingData ? 'animate-spin' : ''}`} />
                  </button>

                  <button
                    type="button"
                    onClick={handleUnlink}
                    disabled={isLoading}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/50 dark:hover:bg-rose-900/60 text-rose-700 dark:text-rose-300 text-xs font-medium border border-rose-200 dark:border-rose-900 transition cursor-pointer"
                  >
                    <Unlink className="w-3.5 h-3.5" />
                    <span>Hủy liên kết</span>
                  </button>
                </div>
              </div>

              {/* Tabs chuyển đổi giữa Tổng quan, Bảng điểm và Chứng chỉ */}
              <div className="flex items-center border-b border-slate-200 dark:border-slate-700 gap-1 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setActiveTab('overview')}
                  className={`pb-2 px-3 border-b-2 transition cursor-pointer ${
                    activeTab === 'overview'
                      ? 'border-[#1565C0] text-[#1565C0] dark:border-[#4D8FE0] dark:text-[#4D8FE0]'
                      : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  Tổng quan học vụ
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('courses')}
                  className={`pb-2 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                    activeTab === 'courses'
                      ? 'border-[#1565C0] text-[#1565C0] dark:border-[#4D8FE0] dark:text-[#4D8FE0]'
                      : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>Bảng điểm ({coursesList.length} môn)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('certificates')}
                  className={`pb-2 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                    activeTab === 'certificates'
                      ? 'border-[#1565C0] text-[#1565C0] dark:border-[#4D8FE0] dark:text-[#4D8FE0]'
                      : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <Award className="w-3.5 h-3.5" />
                  <span>Chứng chỉ ({certificates?.length ?? 0})</span>
                </button>
              </div>

              {/* Tab 1: Tổng quan số liệu */}
              {activeTab === 'overview' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="p-3 bg-blue-50/70 dark:bg-slate-800 rounded-xl border border-blue-100 dark:border-slate-700 text-center">
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">Tổng môn học</p>
                      <p className="text-lg font-bold text-[#1565C0] dark:text-[#4D8FE0]">{coursesList.length}</p>
                    </div>
                    <div className="p-3 bg-emerald-50/70 dark:bg-slate-800 rounded-xl border border-emerald-100 dark:border-slate-700 text-center">
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">Môn đã đạt</p>
                      <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">{passedCourses.length}</p>
                    </div>
                    <div className="p-3 bg-rose-50/70 dark:bg-slate-800 rounded-xl border border-rose-100 dark:border-slate-700 text-center">
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">Môn chưa đạt</p>
                      <p className="text-lg font-bold text-rose-600 dark:text-rose-400">{failedCourses.length}</p>
                    </div>
                  </div>

                  {transcript?.gpa_portal !== undefined && (
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700 flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-600 dark:text-slate-300">Điểm trung bình (GPA cổng trường):</span>
                      <span className="font-bold text-slate-800 dark:text-slate-100 text-sm">{transcript.gpa_portal}</span>
                    </div>
                  )}

                  {/* Tóm tắt chứng chỉ */}
                  <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-bold text-slate-700 dark:text-slate-200 mb-2 flex items-center gap-1.5">
                      <Award className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />
                      <span>Trạng thái chứng chỉ chuẩn đầu ra</span>
                    </p>
                    {certificates && certificates.length > 0 ? (
                      <div className="space-y-1.5">
                        {certificates.map((c: any, idx: number) => (
                          <div key={idx} className="flex items-center justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-700/60 last:border-0">
                            <span className="text-slate-700 dark:text-slate-300">{c.ten || c.name || 'Chứng chỉ'}</span>
                            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                              c.hoan_tat
                                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                            }`}>
                              {c.hoan_tat ? 'Đã hoàn tất' : (c.tinh_trang || 'Chưa hoàn tất')}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 dark:text-slate-400 italic">Chưa có dữ liệu chứng chỉ trên hệ thống trường.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Danh sách môn học */}
              {activeTab === 'courses' && (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {coursesList.length === 0 ? (
                    <p className="text-xs text-slate-500 italic text-center py-4">Chưa có môn học nào được trích xuất.</p>
                  ) : (
                    coursesList.map((course: any, idx: number) => {
                      const isPassed = course.status === 'passed' || course.dat === true;
                      return (
                        <div
                          key={idx}
                          className="p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 flex items-center justify-between text-xs"
                        >
                          <div className="min-w-0 flex-1 mr-2">
                            <p className="font-semibold text-slate-800 dark:text-slate-100 truncate">
                              {course.name || course.ten_mon}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                              Mã: {course.code || course.ma_mon || 'N/A'} · {course.credits || course.tin_chi} TC {course.semester ? `· ${course.semester}` : ''}
                              {course.retake_count > 0 && ` · Thi lại ${course.retake_count} lần`}
                            </p>
                          </div>
                          <div className="text-right shrink-0">
                            <span className="font-bold text-sm text-slate-800 dark:text-slate-100">
                              {course.grade !== null && course.grade !== undefined ? course.grade : (course.diem !== null ? course.diem : '—')}
                            </span>
                            <div>
                              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md ${
                                isPassed
                                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                                  : 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400'
                              }`}>
                                {isPassed ? 'Đạt' : 'Chưa đạt'}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* Tab 3: Danh sách chứng chỉ */}
              {activeTab === 'certificates' && (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {certificates && certificates.length > 0 ? (
                    certificates.map((cert: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 flex items-center justify-between text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-800 dark:text-slate-100">{cert.ten}</p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">Loại: {cert.loai || 'Chứng chỉ'}</p>
                        </div>
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                          cert.hoan_tat
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                            : 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                        }`}>
                          {cert.hoan_tat ? 'Đã hoàn tất' : (cert.tinh_trang || 'Chưa hoàn tất')}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 italic text-center py-4">Chưa có chứng chỉ nào.</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Modal */}
        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <span>Cổng trường:</span>
            <a
              href="https://dkmh.lhu.edu.vn"
              target="_blank"
              rel="noreferrer"
              className="text-[#1565C0] dark:text-[#4D8FE0] hover:underline flex items-center gap-0.5"
            >
              <span>dkmh.lhu.edu.vn</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold transition cursor-pointer"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
