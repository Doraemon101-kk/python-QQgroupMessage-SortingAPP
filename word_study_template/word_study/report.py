"""Optional Markdown output; no loading, analysis, or chart dependencies."""
from .storage import output_transaction, write_manifest, write_summary


def write_report(folder, result):
    lines = ['# 词语研究报告', '', f'研究范围记录数：{result.record_count}',
             f'包含任意研究词的记录数：{result.any_hit_messages}', '',
             '| 词语 | 出现次数 | 命中记录数 | 每千条命中记录 |',
             '|---|---:|---:|---:|']
    for term, values in result.per_term.items():
        rate = values['hit_messages'] / result.record_count * 1000 if result.record_count else 0
        label = term.replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')
        lines.append(f"| {label} | {values['occurrences']} | {values['hit_messages']} | {rate:.2f} |")
    lines += ['', '分母为成功读取且在研究日期范围内的记录，包括本体未区分的系统或媒体记录。',
              '别名合计：命中记录取并集；出现次数合并重叠的别名位置，独立位置分别计数。词云仅显示单词项，避免合计重复计权。',
              '词频不能直接证明语气、动机或作者身份；本报告不包含聊天原文。', '']
    (folder / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def run(result, folder):
    write_report(folder, result)


def write_results(folder, result):
    """Compatibility entry for existing callers."""
    write_summary(folder, result)
    write_report(folder, result)
