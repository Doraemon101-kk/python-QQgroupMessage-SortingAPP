"""CLI handles arguments and messages; service owns the business flow."""
import argparse
import sys
from .service import run_request


def main(argv=None):
    parser = argparse.ArgumentParser(description='活引用群聊检索器的独立词语研究模板')
    parser.add_argument('command', choices=('prepare', 'run'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--project-path', dest='project_path')
    parser.add_argument('--input-path', dest='input_path')
    parser.add_argument('--output-dir', dest='output_dir')
    parser.add_argument('--visualize', action='store_true')
    parser.add_argument('--show', action='store_true', help='显示已成功保存的图表')
    parser.add_argument('--tasks', help='独立选择输出：report,monthly_trend,word_cloud；用逗号分隔')
    args = parser.parse_args(argv)
    if args.tasks:
        names = args.tasks.split(',')
        if any(name not in ('report', 'monthly_trend', 'word_cloud') for name in names):
            parser.error('--tasks 只接受 report,monthly_trend,word_cloud')
        if args.command == 'prepare':
            parser.error('prepare 不生成输出任务')
    try:
        target, corpus, statuses = run_request(args)
        print(f'完成：读取 {len(corpus.messages)} 条，范围内 {len(corpus.eligible_indices)} 条，跳过 {corpus.skipped_records} 条。')
        print(f'输出：{target}')
        failed = [name for name, state in statuses.items() if state['status'] == 'failed']
        for name in failed:
            print(f'任务失败：{name}：{statuses[name]["error"]}', file=sys.stderr)
        return 3 if failed else 0
    except (ValueError, OSError, TypeError, ImportError, NotImplementedError) as exc:
        print(f'无法完成：{exc}', file=sys.stderr)
        return 2
