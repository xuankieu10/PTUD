import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LandingPage } from './components/Landing/LandingPage';
import { SignUpPage } from './components/Auth/SignUpPage';

describe('LandingPage Component', () => {
  it('renders landing hero, features, and core branding', () => {
    const handleToggleDark = vi.fn();
    const handleNavigateSignUp = vi.fn();
    const handleOpenLogin = vi.fn();
    const handleNavigateChat = vi.fn();

    render(
      <LandingPage
        isDarkMode={false}
        onToggleDarkMode={handleToggleDark}
        onNavigateToSignUp={handleNavigateSignUp}
        onOpenLoginModal={handleOpenLogin}
        onNavigateToChat={handleNavigateChat}
      />
    );

    // Hero title check
    expect(screen.getByText(/Tư Vấn Học Vụ Thông Minh/i)).toBeInTheDocument();
    expect(screen.getByText(/Tốt Nghiệp Đúng Hạn Cùng AI/i)).toBeInTheDocument();

    // Check features
    expect(screen.getByText(/Tư Vấn Chuẩn Đầu Ra Tốt Nghiệp/i)).toBeInTheDocument();
    expect(screen.getByText(/Quét & Nhận Diện Bảng Điểm/i)).toBeInTheDocument();
    expect(screen.getByText(/Phân Loại Môn Chưa Đạt Chuẩn Xác/i)).toBeInTheDocument();
  });

  it('triggers navigation when clicking CTA buttons', () => {
    const handleNavigateSignUp = vi.fn();
    const handleNavigateChat = vi.fn();

    render(
      <LandingPage
        isDarkMode={false}
        onToggleDarkMode={vi.fn()}
        onNavigateToSignUp={handleNavigateSignUp}
        onOpenLoginModal={vi.fn()}
        onNavigateToChat={handleNavigateChat}
      />
    );

    // Click "Bắt đầu trò chuyện với AI"
    const startChatBtn = screen.getByRole('button', { name: /Bắt đầu trò chuyện với AI/i });
    fireEvent.click(startChatBtn);
    expect(handleNavigateChat).toHaveBeenCalled();
  });
});

describe('SignUpPage Component (4 trường chuẩn & validation)', () => {
  it('renders exactly 4 required fields and no extra fields', () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    // 4 trường chính
    expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mã số sinh viên/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Mật khẩu/i)).toBeInTheDocument();

    // Nút Đăng Ký
    expect(screen.getByRole('button', { name: /^Đăng Ký$/i })).toBeInTheDocument();

    // Các phần đã XÓA không được xuất hiện
    expect(screen.queryByLabelText(/Khoa/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Năm học/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Xác nhận mật khẩu/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tiếp tục với Google/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('displays Vietnamese validation error messages when submitting empty form', async () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    const submitBtn = screen.getByRole('button', { name: /^Đăng Ký$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Vui lòng nhập họ và tên')).toBeInTheDocument();
      expect(screen.getByText('MSSV phải gồm đúng 9 chữ số')).toBeInTheDocument();
      expect(screen.getByText('Email không hợp lệ')).toBeInTheDocument();
      expect(screen.getByText('Vui lòng nhập mật khẩu')).toBeInTheDocument();
    });
  });

  it('validates MSSV: strips non-numeric characters and enforces exactly 9 digits', async () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    const mssvInput = screen.getByPlaceholderText(/Nhập đúng 9 chữ số/i) as HTMLInputElement;

    // Gõ chữ cái và ký tự đặc biệt -> tự động lọc bỏ chỉ giữ số
    fireEvent.change(mssvInput, { target: { value: 'abc123xyz' } });
    expect(mssvInput.value).toBe('123');

    // Thử nhập 8 chữ số -> phải báo lỗi "MSSV phải gồm đúng 9 chữ số"
    fireEvent.change(mssvInput, { target: { value: '12345678' } });
    expect(mssvInput.value).toBe('12345678');

    const submitBtn = screen.getByRole('button', { name: /^Đăng Ký$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('MSSV phải gồm đúng 9 chữ số')).toBeInTheDocument();
    });
  });

  it('validates email format', async () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    const emailInput = screen.getByPlaceholderText('nguyenvana@lhu.edu.vn');
    fireEvent.change(emailInput, { target: { value: 'not-an-email' } });

    const submitBtn = screen.getByRole('button', { name: /^Đăng Ký$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Email không hợp lệ')).toBeInTheDocument();
    });
  });

  it('accepts password of 1 character and succeeds with full valid info', async () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    // Điền đầy đủ 4 trường hợp lệ, trong đó mật khẩu chỉ có 1 ký tự
    fireEvent.change(screen.getByPlaceholderText('Nguyễn Văn A'), { target: { value: 'Trần Thị B' } });
    fireEvent.change(screen.getByPlaceholderText(/Nhập đúng 9 chữ số/i), { target: { value: '121000123' } });
    fireEvent.change(screen.getByPlaceholderText('nguyenvana@lhu.edu.vn'), { target: { value: 'tranthib@lhu.edu.vn' } });
    fireEvent.change(screen.getByPlaceholderText('••••••••'), { target: { value: 'x' } });

    const submitBtn = screen.getByRole('button', { name: /^Đăng Ký$/i });
    fireEvent.click(submitBtn);

    // Không có lỗi validate nào xuất hiện
    await waitFor(() => {
      expect(screen.queryByText('Vui lòng nhập họ và tên')).not.toBeInTheDocument();
      expect(screen.queryByText('MSSV phải gồm đúng 9 chữ số')).not.toBeInTheDocument();
      expect(screen.queryByText('Email không hợp lệ')).not.toBeInTheDocument();
      expect(screen.queryByText('Vui lòng nhập mật khẩu')).not.toBeInTheDocument();
    });

    // Sau khi submit thành công (mock delay) -> hiển thị banner thành công
    await waitFor(() => {
      expect(screen.getByText('Đăng ký tài khoản thành công!')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('allows toggling password visibility', () => {
    render(<SignUpPage onBackToHome={vi.fn()} onOpenLogin={vi.fn()} />);

    const passwordInput = screen.getByPlaceholderText('••••••••') as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    const toggleBtn = screen.getByRole('button', { name: /Hiện mật khẩu/i });
    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe('text');

    const hideBtn = screen.getByRole('button', { name: /Ẩn mật khẩu/i });
    fireEvent.click(hideBtn);
    expect(passwordInput.type).toBe('password');
  });
});
