"""Optional Matplotlib view. Selection callbacks are injected by the app."""
import math
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import SpanSelector
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from tkinter import ttk
from .timeline import cumulative_fraction
from matplotlib.ticker import MaxNLocator


def _font():
    names = {font.name for font in font_manager.fontManager.ttflist}
    return next((name for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC') if name in names), 'DejaVu Sans')


def clock(value, day_start=0):
    total = max(0, min(86400, int(value)))
    if not day_start:return f'{total//3600:02d}:{total%3600//60:02d}'
    total+=day_start*3600
    return ('次日' if total>=86400 else '')+f'{total%86400//3600:02d}:{total%3600//60:02d}'


class PlotView:
    def __init__(self, parent, on_range, on_message, on_scroll=None, on_capacity=None):
        self.on_range, self.on_message = on_range, on_message
        self.on_capacity = on_capacity
        self.capacity = 4
        self.total_rows = 0
        self.offset = 0
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill='both', expand=True)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.figure = Figure(figsize=(10, 4.2), dpi=100)
        self.overview = self.figure.add_axes((.23, .77, .73, .18))
        self.lanes = self.figure.add_axes((.23, .16, .73, .44))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        self.y_scroll = ttk.Scrollbar(self.frame, orient='vertical', command=on_scroll)
        self.y_scroll.grid(row=0, column=1, sticky='ns')
        self.x_scroll = ttk.Scrollbar(self.frame, orient='horizontal', command=self.pan)
        self.x_scroll.grid(row=1, column=0, sticky='ew')
        self.selector = SpanSelector(self.overview, self.span, 'horizontal', useblit=False,
                                     props={'facecolor': '#2563eb', 'alpha': .25}, interactive=True)
        self.canvas.mpl_connect('pick_event', self.pick)
        self.canvas.mpl_connect('scroll_event', self.scroll)
        self.canvas.mpl_connect('draw_event', self.resized)
        self.points = ()
        self.artist = None
        self.window = (0, 86400)
        self.day_start = 0
        self.range_enabled = False
        self.font = _font()
        self.set_range_enabled(False)
        self.full_labels = ()
        self.overview_artists = []
        self.overview_signature = None

    def style(self, ax):
        ax.grid(axis='x', alpha=.15)
        for label in [ax.title, ax.xaxis.label, ax.yaxis.label, *ax.get_xticklabels(), *ax.get_yticklabels()]:
            label.set_fontfamily(self.font)
            label.set_fontsize(9)

    def draw_overview(self, bins, start, end, system_bins=None, include_system=True, mode='bar', day_start=0):
        if mode not in ('bar','cumulative'):
            raise ValueError('未知的概览模式')
        self.day_start=day_start
        ax = self.overview
        system_bins = system_bins or (0,) * 1440
        signature=(tuple(bins),tuple(system_bins),include_system,mode)
        if signature != self.overview_signature:
            for artist in self.overview_artists:
                artist.remove()
            self.overview_artists=[]
            members = [total-system for total,system in zip(bins,system_bins)]
            if mode=='bar':
                occupied=[i for i,count in enumerate(members) if count]
                self.overview_artists.append(ax.bar([i+.5 for i in occupied],[members[i] for i in occupied],
                                                    width=1,color='#0891b2',label='成员'))
                if include_system:
                    occupied=[i for i,count in enumerate(system_bins) if count]
                    self.overview_artists.append(ax.bar([i+.5 for i in occupied],[system_bins[i] for i in occupied],
                                                        bottom=[members[i] for i in occupied],width=1,color='#d97706',label='系统'))
                maximum=max(bins if include_system else members,default=0)
                ax.set_ylabel('条/分钟')
                ax.yaxis.set_major_locator(MaxNLocator(nbins=4,integer=True))
                ax.set_ylim(0,max(1,maximum*1.15))
            else:
                values=cumulative_fraction(members)
                self.overview_artists.extend(ax.step(range(1441),values,where='post',color='#0891b2',linewidth=1.5,label='成员累计'))
                maximum=values[-1]
                if include_system:
                    values=cumulative_fraction(system_bins)
                    self.overview_artists.extend(ax.step(range(1441),values,where='post',color='#d97706',linewidth=1.5,label='系统累计'))
                    maximum=max(maximum,values[-1])
                ax.set_ylabel('累计比例')
                ax.set_yticks([i/5 for i in range(6)])
                ax.set_ylim(0,1.2)
            ax.legend(loc='upper right',prop={'family':self.font,'size':8})
            self.overview_signature=signature
        ax.set_xlim(0,1440)
        stride=240 if self.figure.bbox.width>=650 else 480
        ax.set_xticks(range(0,1441,stride),[clock(v*60,self.day_start) for v in range(0,1441,stride)])
        self.selector.extents=(start/60,end/60)
        self.selector.set_visible(self.range_enabled)
        self.style(ax)
        self.canvas.draw_idle()

    def draw_lanes(self, view):
        self.window = (view.start, view.end)
        self.day_start = view.day_start
        self.x_scroll.set(view.start/86400, view.end/86400)
        self.full_labels = view.labels
        ax = self.lanes
        ax.clear()
        self.artist = None
        self.points = view.points
        if view.aggregated:
            cells = view.density
            ax.scatter([max(view.start,min(view.end,m * 60 + 30)) for m, _, _ in cells], [r for _, r, _ in cells],
                       s=[min(160, 10 + 12*math.sqrt(n)) for _, _, n in cells], alpha=.7, c=['#d97706' if view.row_kinds[r] else '#0891b2' for _,r,_ in cells])
            ax.set_title('密度模式 · 开启手动选范围后可缩放时间')
        elif view.points:
            self.artist = ax.scatter([p.second for p in view.points], [p.row for p in view.points],
                                     s=26, alpha=.75, c=['#d97706' if p.is_system else '#0891b2' for p in view.points], picker=6)
            ax.set_title('右侧滚条浏览成员 · 点击消息看原文')
        else:
            ax.set_title('当前范围无消息')
        labels = self.short_labels(view.labels)
        ax.set_yticks(range(len(labels)), labels)
        ax.set_ylim(max(.7, len(view.labels)-.3), -.7)
        ax.set_xlim(view.start, view.end)
        divisions = max(2,min(6,int(self.lanes.bbox.width/95)))
        ticks = [view.start + i*(view.end-view.start)/divisions for i in range(divisions+1)]
        ax.set_xticks(ticks, [clock(t,self.day_start) for t in ticks])
        ax.set_xlabel('北京时间')
        self.style(ax)
        self.canvas.draw_idle()

    def short_labels(self, labels):
        renderer = self.canvas.get_renderer()
        prop = FontProperties(family=self.font, size=9)
        budget = max(24, self.lanes.bbox.x0-20)
        result = []
        for label in labels:
            label = label.replace('\n', ' ').replace('\r', ' ')
            if renderer.get_text_width_height_descent(label, prop, False)[0] <= budget:
                result.append(label)
                continue
            lo, hi = 0, len(label)
            while lo < hi:
                mid = (lo+hi+1)//2
                if renderer.get_text_width_height_descent(label[:mid]+'…', prop, False)[0] <= budget:
                    lo = mid
                else:
                    hi = mid-1
            result.append(label[:lo]+'…')
        return result

    def set_member_scroll(self, offset, total, capacity):
        self.offset, self.total_rows = offset, total
        self.y_scroll.set(offset/max(1,total), min(1,(offset+capacity)/max(1,total)))

    def resized(self, event):
        capacity = max(1,int(self.lanes.bbox.height//30))
        if capacity != self.capacity:
            self.capacity = capacity
            if self.on_capacity:
                self.on_capacity(capacity)
        # Refit long names immediately during window resizing.
        labels = self.short_labels(self.full_labels)
        changed = any(a.get_text()!=b for a,b in zip(self.lanes.get_yticklabels(),labels))
        if changed:
            self.lanes.set_yticks(range(len(labels)),labels)
            self.style(self.lanes)
            self.canvas.draw_idle()

    def set_range_enabled(self, enabled):
        self.range_enabled=enabled
        self.selector.set_active(enabled)
        self.selector.set_visible(enabled)
        self.x_scroll.state(['!disabled'] if enabled else ['disabled'])
        self.canvas.draw_idle()

    def pan(self, *args):
        if not self.range_enabled:return
        start,end = self.window
        width = end-start
        if args[0]=='moveto':
            lower = float(args[1])*86400
        else:
            lower = start+int(args[1])*width*(.85 if args[2]=='pages' else .1)
        lower = max(0,min(86400-width,lower))
        self.on_range(lower, lower+width)

    def span(self, minimum, maximum):
        if not self.range_enabled:return
        start, end = max(0, minimum * 60), min(86400, maximum * 60)
        if end-start >= 1:
            self.on_range(start, end)

    def pick(self, event):
        if event.artist is self.artist and len(event.ind):
            self.on_message(self.points[int(event.ind[0])].original_index)

    def scroll(self, event):
        if event.x < self.lanes.bbox.x0 and self.lanes.bbox.y0 <= event.y <= self.lanes.bbox.y1:
            command = self.y_scroll.cget('command')
            if command:
                self.y_scroll.tk.call(command, 'scroll', -1 if event.button=='up' else 1, 'units')
            return
        if not self.range_enabled or event.inaxes is not self.lanes or event.xdata is None:
            return
        start,end = self.window
        width = min(86400, max(10, (end-start) * (.65 if event.button == 'up' else 1/.65)))
        fraction = (event.xdata-start)/(end-start)
        lower = max(0, min(86400-width, event.xdata-width*fraction))
        self.on_range(lower, lower+width)
