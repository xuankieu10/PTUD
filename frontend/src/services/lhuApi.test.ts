import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { lhuApi, authApi, API_BASE_URL, setAuthToken, removeAuthToken } from './api';

describe('lhuApi - Cấu hình Base URL và Method chuẩn xác', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    removeAuthToken();
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    removeAuthToken();
  });

  it('lhuApi.getStatus gọi đúng URL cùng base với auth, method GET và gắn Bearer token', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ linked: true, student_id: 'SV_001' }),
    });
    global.fetch = mockFetch;

    const res = await lhuApi.getStatus();
    expect(res.linked).toBe(true);
    expect(res.student_id).toBe('SV_001');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/status`);
    expect(callOptions?.method || 'GET').toBe('GET');
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi.link gọi đúng URL cùng base với auth, method POST, body đúng schema và gắn Bearer token', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'Liên kết thành công' }),
    });
    global.fetch = mockFetch;

    const res = await lhuApi.link('121000123', 'Secret@Pass');
    expect(res.success).toBe(true);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/link`);
    expect(callOptions?.method).toBe('POST');
    expect(JSON.parse(callOptions?.body)).toEqual({
      student_id: '121000123',
      password: 'Secret@Pass',
    });
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi.getTranscript gọi đúng URL cùng base với auth và method GET', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ student: { student_id: '121000123' }, courses: [] }),
    });
    global.fetch = mockFetch;

    const res = await lhuApi.getTranscript();
    expect(res.student.student_id).toBe('121000123');

    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/transcript`);
    expect(callOptions?.method || 'GET').toBe('GET');
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi.getCertificates gọi đúng URL cùng base với auth và method GET', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ ten: 'TOEIC', loai: 'Ngoại ngữ', hoan_tat: true }],
    });
    global.fetch = mockFetch;

    const res = await lhuApi.getCertificates();
    expect(res).toHaveLength(1);

    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/certificates`);
    expect(callOptions?.method || 'GET').toBe('GET');
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi.getSummary gọi đúng URL cùng base với auth và method GET', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ gpa: 3.5, total_accumulated_credits: 120 }),
    });
    global.fetch = mockFetch;

    const res = await lhuApi.getSummary();
    expect(res.gpa).toBe(3.5);

    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/summary`);
    expect(callOptions?.method || 'GET').toBe('GET');
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi.unlink gọi đúng URL cùng base với auth và method DELETE', async () => {
    setAuthToken('mock_jwt_token_123');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    global.fetch = mockFetch;

    const res = await lhuApi.unlink();
    expect(res.success).toBe(true);

    const [callUrl, callOptions] = mockFetch.mock.calls[0];
    expect(callUrl).toBe(`${API_BASE_URL}/lhu/link`);
    expect(callOptions?.method).toBe('DELETE');
    expect(callOptions?.headers?.['Authorization']).toBe('Bearer mock_jwt_token_123');
  });

  it('lhuApi và authApi tuyệt đối không gọi trực tiếp tapi.lhu.edu.vn hay dkmh.lhu.edu.vn', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'fake', role: 'student' }),
    });
    global.fetch = mockFetch;

    await authApi.login('test', 'test');
    await lhuApi.getStatus();

    for (const call of mockFetch.mock.calls) {
      const url = String(call[0]);
      expect(url).not.toContain('tapi.lhu.edu.vn');
      expect(url).not.toContain('dkmh.lhu.edu.vn');
      expect(url.startsWith(API_BASE_URL)).toBe(true);
    }
  });
});
