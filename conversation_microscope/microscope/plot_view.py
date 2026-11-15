"""Optional Matplotlib view. Selection callbacks are injected by the app."""
import math
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import SpanSelector
from matplotlib import font_manager


def _font():
    names = {font.name for font in font_manager.fontManager.ttflist}
    return next((name for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC') if name in names), 'DejaVu Sans')


def clock(value):
    total = max(0, min(86400, int(value)))
    return f'{total//3600:02d}:{total%3600//60:02d}'


class PlotView:
    def __init__(self, parent, on_range, on_message):
        self.on_range, self.on_message = on_range, on_message
        self.figure = Figure(figsize=(10, 4.2), dpi=100, layout='constrained')
        self.overview, self.lanes = self.figure.subplots(2, 1, gridspec_kw={'height_ratios': [1, 2.5]})
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.selector = SpanSelector(self.overview, self.span, 'horizontal', useblit=False,
                                     props={'facecolor': '#2563eb', 'alpha': .25}, interactive=True)
        self.canvas.mpl_connect('pick_event', self.pick)
        self.canvas.mpl_connect('scroll_event', self.scroll)
        self.points = ()
        self.artist = None
        self.window = (0, 86400)
        self.font = _font()

    def style(self, ax):
        ax.grid(axis='x', alpha=.15)
        for label in [ax.title, ax.xaxis.label, ax.yaxis.label, *ax.get_xticklabels(), *ax.get_yticklabels()]:
            label.set_fontfamily(self.font)

    def draw_overview(self, bins, start, end, system_bins=None, include_system=True):
        ax = self.overview
        # Keep axes and selector alive; remove artists rather than clearing axes.
        for artist in list(ax.lines):
            artist.remove()
        system_bins = system_bins or (0,) * 1440
        members = [total-system for total,system in zip(bins,system_bins)]
        ax.plot(range(1440),members,color='#0891b2',linewidth=1,label='成员')
        if include_system:ax.plot(range(1440),system_bins,color='#d97706',linewidth=1,label='系统')
        ax.legend(loc='upper right',prop={'family':self.font,'size':8})
        ax.set_xlim(0, 1440)
        ax.set_ylim(0, max(1, max((*members,*(system_bins if include_system else ())), default=0) * 1.15))
        ax.set_xticks(range(0,1441,240), [clock(v*60) for v in range(0,1441,240)])
        ax.set_ylabel('条/分钟')
        self.selector.extents = (start/60, end/60)
        self.style(ax)
        self.canvas.draw_idle()

    def draw_lanes(self, view):
        self.window = (view.start, view.end)
        ax = self.lanes
        ax.clear()
        self.artist = None
        self.points = view.points
        if view.aggregated:
            cells = view.density
            ax.scatter([max(view.start,min(view.end,m * 60 + 30)) for m, _, _ in cells], [r for _, r, _ in cells],
                       s=[min(160, 10 + 12*math.sqrt(n)) for _, _, n in cells], alpha=.7, c=['#d97706' if view.row_kinds[r] else '#0891b2' for _,r,_ in cells])
            ax.set_title('密度模式：滚轮放大后选择单条消息')
        elif view.points:
            self.artist = ax.scatter([p.second for p in view.points], [p.row for p in view.points],
                                     s=26, alpha=.75, c=['#d97706' if p.is_system else '#0891b2' for p in view.points], picker=6)
            ax.set_title('滚轮缩放 · 点击消息点查看原文')
        else:
            ax.set_title('当前范围无消息')
        ax.set_yticks(range(len(view.labels)), view.labels)
        ax.set_ylim(max(.7, len(view.labels)-.3), -.7)
        ax.set_xlim(view.start, view.end)
        ticks = [view.start + i*(view.end-view.start)/6 for i in range(7)]
        ax.set_xticks(ticks, [clock(t) for t in ticks])
        ax.set_xlabel('北京时间')
        self.style(ax)
        self.canvas.draw_idle()

    def span(self, minimum, maximum):
        start, end = max(0, minimum * 60), min(86400, maximum * 60)
        if end-start >= 1:
            self.on_range(start, end)

    def pick(self, event):
        if event.artist is self.artist and len(event.ind):
            self.on_message(self.points[int(event.ind[0])].original_index)

    def scroll(self, event):
        if event.inaxes is not self.lanes or event.xdata is None:
            return
        start,end = self.window
        width = min(86400, max(10, (end-start) * (.65 if event.button == 'up' else 1/.65)))
        fraction = (event.xdata-start)/(end-start)
        lower = max(0, min(86400-width, event.xdata-width*fraction))
        self.on_range(lower, lower+width)
