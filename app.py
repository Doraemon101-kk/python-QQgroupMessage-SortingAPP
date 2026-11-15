"""Local desktop viewer; run with Python, no packages or accounts required."""
import argparse
import calendar
from datetime import date, datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import load_messages, search, context_text, export_markdown, calendar_months, date_bounds, MIN_DATE, MAX_DATE, LOCAL_TZ


class DatePicker(ttk.Frame):
    """A calendar with year/month controls and clickable days, using only Tkinter."""
    def __init__(self, parent, variable):
        super().__init__(parent)
        self.variable = variable
        self.popup = None
        ttk.Entry(self, textvariable=variable, state='readonly', width=12).pack(side='left')
        ttk.Button(self, text='选择日期', command=self.open).pack(side='left', padx=4)

    def open(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            return
        self.months = calendar_months()
        self.popup = tk.Toplevel(self)
        self.popup.title('选择日期')
        self.popup.transient(self.winfo_toplevel())
        self.popup.resizable(False, False)
        frame = ttk.Frame(self.popup, padding=12)
        frame.pack()
        years = list(dict.fromkeys(m[:4] for m in self.months))
        selected = self.variable.get()
        current = datetime.now(LOCAL_TZ).strftime('%Y-%m')
        default_month = min(max(current, self.months[-1]), self.months[0])
        initial = selected[:7] if selected[:7] in self.months else default_month
        self.year = tk.StringVar(value=initial[:4])
        self.month = tk.StringVar(value=initial[5:7])
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 8))
        self.previous = ttk.Button(bar, text='◀', width=3, command=lambda: self.move(-1))
        self.previous.pack(side='left')
        year_box = ttk.Combobox(bar, textvariable=self.year, values=years, state='readonly', width=6)
        year_box.pack(side='left', padx=4)
        self.month_box = ttk.Combobox(bar, textvariable=self.month, state='readonly', width=4)
        self.month_box.pack(side='left', padx=4)
        self.next = ttk.Button(bar, text='▶', width=3, command=lambda: self.move(1))
        self.next.pack(side='left')
        year_box.bind('<<ComboboxSelected>>', self.change_year)
        self.month_box.bind('<<ComboboxSelected>>', self.draw)
        self.board = ttk.Frame(frame)
        self.board.pack()
        ttk.Label(frame, text=f'{MIN_DATE:%Y-%m-%d} 至 {MAX_DATE:%Y-%m-%d} · 北京时间').pack(pady=(8, 4))
        ttk.Button(frame, text='不限日期', command=lambda: self.pick('')).pack()
        self.draw()

    def pick(self, value):
        if value and not MIN_DATE <= date.fromisoformat(value) <= MAX_DATE:
            return
        self.variable.set(value)
        self.popup.destroy()

    def change_year(self, *_):
        available = [m[5:7] for m in self.months if m[:4] == self.year.get()]
        if self.month.get() not in available:
            self.month.set(available[0])
        self.draw()

    def move(self, direction):
        current = self.year.get() + '-' + self.month.get()
        # months are newest first; chronological next has a lower index.
        index = self.months.index(current) - direction
        if 0 <= index < len(self.months):
            target = self.months[index]
            self.year.set(target[:4])
            self.month.set(target[5:7])
            self.draw()

    def draw(self, *_):
        available = sorted(m[5:7] for m in self.months if m[:4] == self.year.get())
        self.month_box.configure(values=available)
        for widget in self.board.winfo_children():
            widget.destroy()
        for column, name in enumerate(('一', '二', '三', '四', '五', '六', '日')):
            ttk.Label(self.board, text=name, anchor='center').grid(row=0, column=column, padx=3)
        year, month = int(self.year.get()), int(self.month.get())
        self.day_buttons = {}
        for row, week in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(year, month), 1):
            for column, day in enumerate(week):
                if not day:
                    continue
                value = f'{year:04d}-{month:02d}-{day:02d}'
                label = f'[{day}]' if value == self.variable.get() else str(day)
                button = ttk.Button(self.board, text=label, width=4, command=lambda v=value: self.pick(v))
                button.grid(row=row, column=column, padx=2, pady=2)
                if not MIN_DATE <= date(year, month, day) <= MAX_DATE:
                    button.configure(state='disabled')
                self.day_buttons[day] = button
        current = f'{year:04d}-{month:02d}'
        self.previous.configure(state='disabled' if current == self.months[-1] else 'normal')
        self.next.configure(state='disabled' if current == self.months[0] else 'normal')


class App:
    PAGE_SIZE = 200

    def __init__(self, root):
        self.root = root
        root.title('群聊检索器')
        root.geometry('1120x780')
        root.minsize(850, 580)
        self._init_state()
        self._build_ui()
        root.after(100, self.poll)

    def _init_state(self):
        """Initialize message data, search state, and values bound to controls."""
        self.messages, self.hits, self.page = [], [], 0
        self.events = queue.Queue()
        self.busy = False
        self.loaded_path = ''
        self.source_label = tk.StringVar(value='当前未加载数据。支持 JSON、JSONL、ZIP 和分块导出文件夹。')
        self.active_sender = self.active_keywords = ''
        self.active_match_all = True
        self.active_start_date = self.active_end_date = ''
        self.start_date = tk.StringVar(value='')
        self.end_date = tk.StringVar(value='')
        self.match_mode = tk.StringVar(value='全部命中')
        self.path = tk.StringVar(value='')
        self.sender = tk.StringVar(value='')
        self.keywords = tk.StringVar(value='')
        self.radius = tk.IntVar(value=3)
        self.status = tk.StringVar(value='选择导出文件并点击“读取文件”。所有处理均在本机进行。')
        self.page_label = tk.StringVar()

    def _build_ui(self):
        """Compose the screen in display order; each section owns its layout."""
        box = ttk.Frame(self.root, padding=12)
        box.pack(fill='both', expand=True)
        self._build_file_controls(box)
        self._build_search_controls(box)
        self._build_date_controls(box)
        self._build_pagination(box)
        self._build_message_views(box)
        ttk.Label(box, textvariable=self.status, wraplength=1050).pack(anchor='w', pady=(8, 0))

    def _build_file_controls(self, box):
        """File/folder selection, loading, and the currently loaded source."""
        file_row = ttk.Frame(box)
        file_row.pack(fill='x')
        ttk.Label(file_row, text='导出文件').pack(side='left')
        ttk.Entry(file_row, textvariable=self.path).pack(side='left', fill='x', expand=True, padx=8)
        self.choose_button = ttk.Button(file_row, text='选择文件', command=self.choose)
        self.choose_button.pack(side='left')
        self.folder_button = ttk.Button(file_row, text='选择文件夹', command=self.choose_folder)
        self.folder_button.pack(side='left', padx=(6, 0))
        self.load_button = ttk.Button(file_row, text='读取文件', command=self.load)
        self.load_button.pack(side='left', padx=(8, 0))
        ttk.Label(box, textvariable=self.source_label, wraplength=1050).pack(anchor='w', pady=(6, 0))

    def _build_search_controls(self, box):
        """Sender, keywords, match mode, search, and export."""
        filters = ttk.Frame(box, padding=(0, 12))
        filters.pack(fill='x')
        ttk.Label(filters, text='发送者').pack(side='left')
        ttk.Entry(filters, textvariable=self.sender, width=22).pack(side='left', padx=6)
        ttk.Label(filters, text='关键词').pack(side='left')
        entry = ttk.Entry(filters, textvariable=self.keywords)
        entry.pack(side='left', fill='x', expand=True, padx=6)
        entry.bind('<Return>', lambda _: self.do_search())
        ttk.Combobox(filters, textvariable=self.match_mode, values=('全部命中', '任意命中'),
                     state='readonly', width=9).pack(side='left', padx=(0, 8))
        self.search_button = ttk.Button(filters, text='搜索', command=self.do_search)
        self.search_button.pack(side='left')
        self.export_button = ttk.Button(filters, text='导出全部命中', command=self.export)
        self.export_button.pack(side='left', padx=(8, 0))
        ttk.Label(box, text='昵称、群名片或 QQ 号均可；关键词用空格分隔，可选全部或任意命中。留空表示不限。').pack(anchor='w')

    def _build_date_controls(self, box):
        """Independent date pickers sharing the search date variables."""
        dates = ttk.Frame(box, padding=(0, 6))
        dates.pack(fill='x')
        ttk.Label(dates, text='开始日期').pack(side='left', padx=(0, 6))
        DatePicker(dates, self.start_date).pack(side='left')
        ttk.Label(dates, text='结束日期').pack(side='left', padx=(18, 6))
        DatePicker(dates, self.end_date).pack(side='left')
        ttk.Label(dates, text='留空表示不限，包含起止当天（北京时间）').pack(side='left', padx=12)

    def _build_pagination(self, box):
        """Page navigation and the amount of surrounding context."""
        pager = ttk.Frame(box, padding=(0, 8))
        pager.pack(fill='x')
        ttk.Button(pager, text='上一页', command=lambda: self.turn(-1)).pack(side='left')
        ttk.Button(pager, text='下一页', command=lambda: self.turn(1)).pack(side='left', padx=6)
        ttk.Label(pager, textvariable=self.page_label).pack(side='left', padx=6)
        ttk.Label(pager, text='前后消息数').pack(side='right')
        spin = ttk.Spinbox(pager, from_=0, to=20, textvariable=self.radius, width=4,
                           command=self.detail)
        spin.pack(side='right', padx=6)

    def _build_message_views(self, box):
        """Result list and read-only message context, with their event bindings."""
        split = ttk.Panedwindow(box, orient='vertical')
        split.pack(fill='both', expand=True)
        results = ttk.Frame(split)
        self.tree = ttk.Treeview(results, columns=('time', 'sender', 'text'), show='headings', selectmode='browse')
        for col, label, width in [('time', '时间（北京时间）', 160), ('sender', '发送者', 150), ('text', '消息摘要', 700)]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, stretch=(col == 'text'))
        scroll = ttk.Scrollbar(results, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.detail)
        split.add(results, weight=1)
        details = ttk.Frame(split)
        self.text = tk.Text(details, wrap='word', font=('Microsoft YaHei UI', 11), state='disabled')
        ds = ttk.Scrollbar(details, command=self.text.yview)
        self.text.configure(yscrollcommand=ds.set)
        ds.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)
        split.add(details, weight=1)

    def choose(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(filetypes=[('QQ 聊天记录', '*.json *.jsonl *.zip'), ('全部文件', '*.*')])
        if path:
            self.path.set(path)

    def choose_folder(self):
        if self.busy:
            return
        path = filedialog.askdirectory(title='选择单个会话的分块导出文件夹')
        if path:
            self.path.set(path)

    def set_busy(self, value):
        self.busy = value
        for button in (self.load_button, self.search_button, self.export_button,
                       self.choose_button, self.folder_button):
            button.configure(state='disabled' if value else 'normal')

    def background(self, fn, operation="操作"):
        def run():
            try:
                self.events.put(('done', fn()))
            except Exception as exc:
                self.events.put(('error', (operation, str(exc))))
        threading.Thread(target=run, daemon=True).start()

    def load(self):
        if self.busy:
            return
        path = self.path.get().strip().strip('"')
        if not path:
            self.choose()
            path = self.path.get().strip().strip('"')
            if not path:
                return
        self.set_busy(True)
        self.status.set('正在读取文件，请稍候……')
        self.background(lambda: ('load', path, load_messages(path)), operation='读取 ' + Path(path).name)

    def poll(self):
        try:
            kind, data = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.set_busy(False)
            if kind == 'error':
                operation, reason = data
                current = f'当前仍显示之前的数据：{self.loaded_path}' if self.loaded_path else '当前没有已加载的数据。'
                self.status.set(f'{operation}失败。{current}')
                messagebox.showerror('无法完成操作', f'{operation}失败：\n{reason}\n\n{current}')
            elif data[0] == 'load':
                _, self.loaded_path, result = data
                self.messages, skipped = result
                self.source_label.set(f'当前已加载：{self.loaded_path} ｜ {len(self.messages):,} 条消息 ｜ 跳过 {skipped} 条')
                self.hits = []
                self.tree.delete(*self.tree.get_children())
                self.show_text('正在搜索新文件……')
                self.status.set(f'已读取 {len(self.messages):,} 条消息，跳过 {skipped} 行。文件：{Path(self.loaded_path).name}')
                self.do_search()
            elif data[0] == 'search':
                (_, self.hits, self.active_sender, self.active_keywords, self.active_match_all,
                 self.active_start_date, self.active_end_date) = data
                self.page = 0
                self.render()
                self.status.set(f'共 {len(self.messages):,} 条消息，命中 {len(self.hits):,} 条。点击结果查看上下文。来源：{Path(self.loaded_path).name}')
            elif data[0] == 'export':
                self.status.set(f'已导出 {len(self.hits):,} 条命中及上下文：{data[1]}')
                messagebox.showinfo('导出完成', str(data[1]))
        self.root.after(100, self.poll)

    def do_search(self):
        if self.busy:
            return
        if not self.messages:
            messagebox.showinfo('尚未读取', '请先选择并读取文件。')
            return
        start, end = self.start_date.get(), self.end_date.get()
        try:
            date_bounds(start, end)
        except ValueError as exc:
            messagebox.showerror('日期范围无效', str(exc))
            return
        sender, words = self.sender.get(), self.keywords.get()
        match_all = self.match_mode.get() == '全部命中'
        self.set_busy(True)
        self.status.set('正在搜索……')
        self.background(lambda: ('search', search(self.messages, sender, words, match_all, start, end),
                                 sender, words, match_all, start, end))

    def render(self):
        self.tree.delete(*self.tree.get_children())
        begin = self.page * self.PAGE_SIZE
        for i in self.hits[begin:begin+self.PAGE_SIZE]:
            m = self.messages[i]
            self.tree.insert('', 'end', iid=str(i), values=(m.time, m.sender, m.text.replace('\n', ' / ')[:180]))
        pages = max(1, (len(self.hits)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.page_label.set(f'第 {self.page+1} / {pages} 页 · 共 {len(self.hits):,} 条')
        self.show_text('点击一条结果查看全文及前后消息。' if self.hits else '没有匹配结果。可以缩短昵称、减少关键词或留空条件。')
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])

    def turn(self, step):
        pages = max(1, (len(self.hits)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.page = max(0, min(pages-1, self.page+step))
        self.render()

    def get_radius(self):
        try:
            return max(0, min(20, int(self.radius.get())))
        except (ValueError, tk.TclError):
            return 3

    def detail(self, *_):
        selected = self.tree.selection()
        if selected:
            self.show_text(context_text(self.messages, int(selected[0]), self.get_radius()))

    def show_text(self, value):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)
        self.text.configure(state='disabled')

    def export(self):
        if self.busy or not self.hits:
            messagebox.showinfo('没有结果', '请先搜索到消息。')
            return
        path = filedialog.asksaveasfilename(initialfile='群聊检索结果.md',
                                          defaultextension='.md', filetypes=[('Markdown 文本', '*.md')])
        if not path:
            return
        radius = self.get_radius()
        self.set_busy(True)
        self.status.set('正在导出全部命中……')
        def run():
            export_markdown(path, self.messages, self.hits, self.active_sender,
                            self.active_keywords, radius, self.active_match_all,
                            self.active_start_date, self.active_end_date)
            return ('export', path)
        self.background(run)


def main():
    parser = argparse.ArgumentParser(description='本地 QQ 群聊检索器')
    parser.add_argument('--file', help='JSON、JSONL、ZIP 或分块导出文件夹路径')
    parser.add_argument('--sender', default='')
    parser.add_argument('--keywords', default='')
    parser.add_argument('--any', dest='match_any', action='store_true', help='多个关键词任意命中；默认全部命中')
    parser.add_argument('--start-date', default='', help='开始日期 YYYY-MM-DD，留空不限')
    parser.add_argument('--end-date', default='', help='结束日期 YYYY-MM-DD，含当天')
    parser.add_argument('--output', help='非交互导出 Markdown 路径')
    parser.add_argument('--context', type=int, default=3, choices=range(21))
    args = parser.parse_args()
    if args.output:
        if not args.file:
            parser.error('--output 需要 --file')
        try:
            messages, skipped = load_messages(args.file)
            hits = search(messages, args.sender, args.keywords, match_all=not args.match_any,
                          start_date=args.start_date, end_date=args.end_date)
            export_markdown(args.output, messages, hits, args.sender, args.keywords,
                            args.context, match_all=not args.match_any,
                            start_date=args.start_date, end_date=args.end_date)
        except (ValueError, OSError, RuntimeError) as exc:
            parser.exit(1, f'操作失败：{exc}\n')
        print(f'消息 {len(messages)}；跳过 {skipped}；命中 {len(hits)}；导出 {args.output}')
    else:
        root = tk.Tk()
        app = App(root)
        app.start_date.set(args.start_date)
        app.end_date.set(args.end_date)
        app.sender.set(args.sender)
        app.keywords.set(args.keywords)
        app.match_mode.set('任意命中' if args.match_any else '全部命中')
        if args.file:
            app.path.set(args.file)
            root.after(100, app.load)
        root.mainloop()


if __name__ == '__main__':
    main()
