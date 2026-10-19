"""Read explicitly selected text, with one output budget across all files.

Examples:
    python -B _scripts/context_excerpt.py docs/handoff.md --heading '最小接续入口'
    python -B _scripts/context_excerpt.py README.md --start 1 --end 12
"""
import argparse
from pathlib import Path
import sys


def select(text, heading=None, start=None, end=None):
    lines = text.splitlines()
    if heading is not None:
        matches = [i for i, line in enumerate(lines)
                   if line.startswith('#') and line.lstrip('#').strip() == heading]
        if len(matches) != 1:
            raise ValueError('章节标题必须准确匹配且唯一')
        first = matches[0]
        level = len(lines[first]) - len(lines[first].lstrip('#'))
        last = len(lines)
        for i in range(first + 1, len(lines)):
            if lines[i].startswith('#'):
                depth = len(lines[i]) - len(lines[i].lstrip('#'))
                if depth <= level:
                    last = i
                    break
        return '\n'.join(lines[first:last])
    if start is None or end is None or not 1 <= start <= end <= len(lines):
        raise ValueError('必须指定有效的 --start 与 --end 行范围，或 --heading')
    return '\n'.join(lines[start - 1:end])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='+')
    p.add_argument('--heading')
    p.add_argument('--start', type=int)
    p.add_argument('--end', type=int)
    p.add_argument('--max-chars', type=int, default=5000)
    args = p.parse_args(argv)
    try:
        if not 300 <= args.max_chars <= 10000:
            raise ValueError('输出预算须为 300–10000 字符，默认5000')
        if args.heading is not None and (args.start is not None or args.end is not None):
            raise ValueError('章节与行范围不能混用')
        parts = []
        for filename in args.files:
            path = Path(filename)
            if path.suffix.lower() not in ('.md', '.py', '.txt', '.log', '.ps1'):
                raise ValueError('只接受普通文本；工作流 JSON 使用 diff_wf.py')
            parts.append(f'{path}\n' + select(path.read_text(encoding='utf-8'),
                                              args.heading, args.start, args.end))
        output = '\n\n'.join(parts) + '\n'
        if len(output) > args.max_chars:
            raise ValueError(f'选取内容合计 {len(output)} 字符，超过预算 {args.max_chars}；请缩小范围。正文未输出')
        print(output, end='')
        return 0
    except (ValueError, OSError, UnicodeError) as e:
        print(f'读取停止：{str(e)[:400]}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
