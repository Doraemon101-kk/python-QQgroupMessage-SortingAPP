"""Tk widgets only; callbacks come from the controller."""
import tkinter as tk
from tkinter import ttk, filedialog
from .timeline import display_sender, is_system


class UI:
    def __init__(self, root, callbacks):
        self.root = root
        root.title('对话显微镜')
        root.geometry('1220x900')
        root.minsize(900, 680)
        self.path = tk.StringVar()
        self.day = tk.StringVar()
        self.start, self.end = tk.StringVar(value='00:00:00'), tk.StringVar(value='24:00:00')
        self.include_system = tk.BooleanVar(value=True)
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
        for label,var in (('开始',self.start),('结束',self.end)):
            ttk.Label(filters,text=label).pack(side='left',padx=4)
            ttk.Entry(filters,textvariable=var,width=10).pack(side='left')
        ttk.Button(filters,text='应用范围',command=callbacks['range']).pack(side='left',padx=4)
        ttk.Button(filters,text='全天',command=callbacks['reset']).pack(side='left')
        ttk.Checkbutton(filters,text='显示系统消息',variable=self.include_system,command=callbacks['system']).pack(side='left',padx=8)
        pane = ttk.Panedwindow(frame, orient='vertical');pane.pack(fill='both',expand=True)
        self.plot_frame=ttk.Frame(pane);pane.add(self.plot_frame,weight=3)
        bottom=ttk.Frame(pane);pane.add(bottom,weight=2)
        row=ttk.Frame(bottom);row.pack(fill='x')
        ttk.Button(row,text='上一组成员',command=lambda:callbacks['members'](-1)).pack(side='left')
        ttk.Button(row,text='下一组成员',command=lambda:callbacks['members'](1)).pack(side='left',padx=4)
        self.info=ttk.Label(row,text='');self.info.pack(side='left',padx=8)
        details=ttk.Panedwindow(bottom,orient='horizontal');details.pack(fill='both',expand=True,pady=6)
        left=ttk.Frame(details);right=ttk.Frame(details)
        details.add(left,weight=1);details.add(right,weight=2)
        self.tree=ttk.Treeview(left,columns=('time','kind','sender','text'),show='headings',selectmode='browse')
        for key,title,width in (('time','时间',90),('kind','类型',65),('sender','发送者',110),('text','摘要',220)):
            self.tree.heading(key,text=title);self.tree.column(key,width=width)
        self.tree.tag_configure('system',foreground='#b45309')
        scroll=ttk.Scrollbar(left,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda e: callbacks['select']())
        self.text=tk.Text(right,wrap='word',state='disabled',font=('Microsoft YaHei',11))
        ts=ttk.Scrollbar(right,orient='vertical',command=self.text.yview)
        self.text.configure(yscrollcommand=ts.set)
        ts.pack(side='right',fill='y');self.text.pack(fill='both',expand=True)
        ttk.Label(frame,textvariable=self.status,wraplength=1150).pack(fill='x',pady=(5,0))

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
