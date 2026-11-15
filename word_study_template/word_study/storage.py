from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from . import __version__


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


@contextmanager
def output_transaction(output_root):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=root))
    target = root / (datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%SZ-') + uuid4().hex[:12])
    try:
        yield temporary, target
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def write_manifest(folder, corpus, config, mode):
    write_json(folder / 'run_manifest.json', {
        'template_version': __version__, 'mode': mode,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'config': asdict(config), 'core_sha256': corpus.core_sha256,
        'input_sha256': corpus.input_sha256,
        'loaded_records': len(corpus.messages),
        'selected_records': len(corpus.eligible_indices),
        'skipped_records': corpus.skipped_records,
        'rules': {'matching': 'literal, case-sensitive, non-overlapping per term',
                  'groups': 'union of hit messages; merge overlapping alias spans for mentions',
                  'denominator': 'successfully parsed records in selected date range',
                  'timezone': 'upstream core normalization',
                  'context': 'adjacent records; may cross selected date range'},
    })



def write_summary(folder, result):
    payload = {key: value for key, value in asdict(result).items() if key != 'occurrences'}
    write_json(folder / 'summary.json', payload)


def write_gallery(folder, statuses):
    names = [('monthly_trend', '月度折线图'), ('word_cloud', '研究词词云')]
    images = ''.join(f'<h2>{label}</h2><img src="{name}.png" alt="{label}">'
                     for name, label in names if statuses.get(name, {}).get('status') == 'ok')
    (folder / 'charts.html').write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>词语研究图表</title><style>body{font-family:sans-serif;background:#f1f5f9}'
        'img{max-width:100%}</style><h1>词语研究图表</h1>' +
        (images or '<p>本次没有成功生成的图表，请查看 task_status.json。</p>') + '</html>', encoding='utf-8')
