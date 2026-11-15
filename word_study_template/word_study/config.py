from datetime import date
import json
from pathlib import Path
from .models import StudyConfig, validate_groups


def read_config(args):
    config_file = Path(args.config).resolve()
    raw = json.loads(config_file.read_text(encoding='utf-8-sig'))
    if not isinstance(raw, dict):
        raise ValueError('配置必须是 JSON 对象')
    allowed = {'project_path', 'input_path', 'output_dir', 'terms', 'start_date',
               'end_date', 'context_radius', 'case_sensitive', 'term_groups'}
    unknown = raw.keys() - allowed
    if unknown:
        raise ValueError('存在不支持的配置项：' + ', '.join(sorted(unknown)))
    paths = {}
    for key in ('project_path', 'input_path', 'output_dir'):
        override = getattr(args, key)
        value = override if override is not None else raw.get(key, '')
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'请填写 {key}')
        path = Path(value).expanduser()
        paths[key] = path.resolve() if override is not None else (config_file.parent / path).resolve()
    terms = raw.get('terms', [])
    if not isinstance(terms, list) or any(not isinstance(t, str) or not t.strip() for t in terms):
        raise ValueError('terms 必须是非空字符串列表')
    terms = tuple(dict.fromkeys(terms))
    if not terms:
        raise ValueError('至少填写一个研究词')
    start, end = raw.get('start_date', ''), raw.get('end_date', '')
    for value in (start, end):
        if not isinstance(value, str):
            raise ValueError('日期必须是 YYYY-MM-DD 字符串或空字符串')
        if value and date.fromisoformat(value).isoformat() != value:
            raise ValueError('日期必须是 YYYY-MM-DD')
    if start and end and start > end:
        raise ValueError('开始日期不能晚于结束日期')
    radius = raw.get('context_radius', 3)
    if type(radius) is not int or not 0 <= radius <= 100:
        raise ValueError('context_radius 必须是 0 到 100 的整数')
    if raw.get('case_sensitive', True) is not True:
        raise ValueError('首版只支持 case_sensitive: true，以保证原文位置正确')
    # Keep generated output entirely outside the upstream project and input tree.
    output, project, source = paths['output_dir'], paths['project_path'], paths['input_path']
    if output == project or project in output.parents:
        raise ValueError('输出目录必须位于本体项目之外')
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('输出目录与输入数据必须位于不同目录树，不能互相包含')
    groups = validate_groups(raw.get('term_groups', {}), terms)
    return paths, StudyConfig(terms, start, end, radius, term_groups=groups)
