import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys

from .models import Corpus


def content_digest(path):
    """Hash contents without recording private absolute paths."""
    path = Path(path)
    digest = hashlib.sha256()
    files = sorted(path.rglob('*')) if path.is_dir() else [path]
    for item in files:
        if not item.is_file():
            continue
        if path.is_dir():
            name = item.relative_to(path).as_posix().encode('utf-8')
            digest.update(len(name).to_bytes(8, 'big'))
            digest.update(name)
        digest.update(item.stat().st_size.to_bytes(8, 'big'))
        with item.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()


class ProjectBridge:
    def __init__(self, project_path):
        self.core_path = Path(project_path).resolve() / 'core.py'
        if not self.core_path.is_file():
            raise ValueError('指定项目中没有 core.py')
        self.core_sha256 = content_digest(self.core_path)
        token = hashlib.sha256(str(self.core_path).encode()).hexdigest()[:16]
        name = f'_word_study_core_{token}'
        spec = importlib.util.spec_from_file_location(name, self.core_path)
        if spec is None or spec.loader is None:
            raise ValueError('无法加载指定项目的 core.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dataclass resolves its owning module here.
        try:
            # Compile current source directly to avoid stale bytecode on rapid edits.
            exec(compile(self.core_path.read_bytes(), str(self.core_path), 'exec'), module.__dict__)
            for function in ('load_messages', 'search'):
                if not callable(getattr(module, function, None)):
                    raise ValueError(f'本体缺少接口：{function}')
            parameters = inspect.signature(module.search).parameters
            if not {'start_date', 'end_date'} <= parameters.keys():
                raise ValueError('本体 search 接口缺少日期参数')
            self.module = module
            self.check_unchanged()
        except Exception:
            sys.modules.pop(name, None)
            raise

    def check_unchanged(self):
        if content_digest(self.core_path) != self.core_sha256:
            raise ValueError('运行期间 core.py 已变化，请重新运行')

    def load(self, input_path, config):
        input_path = Path(input_path)
        if not input_path.exists():
            raise ValueError('输入文件或文件夹不存在')
        before = content_digest(input_path)
        loaded = self.module.load_messages(input_path)
        if not isinstance(loaded, tuple) or len(loaded) != 2:
            raise ValueError('本体 load_messages 返回结构不兼容')
        messages, skipped = loaded
        if not isinstance(messages, (list, tuple)) or type(skipped) is not int or skipped < 0:
            raise ValueError('本体返回的消息列表或跳过数量不兼容')
        for message in messages:
            if not all(isinstance(getattr(message, key, None), str)
                       for key in ('time', 'text', 'message_id')):
                raise ValueError('本体消息结构缺少 time/text/message_id 字符串字段')
        indices = tuple(self.module.search(messages, start_date=config.start_date,
                                           end_date=config.end_date))
        if any(type(i) is not int or not 0 <= i < len(messages) for i in indices):
            raise ValueError('本体 search 返回了无效索引')
        if len(set(indices)) != len(indices):
            raise ValueError('本体 search 返回了重复索引')
        if content_digest(input_path) != before:
            raise ValueError('读取期间输入数据已变化，请重新运行')
        self.check_unchanged()
        return Corpus(tuple(messages), indices, skipped, self.core_sha256, before)
