# QQ 聊天记录工具集

本地运行的聊天记录检索器与研究拓展，共用一个仓库，各自独立启动。消息解析通过检索器核心接口复用，拓展通过桥接层调用，不修改原始档案。

## 目录与入口

| 目录 | 用途 | 说明 |
|---|---|---|
| [qq_chat_search](qq_chat_search/README.md) | 搜索消息、选择日期、查看上下文、导出 | 主程序，仅使用 Python 标准库 |
| [word_study_template](word_study_template/README.md) | 字面词频、别名合计、月度趋势和词云 | 配套拓展，绘图时使用 Matplotlib |

对话显微镜仍处于规划阶段，其本地预留目录暂不加入版本管理。

## 启动检索器

需要 Python 3.10 或更新版本及 Tkinter。在仓库根目录执行：

```cmd
cd qq_chat_search
python app.py
```

## 使用研究拓展

从仓库根目录开始：

```cmd
cd word_study_template
python -m pip install -r requirements.txt
copy study.example.json study.local.json
```

在本地配置中自行填写研究条件和输入数据位置。相对路径以配置文件目录为基准；project_path 可以填 ../qq_chat_search。示例配置保持空白，不附带语料、研究词或结果。

```cmd
python -m word_study run --config study.local.json --visualize
```

使用 --show 可弹窗查看图表。更详细的任务选择与接口约定见各目录说明。

## 发布范围

仓库根目录统一管理 Git。源码目录内部不建立嵌套仓库。根忽略规则使用逐文件白名单；新增源码需要主动加入白名单。

仅公开通用源码、依赖说明、通用文档与空配置。聊天记录、数据集、实际用例、本地配置、个人路径、论文、图表、运行结果、截图、缓存、日志、压缩包及本地测试均排除。

提交前检查 git diff --cached，核实内容及提交元数据。Git 忽略规则只约束未跟踪文件，历史隐私信息需另行处理。
