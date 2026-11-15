"""UI-independent selection state and orchestration."""
from .timeline import TimelineIndex, context_text


class Session:
    def __init__(self):
        self.index = None
        self.day_start = 0
        self.day = ''
        self.start, self.end = 0., 86400.
        self.selected = None
        self.include_system = False
        self.overview_mode = "bar"
        self.manual_range = False
        self.row_offset = 0
        self.row_limit = 4

    def accept(self, index):
        if index.day_start != self.day_start:
            index=TimelineIndex(index.corpus,self.day_start)
        self.index = index
        self.day = index.days[-1] if index.days else ''
        self.start, self.end = 0., 86400.
        self.selected = None
        self.row_offset = 0

    def set_day_start(self, hour):
        if hour not in (0,4):raise ValueError('统计日起点仅支持0点或4点')
        candidate=TimelineIndex(self.index.corpus,hour) if self.index else None
        previous=self.day
        self.day_start=hour
        if candidate:
            self.accept(candidate)
            if previous in candidate.days:self.day=previous

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
        return self.index.view(self.day, self.start, self.end, self.include_system, row_offset=self.row_offset, row_limit=self.row_limit)

    def context(self, original_index):
        if not self.index:
            return ''
        self.selected = original_index
        return context_text(self.index.corpus, original_index)


def prepare(project_path, input_path):
    from .project_bridge import load_corpus
    return TimelineIndex(load_corpus(project_path, input_path))
