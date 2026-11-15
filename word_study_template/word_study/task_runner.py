"""A failure boundary around each optional output task."""
import importlib
from pathlib import Path
import shutil
import tempfile
from copy import deepcopy


def run_task(module_name, result, target):
    target = Path(target)
    stage = Path(tempfile.mkdtemp(prefix='.task-', dir=target))
    published = []
    try:
        module = importlib.import_module(module_name)
        # 每个任务拿自己的一份结果；即使误改输入，也不会污染下个任务。
        module.run(deepcopy(result), stage)
        files = list(stage.iterdir())
        if not files or any(not file.is_file() for file in files):
            raise ValueError('输出任务必须生成至少一个普通文件')
        if any((target / file.name).exists() for file in files):
            raise ValueError('输出任务试图覆盖已有结果')
        for file in files:
            destination = target / file.name
            file.rename(destination)
            published.append(destination)
        return {'status': 'ok', 'files': [p.name for p in published]}
    except Exception as exc:
        for file in published:
            file.unlink(missing_ok=True)
        return {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}
    finally:
        shutil.rmtree(stage, ignore_errors=True)
