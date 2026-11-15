"""Pure indexing and viewport calculation. No GUI or plotting imports."""
from bisect import bisect_left
from collections import Counter, OrderedDict
from datetime import datetime
import math
from .models import Point, TimelineView


def is_system(message):
    return getattr(message, 'is_system', False) is True


def row_key(message):
    return (True, '') if is_system(message) else (False, message.sender)


def display_sender(message):
    return '[系统通知]' if is_system(message) else (message.sender or '未知成员')


class TimelineIndex:
    def __init__(self, corpus):
        self.corpus = corpus
        days = {}
        names = {}
        for index, message in enumerate(corpus.messages):
            stamp = datetime.strptime(message.time, '%Y-%m-%d %H:%M:%S')
            day = stamp.strftime('%Y-%m-%d')
            second = stamp.hour * 3600 + stamp.minute * 60 + stamp.second
            days.setdefault(day, []).append((second, index))
            names.setdefault(row_key(message), len(names))
        self.days = tuple(sorted(days))
        self.entries = {day: tuple(sorted(entries)) for day, entries in days.items()}
        self.seconds = {day: tuple(second for second, _ in entries) for day, entries in self.entries.items()}
        self.name_order = names
        self.cache = OrderedDict()

    def indices(self, day, start=0, end=86400, include_system=True):
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= 86400:
            raise ValueError('观察范围应满足 00:00 ≤ 开始 < 结束 ≤ 24:00')
        seconds = self.seconds.get(day, ())
        left, right = bisect_left(seconds, start), bisect_left(seconds, end)
        return tuple(index for _, index in self.entries.get(day, ())[left:right]
                     if include_system or not is_system(self.corpus.messages[index]))

    def overview(self, day, system_only=False):
        key = (day, system_only)
        if key not in self.cache:
            bins = [0] * 1440
            for second, index in self.entries.get(day, ()):
                if not system_only or is_system(self.corpus.messages[index]):
                    bins[int(second // 60)] += 1
            self.cache[key] = tuple(bins)
            if len(self.cache) > 16:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]

    def view(self, day, start, end, include_system=True, max_points=2500, row_offset=0, row_limit=20):
        selected = self.indices(day, start, end, include_system)
        messages = self.corpus.messages
        names = sorted({row_key(messages[i]) for i in selected}, key=lambda key: (not key[0], self.name_order[key]))
        visible_names = names[row_offset:row_offset + row_limit]
        rows = {name: row for row, name in enumerate(visible_names)}
        labels = tuple('[系统通知]' if system else (name or '未知成员') for system, name in visible_names)
        points = []
        for original in selected:
            message = messages[original]
            if row_key(message) not in rows:
                continue
            stamp = message.time[11:]
            h, m, s = map(int, stamp.split(':'))
            points.append(Point(original, h * 3600 + m * 60 + s, rows[row_key(message)], is_system(message)))
        dense = len(points) > max_points
        density = tuple((minute, row, count) for (minute, row), count in
                        sorted(Counter((int(p.second // 60), p.row) for p in points).items())) if dense else ()
        return TimelineView(day, start, end, len(selected), labels, () if dense else tuple(points), dense, density, tuple(key[0] for key in visible_names))

    def sender_count(self, day, start, end, include_system=True):
        return len({row_key(self.corpus.messages[i]) for i in self.indices(day, start, end, include_system)})


def context_text(corpus, original_index, radius=3):
    if not 0 <= original_index < len(corpus.messages):
        raise ValueError('消息索引越界')
    lines = []
    for i in range(max(0, original_index-radius), min(len(corpus.messages), original_index+radius+1)):
        message = corpus.messages[i]
        sender = display_sender(message)
        lines.extend([f'{"▶ 选中" if i == original_index else "上下文"} | {message.time} | {sender}', message.text, ''])
    return '\n'.join(lines)
