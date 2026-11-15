import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description='独立的本地对话显微镜')
    parser.add_argument('--project-path',default=str(Path(__file__).resolve().parents[2]/'qq_chat_search'),help='可信的检索器项目目录')
    parser.add_argument('--file',help='一个会话的 JSON、JSONL、ZIP 或分块目录')
    args=parser.parse_args()
    import tkinter as tk
    from .controller import Controller
    root=tk.Tk()
    app=Controller(root,args.project_path)
    if args.file:
        app.ui.path.set(args.file);root.after(100,app.load)
    root.mainloop()


if __name__=='__main__':main()
