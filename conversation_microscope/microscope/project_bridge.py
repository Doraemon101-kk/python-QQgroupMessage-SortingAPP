"""Only this module imports the upstream project. No copied parser."""
import hashlib
import importlib.util
from pathlib import Path
import sys
from .models import Corpus


def load_corpus(project_path, input_path):
    core = Path(project_path).expanduser().resolve() / 'core.py'
    if not core.is_file():
        raise ValueError('指定的项目目录中没有 core.py')
    source = core.read_bytes()
    digest = hashlib.sha256(source).digest()
    name = '_microscope_core_' + hashlib.sha256(str(core).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, core)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        exec(compile(source, str(core), 'exec'), module.__dict__)
        if not callable(getattr(module, 'load_messages', None)):
            raise ValueError('本体缺少 load_messages 接口')
        loaded = module.load_messages(Path(input_path).expanduser())
        if not isinstance(loaded, tuple) or len(loaded) != 2:
            raise ValueError('本体读取接口返回结构不兼容')
        messages, skipped = loaded
        if not isinstance(messages, (tuple, list)) or type(skipped) is not int or skipped < 0:
            raise ValueError('本体读取接口返回的消息或跳过数量无效')
        for message in messages:
            if not all(isinstance(getattr(message, key, None), str) for key in ('time', 'text', 'sender')):
                raise ValueError('消息需要 time、text、sender 字符串字段')
        if hashlib.sha256(core.read_bytes()).digest() != digest:
            raise ValueError('读取期间本体发生改变，请重新加载')
        return Corpus(tuple(messages), skipped)
    finally:
        sys.modules.pop(name, None)
