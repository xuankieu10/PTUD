import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className = '',
}) => {
  if (!content) return null;

  // Split content into blocks: code blocks, tables, lists, blockquotes, headings, paragraphs
  const blocks = parseBlocks(content);

  return (
    <div className={`space-y-3 leading-relaxed text-[15px] sm:text-base ${className}`}>
      {blocks.map((block, index) => {
        switch (block.type) {
          case 'code':
            return (
              <CodeBlock
                key={index}
                language={block.language || 'text'}
                code={block.content}
              />
            );
          case 'heading':
            if (block.level === 1) {
              return (
                <h1
                  key={index}
                  className="text-xl sm:text-2xl font-bold text-[#1565C0] dark:text-[#4D8FE0] mt-4 mb-2 tracking-tight"
                >
                  {renderInline(block.content)}
                </h1>
              );
            }
            if (block.level === 2) {
              return (
                <h2
                  key={index}
                  className="text-lg sm:text-xl font-bold text-[#3F51B5] dark:text-[#7986CB] mt-3 mb-1.5 tracking-tight"
                >
                  {renderInline(block.content)}
                </h2>
              );
            }
            return (
              <h3
                key={index}
                className="text-base sm:text-lg font-bold text-slate-800 dark:text-slate-100 mt-2.5 mb-1"
              >
                {renderInline(block.content)}
              </h3>
            );
          case 'table':
            return (
              <div key={index} className="overflow-x-auto my-3 rounded-xl border border-slate-200 dark:border-slate-700">
                <table className="w-full text-left text-sm border-collapse">
                  <thead className="bg-[#E3F0FC]/60 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200 font-semibold border-b border-slate-200 dark:border-slate-700">
                    <tr>
                      {block.headers.map((h, i) => (
                        <th key={i} className="px-3.5 py-2.5">
                          {renderInline(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 bg-white dark:bg-[#162338]">
                    {block.rows.map((row, rIdx) => (
                      <tr
                        key={rIdx}
                        className="hover:bg-slate-50/75 dark:hover:bg-slate-800/40 transition-colors"
                      >
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-3.5 py-2 text-slate-700 dark:text-slate-300">
                            {renderInline(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case 'list':
            return block.ordered ? (
              <ol key={index} className="list-decimal pl-5 space-y-1 my-2 text-slate-800 dark:text-slate-200">
                {block.items.map((item, i) => (
                  <li key={i} className="pl-1">
                    {renderInline(item)}
                  </li>
                ))}
              </ol>
            ) : (
              <ul key={index} className="list-disc pl-5 space-y-1 my-2 text-slate-800 dark:text-slate-200 marker:text-[#1565C0] dark:marker:text-[#4D8FE0]">
                {block.items.map((item, i) => (
                  <li key={i} className="pl-1">
                    {renderInline(item)}
                  </li>
                ))}
              </ul>
            );
          case 'blockquote':
            return (
              <blockquote
                key={index}
                className="pl-4 py-1.5 border-l-4 border-[#1565C0] dark:border-[#4D8FE0] bg-[#E3F0FC]/30 dark:bg-slate-800/30 rounded-r-lg my-2.5 text-slate-700 dark:text-slate-300 italic"
              >
                {renderInline(block.content)}
              </blockquote>
            );
          default:
            return (
              <p key={index} className="my-1.5 text-slate-800 dark:text-slate-200 leading-relaxed">
                {renderInline(block.content)}
              </p>
            );
        }
      })}
    </div>
  );
};

// Component Code Block với nút "Sao chép"
const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/60 bg-[#141C2B] text-slate-100 shadow-sm">
      {/* Code block header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#0F1622] border-b border-slate-700/50 text-xs text-slate-400">
        <span className="font-mono uppercase tracking-wider font-semibold text-[11px]">
          {language}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-all text-xs font-medium cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Đã chép</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Sao chép</span>
            </>
          )}
        </button>
      </div>

      {/* Code content */}
      <pre className="p-4 overflow-x-auto text-xs sm:text-[13px] font-mono leading-relaxed text-slate-200">
        <code>{code}</code>
      </pre>
    </div>
  );
};

// Inline Markdown Parser: bold, italic, inline code, links
function renderInline(text: string): React.ReactNode {
  if (!text) return null;

  // Split tokens for `code`, **bold**, *italic*, [label](url)
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(regex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Inline Code
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code
          key={index}
          className="px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[#1565C0] dark:text-[#7986CB] font-mono text-[13px] border border-slate-200/60 dark:border-slate-700"
        >
          {part.slice(1, -1)}
        </code>
      );
    }

    // Bold
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return (
        <strong key={index} className="font-semibold text-slate-900 dark:text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Italic
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return (
        <em key={index} className="italic text-slate-800 dark:text-slate-300">
          {part.slice(1, -1)}
        </em>
      );
    }

    // Link
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={index}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#1565C0] dark:text-[#4D8FE0] hover:underline font-medium"
        >
          {linkMatch[1]}
        </a>
      );
    }

    // Regular text (support line breaks)
    return <span key={index}>{part}</span>;
  });
}

// Block Parser
type Block =
  | { type: 'code'; language: string; content: string }
  | { type: 'heading'; level: number; content: string }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'blockquote'; content: string }
  | { type: 'paragraph'; content: string };

function parseBlocks(raw: string): Block[] {
  const lines = raw.split('\n');
  const blocks: Block[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // 1. Code block ```
    if (line.trim().startsWith('```')) {
      const language = line.trim().replace(/^```/, '').trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push({
        type: 'code',
        language: language || 'text',
        content: codeLines.join('\n'),
      });
      i++;
      continue;
    }

    // 2. Headings #, ##, ###
    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        content: headingMatch[2].trim(),
      });
      i++;
      continue;
    }

    // 3. Blockquote >
    if (line.trim().startsWith('>')) {
      const quoteLines: string[] = [line.trim().replace(/^>\s?/, '')];
      i++;
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      blocks.push({
        type: 'blockquote',
        content: quoteLines.join(' '),
      });
      continue;
    }

    // 4. Tables | a | b |
    if (line.includes('|') && i + 1 < lines.length && lines[i + 1].includes('---')) {
      const headers = line
        .split('|')
        .map((s) => s.trim())
        .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);

      i += 2; // skip header and delimiter line
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|')) {
        const row = lines[i]
          .split('|')
          .map((s) => s.trim())
          .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        if (row.length > 0) rows.push(row);
        i++;
      }
      blocks.push({
        type: 'table',
        headers,
        rows,
      });
      continue;
    }

    // 5. Unordered list (- or *)
    if (/^[\*\-]\s+/.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^[\*\-]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[\*\-]\s+/, ''));
        i++;
      }
      blocks.push({
        type: 'list',
        ordered: false,
        items,
      });
      continue;
    }

    // 6. Ordered list (1. 2.)
    if (/^\d+\.\s+/.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ''));
        i++;
      }
      blocks.push({
        type: 'list',
        ordered: true,
        items,
      });
      continue;
    }

    // 7. Regular paragraph / empty line
    if (!line.trim()) {
      i++;
      continue;
    }

    // Accumulate consecutive text lines into paragraph
    const paraLines: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith('```') &&
      !lines[i].match(/^#{1,3}\s+/) &&
      !lines[i].trim().startsWith('>') &&
      !lines[i].includes('|') &&
      !/^[\*\-]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i]);
      i++;
    }

    blocks.push({
      type: 'paragraph',
      content: paraLines.join('\n'),
    });
  }

  return blocks;
}
