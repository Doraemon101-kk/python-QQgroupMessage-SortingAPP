"""Short required trunk, independent optional branches."""
from .config import read_config
from .models import StudyResult
from .project_bridge import ProjectBridge
from .storage import output_transaction, write_manifest, write_summary, write_json, write_gallery
from .task_runner import run_task


# 人话版：先把数据读好、算好、存好；报告和两张图各自开工。
# 某一项坏了，只记下这一项的错误，其他项接着做，已成功的文件照常保留。
# 读取和分析是必要前置；缺少它们的结果时，只停止依赖它们的下游。
OUTPUT_TASKS = {
    'report': 'word_study.report',
    'monthly_trend': 'word_study.monthly_plot',
    'word_cloud': 'word_study.cloud_plot',
}


def generate_outputs(result, target, tasks):
    statuses = {}
    for name in tasks:
        statuses[name] = run_task(OUTPUT_TASKS[name], result, target)
    if any(name in tasks for name in ('monthly_trend', 'word_cloud')):
        try:
            write_gallery(target, statuses)
            statuses['gallery'] = {'status': 'ok', 'files': ['charts.html']}
        except Exception as exc:
            statuses['gallery'] = {'status': 'failed', 'error': str(exc)}
    write_json(target / 'task_status.json', statuses)
    return statuses


def run_request(args):
    if args.command == 'prepare' and (args.visualize or args.show):
        raise ValueError('prepare 不执行可视化，请使用 run --visualize')
    paths, config = read_config(args)
    bridge = ProjectBridge(paths['project_path'])
    corpus = bridge.load(paths['input_path'], config)
    result = None
    if args.command == 'run':
        from .study import analyze
        result = analyze(corpus, config)
        if not isinstance(result, StudyResult) or result.record_count != len(corpus.eligible_indices):
            raise ValueError('算法返回的结果结构或统计分母与研究范围不一致')
    # 基础结果先独立落盘，后面的可选功能失败不会撤销它。
    with output_transaction(paths['output_dir']) as (stage, target):
        write_manifest(stage, corpus, config, args.command)
        if result is not None:
            write_summary(stage, result)
        bridge.check_unchanged()
    statuses = {}
    if result is not None:
        tasks = args.tasks.split(',') if getattr(args, 'tasks', None) else ['report']
        if args.visualize or args.show:
            tasks += ['monthly_trend', 'word_cloud'] if not getattr(args, 'tasks', None) else []
        statuses = generate_outputs(result, target, list(dict.fromkeys(tasks)))
    if args.show:
        try:
            from .display import show_saved
            show_saved(target, statuses)
        except Exception as exc:
            statuses['display'] = {'status': 'failed', 'error': str(exc)}
            write_json(target / 'task_status.json', statuses)
    return target, corpus, statuses
