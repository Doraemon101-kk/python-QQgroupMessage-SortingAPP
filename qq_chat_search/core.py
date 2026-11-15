"""Read QQ Chat Exporter JSONL files and search messages. Standard library only."""
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import zipfile

LOCAL_TZ = timezone(timedelta(hours=8))
MIN_DATE = date(2020, 9, 1)
MAX_DATE = date(2027, 5, 24)


@dataclass(frozen=True)
class Message:
    time: str
    sender: str
    aliases: str
    text: str
    message_id: str
    is_system: bool = False


def normalize(raw):
    sender = raw.get('sender') or {}
    content = raw.get('content') or {}
    if not isinstance(sender, dict) or not isinstance(content, dict):
        raise ValueError('消息结构不受支持')
    text = content.get('text') or ''
    if not isinstance(text, str):
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
                   name, '\n'.join(names).casefold(), text, str(raw.get('id') or ''),
                   raw.get('system') is True or str(raw.get('type', '')).casefold() == 'system')


def load_messages(path):
    """Read one QCE conversation from JSON, JSONL, a chunk folder, or ZIP."""
    path = Path(path).expanduser()
    messages, skipped = [], 0
    record_errors = (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError)

    def add_message(raw):
        nonlocal skipped
        try:
            if not isinstance(raw, dict):
                raise ValueError('不是消息对象')
            messages.append(normalize(raw))
        except record_errors:
            skipped += 1

    def read_jsonl(stream):
        nonlocal skipped
        for line in stream:
            if not line.strip():
                continue
            try:
                raw = json.loads(line.decode('utf-8-sig'))
            except (UnicodeError, json.JSONDecodeError):
                skipped += 1
                continue
            add_message(raw)

    def read_json(stream, label):
        try:
            data = json.load(stream)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'{label}：JSON 内容无效或尚未导出完整，请重新导出后再试。') from exc
        records = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(records, list):
            raise ValueError(f'{label}：已识别 JSON，但没有找到 messages 消息数组。'
                             '请提供原始导出文件以确认格式，不要只修改扩展名。')
        for raw in records:
            add_message(raw)

    def select_members(names):
        # Never treat manifest or macOS metadata as message data.
        names = [n for n in names if '__MACOSX' not in Path(n).parts
                 and not Path(n).name.startswith('._')]
        chunks = sorted(n for n in names if n.lower().endswith('.jsonl'))
        if chunks:
            parents = {str(Path(n).parent) for n in chunks}
            if len(parents) != 1:
                raise ValueError('发现多个消息目录。请每次选择一个会话导出，避免混合不同聊天的上下文。')
            return chunks, read_jsonl
        docs = [n for n in names if n.lower().endswith('.json')
                and Path(n).name.lower() != 'manifest.json']
        if len(docs) == 1:
            return docs, None
        if len(docs) > 1:
            raise ValueError('发现多个 JSON 文件，无法确定聊天来源。请解压后直接选择一个消息 JSON。')
        raise ValueError('未找到消息数据：没有 JSONL 分块或消息 JSON。'
                         '支持 QCE 普通 JSON、JSONL 及其 ZIP；manifest.json 本身不含消息。')

    if not path.exists():
        raise ValueError('文件或目录不存在，请重新选择；若位于网盘，请先下载到本机。')
    if path.is_dir():
        chunks = path / 'chunks'
        folder = chunks if chunks.is_dir() else path
        names, reader = select_members([str(p) for p in folder.iterdir() if p.is_file()])
        for name in names:
            with Path(name).open('rb') as stream:
                if reader:
                    reader(stream)
                else:
                    read_json(stream, Path(name).name)
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names, reader = select_members([n for n in archive.namelist() if not n.endswith('/')])
            try:
                for name in names:
                    with archive.open(name) as stream:
                        if reader:
                            reader(stream)
                        else:
                            read_json(stream, Path(name).name)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                raise ValueError('无法读取压缩包内容，可能损坏、加密或使用了不支持的压缩方式。') from exc
    elif path.suffix.lower() == '.jsonl':
        with path.open('rb') as stream:
            read_jsonl(stream)
    elif path.suffix.lower() == '.json':
        with path.open('rb') as stream:
            read_json(stream, path.name)
    elif path.suffix.lower() == '.zip':
        raise ValueError('文件不是有效的 ZIP，可能已损坏或下载未完成。仅改名为 ZIP 不会转换格式。')
    else:
        raise ValueError('请选择 QCE 导出的 JSON、JSONL、ZIP 文件，或分块导出文件夹。'
                         'HTML、TXT、Excel 和 BAK 暂不支持。')
    if not messages:
        raise ValueError(f'没有读到有效消息（跳过 {skipped} 条）。'
                         '请确认选择的是消息导出，而非配置或清单文件；空会话也可能没有消息。')
    messages.sort(key=lambda m: m.time)
    return messages, skipped


def calendar_months():
    """All selectable calendar months, newest first; boundary days checked by picker."""
    first = MIN_DATE.year * 12 + MIN_DATE.month - 1
    last = MAX_DATE.year * 12 + MAX_DATE.month - 1
    return [f'{number//12:04d}-{number%12+1:02d}'
            for number in range(last, first-1, -1)]


def date_bounds(start_date='', end_date=''):
    """Inclusive user dates become [start midnight, next midnight), Beijing time."""
    def parse(value):
        if not value:
            return None
        try:
            result = datetime.strptime(value, '%Y-%m-%d')
            if result.strftime('%Y-%m-%d') != value:
                raise ValueError()
            return result
        except ValueError as exc:
            raise ValueError('日期格式应为 YYYY-MM-DD，例如 2026-09-01。') from exc
    start, end = parse(start_date), parse(end_date)
    if start and end and start > end:
        raise ValueError('开始日期不能晚于结束日期，请重新选择。')
    lower = start.strftime('%Y-%m-%d %H:%M:%S') if start else None
    upper = (end + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S') if end else None
    return lower, upper


def search(messages, sender='', keywords='', match_all=True, start_date='', end_date=''):
    """Match sender fields and either all or any literal keyword. Empty means unrestricted."""
    lower, upper = date_bounds(start_date, end_date)
    sender = sender.strip().casefold()
    words = keywords.casefold().split()
    hits = []
    for i, message in enumerate(messages):
        if lower and message.time < lower:
            continue
        if upper and message.time >= upper:
            continue
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


def export_markdown(path, messages, hits, sender='', keywords='', radius=3, match_all=True,
                    start_date='', end_date=''):
    # Quote all untrusted message lines so they remain distinguishable from our headings.
    date_bounds(start_date, end_date)
    with Path(path).open('w', encoding='utf-8') as out:
        out.write('# 群聊检索结果\n\n')
        out.write(f'日期范围（北京时间）：{start_date or "不限"} 至 {end_date or "不限"}\n\n')
        out.write('日期仅限制命中消息；前后文可能跨越筛选日期。\n\n')
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

