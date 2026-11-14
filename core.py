"""Read QQ Chat Exporter JSONL files and search messages. Standard library only."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import zipfile

LOCAL_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class Message:
    time: str
    sender: str
    aliases: str
    text: str
    message_id: str


def normalize(raw):
    sender = raw.get('sender') or {}
    content = raw.get('content') or {}
    text = content.get('text') or ''
    
    if not isinstance(sender, dict) or not isinstance(content, dict) or not isinstance(text, str):
        raise ValueError('消息结构不受支持')
    names = [str(sender.get(k) or '') for k in ('name', 'nickname', 'groupCard', 'uin')]
    name = next((n for n in names[:3] if n), '未知发送者')
    stamp = raw.get('time')


    if stamp:
        dt = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
    else:
        dt = datetime.fromtimestamp(float(raw['timestamp']) / 1000, timezone.utc)
    return Message(dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                   name, '\n'.join(names).casefold(), text, str(raw.get('id') or ''))


def load_messages(path):
    """Stream archive members without extracting; retain only searchable fields."""
    path = Path(path)
    messages, skipped = [], 0

    def read(stream):
        nonlocal skipped
        for line in stream:
            if not line.strip():
                continue
            try:
                raw = json.loads(line.decode('utf-8-sig'))
                if not isinstance(raw, dict):
                    raise ValueError('不是消息对象')
                messages.append(normalize(raw))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
                skipped += 1

    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            members = sorted(n for n in archive.namelist() if n.lower().endswith('.jsonl'))
            if not members:
                raise ValueError('ZIP 中没有 JSONL 分块，请导出 chunked JSONL 格式。')
            for member in members:
                with archive.open(member) as stream:
                    read(stream)
    elif path.suffix.lower() == '.jsonl':
        with path.open('rb') as stream:
            read(stream)
    else:
        raise ValueError('请选择 QQ Chat Exporter 导出的 ZIP 或 JSONL 文件。')
    if not messages:
        raise ValueError(f'没有读到有效消息（跳过 {skipped} 行），请检查导出格式。')
    # Sorting is stable: preserve export order for messages with equal timestamps.
    messages.sort(key=lambda m: m.time)
    return messages, skipped


def search(messages, sender='', keywords='', match_all=True):
    """Match sender fields and either all or any literal keyword. Empty means unrestricted."""
    sender = sender.strip().casefold()
    words = keywords.casefold().split()
    hits = []
    for i, message in enumerate(messages):
        if sender and sender not in message.aliases:
            continue
        text = message.text.casefold()
        if not words:
            keywords_ok = True
        elif match_all:
            keywords_ok = all(word in text for word in words)
        else:
            keywords_ok = any(word in text for word in words)
        if keywords_ok:
            hits.append(i)
    return hits


def context_text(messages, index, radius=3):
    lines = []
    for i in range(max(0, index-radius), min(len(messages), index+radius+1)):
        m = messages[i]
        marker = '>>> 命中' if i == index else '    上下文'
        lines.append(f'{marker} | {m.time} | {m.sender}\n{m.text}\n')
    return '\n'.join(lines)


def export_markdown(path, messages, hits, sender='', keywords='', radius=3, match_all=True):
    # Quote all untrusted message lines so they remain distinguishable from our headings.
    with Path(path).open('w', encoding='utf-8') as out:
        out.write('# 群聊检索结果\n\n')
        mode = '全部命中' if match_all else '任意命中'
        out.write(f'关键词模式：{mode}\n\n')
        for label, value in [('发送者条件', sender or '不限'), ('关键词条件', keywords or '不限')]:
            out.write(f'{label}：{value.replace(chr(10), " ")}\n\n')
        out.write(f'命中 {len(hits)} 条。时间为北京时间。每条附前后 {radius} 条消息。\n\n')
        out.write('以下引用均为聊天记录，包含转发、玩梗和未经核实的自述；不代表事实结论。\n\n')
        for n, index in enumerate(hits, 1):
            m = messages[index]
            out.write(f'## 结果 {n} · {m.time}\n\n')
            out.write('\n'.join('> '+line for line in context_text(messages, index, radius).splitlines()))
            out.write('\n\n')

