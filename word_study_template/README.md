# 词语研究模板

独立于群聊检索器，通过指定目录活引用其 `core.py`。无真实数据、无内置个人路径，不修改本体，不上传文件。需要 Python 3.10 或更新版本；图表使用 Matplotlib。

当前状态：项目接入、配置校验、日期筛选、字面匹配算法、结果导出和命令行已实现。可视化已使用 Matplotlib 实现月度折线图与研究词词云；使用 --visualize 保存，--show 直接弹窗。

## 使用

在本模板目录打开终端：

```powershell
Copy-Item study.example.json study.local.json
```

编辑 `study.local.json`：填写 `project_path`（可信的本体项目目录）、`input_path`（一个会话的导出文件或分块目录）、`output_dir`（独立结果目录）、`terms`（研究词列表）。Windows 路径建议使用 `/`，避免 JSON 反斜杠转义。日期留空表示不限，结束日期包含当天。

配置文件里的相对路径以配置文件所在目录为基准；命令行覆盖路径以当前工作目录为基准。

验证接入，不运行研究算法：

```powershell
python -m word_study prepare --config study.local.json
```

执行分析：

```powershell
python -m word_study run --config study.local.json
```

分析并生成两张图：

```powershell
python -m word_study run --config study.local.json --visualize
```

可用 `--project-path`、`--input-path`、`--output-dir` 覆盖配置路径。只导入明确指定的可信 Python 项目，导入会执行该文件的顶层代码。此模板不会自动搜索磁盘、下载或更新本体。

## 输出

每次运行建立独立结果子目录。`prepare` 只输出运行清单；`run` 先保存清单和 summary.json，再分别生成报告及选定图表。每个任务独立清理失败产物，成功文件保留；task_status.json 记录各项结果。输出目录必须在本体与输入数据目录树之外。

默认输出不包含原文、昵称、输入文件名或绝对输入路径，但包含用户自己填写的研究词、日期和内容摘要。不要在研究词中填写不希望写进报告的个人信息。没有任何自动上传功能。

每次启动加载当前 `core.py`，记录源码和输入内容摘要；运行期间检测到变化会中止。本次运行不热更新。数据量大时计算输入摘要会增加读取时间。

## 算法与可视化

见 `IMPLEMENTATION_GUIDE.md`。analyze 已使用 str.find 实现，分别统计不重叠出现次数、每词命中记录数、并集命中记录数和月度分母，并保留原文字符偏移。render 已实现，只接收统计结果，不接触聊天原文。上下文半径目前只保留为配置，逐例导出、去重对照和人工标注文件属于后续功能，当前不会生成。

仓库根 `.gitignore` 与本目录忽略规则共同限定发布文档、空配置和逐项允许的 Python 代码；本地配置、数据、输出和测试不提交。发布前仍应检查代码和文档是否手动写入了隐私信息。

## 图表文件

运行 `run --config study.local.json --visualize` 后，打开结果目录的 `charts.html`。也可单独打开 `monthly_trend.svg`、`word_cloud.svg`。均可离线使用；先执行 `python -m pip install -r requirements.txt` 安装 Matplotlib。另保存 PNG 图片，使用 --show 可直接弹出两张图，关闭窗口后完成本次运行。

折线使用每千条记录命中率，缺失月份断线，有样本但无命中记为零。分母和实际覆盖日期见 summary.json。词云按频次的 0.85 次幂缩放字号，最小 22、最大 150；采用固定随机种子的紧凑横竖错排布局，所有正频次研究词都会保留；它不是自动分词结果。扩展 terms 即可复用，零频词不进入词云。


## 研究词别名合计

在 terms 中列出所有需要单独统计的字面词，再用 term_groups 把已有词归为一组，例如 `"term_groups": {"作品合计": ["全称", "简称"]}`。报告、summary.json 和月度折线会同时保留单词项和合计项。合计命中记录数按并集统计，同条提及多个别名只算一条；出现次数对重叠别名位置合并，不重叠的位置分别计数。词云只显示单词项，避免加入合计而重复计权。

匹配为字面匹配：全角冒号、半角冒号、空格有区别。需要额外写法时，请同时添加到 terms 和对应分组。当前仅统计写出的词，不会自动识别代称、图片或作品语义。

## 设计约定

采用“共享输入、单向依赖、分支独立”。人话说，就是把统计结果算好以后，分别交给报告和两张图；谁坏了只处理谁，其他功能接着做。完整结构图及说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

原命令保持可用；也可独立选择输出：

```powershell
python -m word_study run --config study.local.json --tasks monthly_trend
python -m word_study run --config study.local.json --tasks report,word_cloud
```

--tasks 明确指定输出时，--visualize 不再追加其他图表；--show 显示成功保存的选定图表。未指定 --tasks 时，run 默认生成报告，--visualize 或 --show 再请求两张图。

返回码 0 表示成功，2 表示配置或必要前置失败，3 表示部分可选输出失败。显示窗口失败也会记录为部分失败，已保存文件不撤销。磁盘整体故障、进程被杀等仍可能中断运行。
