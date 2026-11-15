"""UI-independent selection state and orchestration."""
from .timeline import TimelineIndex, context_text


class Session:
    def __init__(self):
        self.index = None
        self.day = ''
        self.start, self.end = 0., 86400.
        self.selected = None
        self.include_system = True
        self.row_offset = 0

    def accept(self, index):
        self.index = index
        self.day = index.days[-1] if index.days else ''
        self.start, self.end = 0., 86400.
        self.selected = None
        self.row_offset = 0

    def choose_day(self, day):
        if not self.index or day not in self.index.days:
            raise ValueError('请选择档案中实际存在的日期')
        self.day = day
        self.start, self.end = 0., 86400.
        self.selected = None
        self.row_offset = 0

    def choose_range(self, start, end):
        if not self.index:
            return
        self.index.indices(self.day, start, end)  # Validate before changing state.
        self.start, self.end = start, end
        self.selected = None
        self.row_offset = 0

    def view(self):
        return self.index.view(self.day, self.start, self.end, self.include_system, row_offset=self.row_offset)

    def context(self, original_index):
        if not self.index:
            return ''
        self.selected = original_index
        return context_text(self.index.corpus, original_index)


def prepare(project_path, input_path):
    from .project_bridge import load_corpus
    return TimelineIndex(load_corpus(project_path, input_path))
