import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Composer } from './Composer';
import type { AttachedFile } from '../../types';

describe('Composer Component', () => {
  it('renders correctly with "+" button having aria-label="Tải tệp lên"', () => {
    const onInputChange = vi.fn();
    const onSend = vi.fn();

    render(
      <Composer
        input=""
        onInputChange={onInputChange}
        onSend={onSend}
      />
    );

    const plusBtn = screen.getByRole('button', { name: /Tải tệp lên/i });
    expect(plusBtn).toBeInTheDocument();
    expect(plusBtn).toHaveAttribute('aria-label', 'Tải tệp lên');
    expect(plusBtn).toHaveAttribute('title', 'Tải tệp lên');
  });

  it('renders attached file cards and handles removal', () => {
    const onInputChange = vi.fn();
    const onSend = vi.fn();
    const onRemoveFile = vi.fn();

    const mockFiles: AttachedFile[] = [
      { id: '1', name: 'bang_diem.pdf', size: 1024 * 500, type: 'application/pdf' },
      { id: '2', name: 'chung_chi.png', size: 1024 * 200, type: 'image/png' },
    ];

    render(
      <Composer
        input=""
        onInputChange={onInputChange}
        onSend={onSend}
        files={mockFiles}
        onRemoveFile={onRemoveFile}
      />
    );

    expect(screen.getByText('bang_diem.pdf')).toBeInTheDocument();
    expect(screen.getByText('chung_chi.png')).toBeInTheDocument();

    const removeBtn = screen.getByRole('button', { name: /Bỏ tệp bang_diem.pdf/i });
    fireEvent.click(removeBtn);
    expect(onRemoveFile).toHaveBeenCalledWith(0);
  });

  it('allows sending when text is empty but files are attached', () => {
    const onInputChange = vi.fn();
    const onSend = vi.fn();

    const mockFiles: AttachedFile[] = [
      { id: '1', name: 'tailieu.docx', size: 2048, type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
    ];

    render(
      <Composer
        input=""
        onInputChange={onInputChange}
        onSend={onSend}
        files={mockFiles}
      />
    );

    const sendBtn = screen.getByRole('button', { name: /Gửi tin nhắn/i });
    expect(sendBtn).not.toBeDisabled();

    fireEvent.click(sendBtn);
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it('displays Vietnamese error message and allows retry', () => {
    const onRetry = vi.fn();

    render(
      <Composer
        input=""
        onInputChange={vi.fn()}
        onSend={vi.fn()}
        error="Định dạng tệp không được hỗ trợ. Vui lòng chọn tệp PNG, JPG, PDF, DOCX hoặc TXT."
        onRetry={onRetry}
      />
    );

    expect(
      screen.getByText(/Định dạng tệp không được hỗ trợ/i)
    ).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Thử lại/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
