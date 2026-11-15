"""Tk widgets only; callbacks come from the controller."""
import tkinter as tk
from tkinter import ttk, filedialog
from .timeline import display_sender, is_system


class UI:
    def __init__(self, root, callbacks):
        self.root = root
        root.title('对话显微镜')
        width=min(1220,max(800,root.winfo_screenwidth()-80))
        height=min(900,max(540,root.winfo_screenheight()-100))
        root.geometry(f'{width}x{height}')
        root.minsize(min(900,width),min(680,height))
        self.path = tk.StringVar()
        self.day = tk.StringVar()
        self.start, self.end = tk.StringVar(value='00:00:00'), tk.StringVar(value='24:00:00')
        self.include_system = tk.BooleanVar(value=False)
        self.overview_mode = tk.StringVar(value="bar")
        self.non_calendar = tk.BooleanVar(value=False)
        self.manual_range = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='选择一个会话导出文件或分块目录。成员显示导出中的名称，系统通知单独标识。')
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill='both', expand=True)
        bar = ttk.Frame(frame);bar.pack(fill='x')
        ttk.Entry(bar, textvariable=self.path).pack(side='left', fill='x', expand=True)
        ttk.Button(bar, text='选择文件', command=self.choose_file).pack(side='left', padx=4)
        ttk.Button(bar, text='选择文件夹', command=self.choose_folder).pack(side='left')
        self.load_button = ttk.Button(bar, text='读取', command=callbacks['load'])
        self.load_button.pack(side='left', padx=4)
        filters = ttk.Frame(frame, padding=(0,8));filters.pack(fill='x')
        ttk.Label(filters,text='日期').pack(side='left')
        self.date_box = ttk.Combobox(filters, textvariable=self.day, state='readonly', width=12)
        self.date_box.pack(side='left',padx=5)
        self.date_box.bind('<<ComboboxSelected>>',lambda e: callbacks['day']())
        self.range_entries=[]
        for label,var in (('开始',self.start),('结束',self.end)):
            ttk.Label(filters,text=label).pack(side='left',padx=4)
            entry=ttk.Entry(filters,textvariable=var,width=14,state='disabled')
            entry.pack(side='left')
            self.range_entries.append(entry)
        self.range_button=ttk.Button(filters,text='应用范围',command=callbacks['range'],state='disabled')
        self.range_button.pack(side='left',padx=4)
        ttk.Button(filters,text='全天',command=callbacks['reset']).pack(side='left')
        ttk.Checkbutton(filters,text='显示系统消息',variable=self.include_system,command=callbacks['system']).pack(side='left',padx=8)
        modes=ttk.Frame(frame);modes.pack(fill='x',pady=(0,5))
        ttk.Label(modes,text='全天概览：').pack(side='left')
        for title,value in (('条形图','bar'),('积分图','cumulative')):
            ttk.Radiobutton(modes,text=title,value=value,variable=self.overview_mode,style='Toolbutton',command=callbacks['mode']).pack(side='left',padx=3)
        ttk.Style(root).configure('Small.TCheckbutton',font=('Microsoft YaHei',9))
        ttk.Checkbutton(modes,text='非自然日模式',variable=self.non_calendar,style='Small.TCheckbutton',command=callbacks['boundary']).pack(side='left',padx=8)
        ttk.Checkbutton(modes,text='手动选范围',variable=self.manual_range,style='Small.TCheckbutton',command=callbacks['manual']).pack(side='left',padx=8)
        pane = ttk.Panedwindow(frame, orient='vertical');pane.pack(fill='both',expand=True)
        self.pane = pane
        self.plot_frame=ttk.Frame(pane);pane.add(self.plot_frame,weight=3)
        bottom=ttk.Frame(pane);pane.add(bottom,weight=2)
        row=ttk.Frame(bottom);row.pack(fill='x')
        self.info=ttk.Label(row,text='');self.info.pack(side='left',padx=8)
        details=ttk.Panedwindow(bottom,orient='horizontal');details.pack(fill='both',expand=True,pady=6)
        left=ttk.Frame(details);right=ttk.Frame(details)
        details.add(left,weight=1);details.add(right,weight=2)
        self.tree=ttk.Treeview(left,columns=('time','kind','sender','text'),show='headings',selectmode='browse',height=7)
        for key,title,width in (('time','时间',90),('kind','类型',65),('sender','发送者',110),('text','摘要',220)):
            self.tree.heading(key,text=title);self.tree.column(key,width=width)
        self.tree.tag_configure('system',foreground='#b45309')
        scroll=ttk.Scrollbar(left,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda e: callbacks['select']())
        self.text=tk.Text(right,height=8,wrap='word',state='disabled',font=('Microsoft YaHei',11))
        ts=ttk.Scrollbar(right,orient='vertical',command=self.text.yview)
        self.text.configure(yscrollcommand=ts.set)
        ts.pack(side='right',fill='y');self.text.pack(fill='both',expand=True)
        status_label=ttk.Label(frame,textvariable=self.status,wraplength=1150)
        status_label.pack(fill='x',pady=(5,0))
        frame.bind('<Configure>',lambda event:status_label.configure(wraplength=max(300,event.width-20)))

    def enable_range(self, enabled):
        state='normal' if enabled else 'disabled'
        for entry in self.range_entries:entry.configure(state=state)
        self.range_button.configure(state=state)

    def choose_file(self):
        value=filedialog.askopenfilename(filetypes=[('聊天导出','*.zip *.json *.jsonl'),('所有文件','*.*')])
        if value:self.path.set(value)

    def choose_folder(self):
        value=filedialog.askdirectory()
        if value:self.path.set(value)

    def show_text(self, text):
        self.text.configure(state='normal');self.text.delete('1.0','end')
        self.text.insert('1.0',text);self.text.configure(state='disabled')

    def show_messages(self, messages, indices):
        self.tree.delete(*self.tree.get_children())
        for i in indices[:300]:
            m=messages[i]
            self.tree.insert('', 'end',iid=str(i),values=(m.time[11:],'系统' if is_system(m) else '成员',display_sender(m),m.text[:65].replace('\n',' ')),tags=('system',) if is_system(m) else ())
