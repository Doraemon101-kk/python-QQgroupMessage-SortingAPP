"""Connect events to the session; background loading never touches Tk."""
import queue
import threading
from tkinter import messagebox, ttk
from .session import Session, prepare
from .ui import UI


def parse_clock(value):
    parts=value.split(':')
    if len(parts) not in (2,3) or any(not x.isdigit() or len(x)!=2 for x in parts):
        raise ValueError('时间格式应为 HH:MM 或 HH:MM:SS')
    h,m,*rest=map(int,parts);s=rest[0] if rest else 0
    if not 0<=h<=24 or not 0<=m<60 or not 0<=s<60 or (h==24 and (m or s)):
        raise ValueError('时间范围应在 00:00:00 至 24:00:00 之间')
    return h*3600+m*60+s


def format_clock(second):
    total=min(86400,max(0,int(round(second))))
    return f'{total//3600:02d}:{total%3600//60:02d}:{total%60:02d}'


def view_clock(second, day_start=0):
    if not day_start:return format_clock(second)
    total=int(round(second))+day_start*3600
    prefix='次日' if total>=86400 else ''
    return prefix+format_clock(total%86400)


def parse_view_clock(value, day_start=0):
    next_day=value.startswith('次日')
    actual=parse_clock(value.removeprefix('次日'))
    if next_day or (day_start and actual<day_start*3600):actual+=86400
    return actual-day_start*3600


class Controller:
    def __init__(self,root,project_path):
        self.root,self.project_path=root,project_path
        self.session=Session()
        self.events=queue.Queue()
        self.loading=False
        self.pending=None
        self.closed=False
        self.poll_id=None
        self.resize_id=None
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Destroy>", self.on_destroy, add="+")
        callbacks={'load':self.load,'day':self.day,'range':self.range_from_fields,
                   'reset':lambda:self.range(0,86400),'system':self.system,
                   'select':self.select,'mode':self.mode,'boundary':self.boundary,'manual':self.manual}
        self.ui=UI(root,callbacks)
        self.plot=None
        try:
            from .plot_view import PlotView
            self.plot=PlotView(self.ui.plot_frame,self.queue_range,self.pick,self.scroll_members,self.queue_capacity)
        except Exception as exc:
            for child in self.ui.plot_frame.winfo_children():child.destroy()
            ttk.Label(self.ui.plot_frame,text=f'图表不可用：{type(exc).__name__}。仍可用时间输入框、消息列表和原文面板。').pack(pady=20)
        self.poll_id=root.after(100,self.poll)

    def on_destroy(self,event):
        if event.widget is self.root:self.cleanup()

    def cleanup(self):
        if self.closed:return
        self.closed=True
        self.cancel_pending()
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
            self.resize_id=None
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id=None

    def close(self):
        self.cleanup()
        self.root.destroy()

    def cancel_pending(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending=None

    def load(self):
        if self.loading:return
        path=self.ui.path.get().strip()
        if not path:self.ui.choose_file();path=self.ui.path.get().strip()
        if not path:return
        self.cancel_pending()
        self.loading=True
        self.ui.load_button.configure(state='disabled')
        self.ui.status.set('正在读取并建立时间索引……')
        def worker():
            try:self.events.put(('loaded',prepare(self.project_path,path)))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        if self.closed:return
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id=None
        try:kind,data=self.events.get_nowait()
        except queue.Empty:pass
        else:
            self.loading=False;self.ui.load_button.configure(state='normal')
            if kind=='error':
                self.ui.status.set('读取失败；已有数据仍可查看。')
                messagebox.showerror('读取失败',data,parent=self.root)
            else:
                self.cancel_pending()
                self.session.accept(data)
                self.ui.date_box.configure(values=data.days)
                self.ui.day.set(self.session.day)
                self.ui.show_text('')
                self.refresh()
        self.poll_id=self.root.after(100,self.poll)

    def day(self):
        self.cancel_pending()
        try:self.session.choose_day(self.ui.day.get());self.refresh()
        except ValueError as exc:messagebox.showerror('日期无效',str(exc),parent=self.root)

    def range_from_fields(self):
        if not self.session.manual_range:return
        try:self.range(parse_view_clock(self.ui.start.get(),self.session.day_start),parse_view_clock(self.ui.end.get(),self.session.day_start))
        except ValueError as exc:messagebox.showerror('时间无效',str(exc),parent=self.root)

    def queue_range(self,start,end):
        if not self.session.manual_range:return
        if self.pending is not None:self.root.after_cancel(self.pending)
        self.pending=self.root.after(60,lambda:self.range(start,end))

    def range(self,start,end):
        self.cancel_pending()
        try:self.session.choose_range(start,end)
        except ValueError as exc:
            messagebox.showerror('时间无效',str(exc),parent=self.root);return
        self.refresh()

    def system(self):
        self.session.include_system=self.ui.include_system.get()
        self.session.row_offset=0
        self.session.selected=None
        self.refresh()

    def refresh_overview(self):
        s=self.session
        if not self.plot or not s.index:return
        self.plot.draw_overview(s.index.overview(s.day),s.start,s.end,
                                s.index.overview(s.day,True),s.include_system,s.overview_mode,s.day_start)

    def manual(self):
        self.cancel_pending()
        enabled=self.ui.manual_range.get()
        self.session.manual_range=enabled
        self.ui.enable_range(enabled)
        if self.plot:self.plot.set_range_enabled(enabled)
        if not enabled:self.range(0,86400)

    def boundary(self):
        self.cancel_pending()
        self.session.set_day_start(4 if self.ui.non_calendar.get() else 0)
        if self.session.index:
            self.ui.date_box.configure(values=self.session.index.days)
            self.ui.day.set(self.session.day)
            self.refresh()

    def mode(self):
        mode=self.ui.overview_mode.get()
        if mode not in ('bar','cumulative'):return
        self.session.overview_mode=mode
        try:self.refresh_overview()
        except Exception as exc:
            self.ui.status.set('概览切换失败：'+type(exc).__name__)

    def queue_capacity(self, capacity):
        if self.closed:return
        if self.resize_id is not None:self.root.after_cancel(self.resize_id)
        self.resize_id=self.root.after(80,lambda:self.apply_capacity(capacity))

    def apply_capacity(self,capacity):
        self.resize_id=None
        self.session.row_limit=capacity
        if self.session.index:self.refresh()

    def scroll_members(self,*args):
        s=self.session
        if not s.index or not s.day:return
        total=s.index.sender_count(s.day,s.start,s.end,s.include_system)
        if args[0]=='moveto':
            offset=round(float(args[1])*total)
        else:
            offset=s.row_offset+int(args[1])*(s.row_limit if args[2]=='pages' else 1)
        s.row_offset=max(0,min(max(0,total-s.row_limit),offset))
        self.refresh_members()

    def refresh_members(self):
        s=self.session
        count=s.index.sender_count(s.day,s.start,s.end,s.include_system)
        s.row_offset=max(0,min(s.row_offset,max(0,count-s.row_limit)))
        records=len(s.index.indices(s.day,s.start,s.end,s.include_system))
        self.ui.info.configure(text=f'{records} 条 · 名称行 {s.row_offset+1 if count else 0}—{min(count,s.row_offset+s.row_limit)}/{count} · 列表前300条')
        if self.plot:
            self.plot.set_member_scroll(s.row_offset,count,s.row_limit)
            self.plot.draw_lanes(s.view())

    def refresh(self):
        s=self.session
        if not s.index:return
        self.ui.start.set(view_clock(s.start,s.day_start));self.ui.end.set(view_clock(s.end,s.day_start))
        indices=s.index.indices(s.day,s.start,s.end,s.include_system)
        self.ui.show_messages(s.index.corpus.messages,indices)
        if s.selected is not None:
            self.ui.show_text(s.context(s.selected))
        else:
            self.ui.show_text('点击消息点或列表查看原文；前后文可能跨越当前日期范围。')
        count=s.index.sender_count(s.day,s.start,s.end,s.include_system)
        self.ui.info.configure(text=f'{len(indices)} 条 · 名称行 {s.row_offset+1 if count else 0}—{min(count,s.row_offset+s.row_limit)}/{count} · 列表前300条')
        errors=[]
        if self.plot:
            # Independent view branches share state, not each other's outputs.
            for name,fn in [('概览',self.refresh_overview),
                            ('成员时间线',self.refresh_members)]:
                try:fn()
                except Exception as exc:errors.append(name+'：'+type(exc).__name__)
        self.ui.status.set(f'已读取 {len(s.index.corpus.messages)} 条，跳过 {s.index.corpus.skipped} 条。'+('；'.join(errors) if errors else '拖选上方概览，滚轮缩放下方时间线。橙色为系统通知，青色为成员消息。'))

    def pick(self,index):
        self.ui.show_text(self.session.context(index))
        if self.ui.tree.exists(str(index)):
            self.ui.tree.selection_set(str(index));self.ui.tree.see(str(index))

    def select(self):
        selection=self.ui.tree.selection()
        if selection:self.ui.show_text(self.session.context(int(selection[0])))
