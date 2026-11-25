import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LhuLoginPage } from './LhuLoginPage';
import * as apiModule from '../../services/api';

describe('LhuLoginPage - Màn hình đăng nhập Cổng trường LHU', () => {
  const mockOnLoginSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Hiển thị đầy đủ form đăng nhập MSSV, mật khẩu và dòng cam kết bảo mật', () => {
    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    expect(screen.getByRole('heading', { name: /Đăng nhập tài khoản Sinh viên/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Mã số sinh viên/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mật khẩu cổng trường/i)).toBeInTheDocument();
    expect(screen.getByText(/Cam kết bảo mật:/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Mật khẩu chỉ dùng một lần để xác thực, tuyệt đối không lưu trữ\. Token chỉ lưu trong RAM 30 phút\./i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Đăng nhập$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đăng nhập quản trị/i })).toBeInTheDocument();
  });

  it('Xóa mật khẩu khỏi state ngay sau khi gửi và đăng nhập thành công', async () => {
    const loginLhuSpy = vi.spyOn(apiModule.authApi, 'loginLhu').mockResolvedValue({
      access_token: 'mock_jwt_token',
      token_type: 'bearer',
      role: 'student',
      user_id: 101,
    });
    const getMeSpy = vi.spyOn(apiModule.authApi, 'getMe').mockResolvedValue({
      id: 101,
      user_id: 101,
      username: '121000123',
      role: 'student',
      student_code: '121000123',
      full_name: 'Nguyễn Văn Sinh Viên',
      major: 'Công nghệ thông tin',
      student_id: 101,
    });

    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    const sidInput = screen.getByLabelText(/Mã số sinh viên/i) as HTMLInputElement;
    const pwdInput = screen.getByLabelText(/Mật khẩu cổng trường/i) as HTMLInputElement;
    const submitBtn = screen.getByRole('button', { name: /^Đăng nhập$/i });

    fireEvent.change(sidInput, { target: { value: '121000123' } });
    fireEvent.change(pwdInput, { target: { value: 'MySecretPassword123' } });
    expect(pwdInput.value).toBe('MySecretPassword123');

    fireEvent.click(submitBtn);

    // Mật khẩu phải được xóa khỏi state ngay sau khi gửi
    expect(pwdInput.value).toBe('');

    await waitFor(() => {
      expect(loginLhuSpy).toHaveBeenCalledWith('121000123', 'MySecretPassword123');
      expect(getMeSpy).toHaveBeenCalledTimes(1);
      expect(mockOnLoginSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ username: '121000123', role: 'student' })
      );
    });
  });

  it('Xử lý hiển thị thông báo lỗi 401 khi sai MSSV hoặc mật khẩu', async () => {
    vi.spyOn(apiModule.authApi, 'loginLhu').mockRejectedValue(
      new Error('Mã số sinh viên hoặc mật khẩu cổng trường không chính xác.')
    );

    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    const sidInput = screen.getByLabelText(/Mã số sinh viên/i);
    const pwdInput = screen.getByLabelText(/Mật khẩu cổng trường/i) as HTMLInputElement;

    fireEvent.change(sidInput, { target: { value: '121000123' } });
    fireEvent.change(pwdInput, { target: { value: 'WrongPass' } });
    fireEvent.click(screen.getByRole('button', { name: /^Đăng nhập$/i }));

    expect(pwdInput.value).toBe('');

    await waitFor(() => {
      expect(
        screen.getByText(/Mã số sinh viên hoặc mật khẩu cổng trường không chính xác\./i)
      ).toBeInTheDocument();
    });
  });

  it('Xử lý hiển thị thông báo lỗi 429 khi bị khóa do nhập sai quá 5 lần', async () => {
    vi.spyOn(apiModule.authApi, 'loginLhu').mockRejectedValue(
      new Error('Tài khoản tạm thời bị khóa do nhập sai mật khẩu quá 5 lần. Vui lòng thử lại sau 10 phút.')
    );

    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    fireEvent.change(screen.getByLabelText(/Mã số sinh viên/i), { target: { value: '121000123' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu cổng trường/i), { target: { value: 'WrongPass' } });
    fireEvent.click(screen.getByRole('button', { name: /^Đăng nhập$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Tài khoản tạm thời bị khóa do nhập sai mật khẩu quá 5 lần/i)
      ).toBeInTheDocument();
    });
  });

  it('Xử lý hiển thị thông báo lỗi 502 khi Cổng trường LHU không kết nối được', async () => {
    vi.spyOn(apiModule.authApi, 'loginLhu').mockRejectedValue(
      new Error('Cổng trường LHU không phản hồi hoặc không thể kết nối.')
    );

    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    fireEvent.change(screen.getByLabelText(/Mã số sinh viên/i), { target: { value: '121000123' } });
    fireEvent.change(screen.getByLabelText(/Mật khẩu cổng trường/i), { target: { value: 'Pass123' } });
    fireEvent.click(screen.getByRole('button', { name: /^Đăng nhập$/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Cổng trường LHU không phản hồi hoặc không thể kết nối/i)
      ).toBeInTheDocument();
    });
  });

  it('Chuyển đổi linh hoạt giữa luồng Sinh viên LHU và Đăng nhập Quản trị', async () => {
    const loginAdminSpy = vi.spyOn(apiModule.authApi, 'login').mockResolvedValue({
      access_token: 'admin_token',
      token_type: 'bearer',
      role: 'admin',
      user_id: 1,
    });
    vi.spyOn(apiModule.authApi, 'getMe').mockResolvedValue({
      id: 1,
      user_id: 1,
      username: 'admin',
      role: 'admin',
      student_code: 'ADMIN',
      full_name: 'Quản trị viên',
      major: 'Phòng Đào tạo',
      student_id: null,
    });

    render(<LhuLoginPage onLoginSuccess={mockOnLoginSuccess} />);

    // Bấm link "Đăng nhập quản trị"
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập quản trị/i }));

    expect(screen.getByRole('heading', { name: /Đăng nhập Quản trị viên/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Tên tài khoản quản trị/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mật khẩu quản trị/i)).toBeInTheDocument();

    // Submit form admin
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập Quản trị/i }));

    await waitFor(() => {
      expect(loginAdminSpy).toHaveBeenCalledWith('test01', 'Test@123');
      expect(mockOnLoginSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ username: 'admin', role: 'admin' })
      );
    });

    // Có nút quay lại đăng nhập sinh viên
    expect(screen.getByRole('button', { name: /Quay lại Đăng nhập Sinh viên LHU/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Quay lại Đăng nhập Sinh viên LHU/i }));

    expect(screen.getByRole('heading', { name: /Đăng nhập tài khoản Sinh viên/i })).toBeInTheDocument();
  });
});
