# 算法与可视化实现指南

当前 analyze 与 render 均已完成，下文说明算法和可视化约定。

## 1. 算法：analyze(corpus, config)

位置：`word_study/study.py`。输入已经完成加载和日期筛选，你不用解析 ZIP 或写文件。

- `corpus.messages`：全部消息，保留本体顺序；每个对象至少有 `time`、`text`、`message_id`。
- `corpus.eligible_indices`：真正参与统计的消息下标。遍历这些下标，再去 messages 取原对象。
- `config.terms`：去重后的研究词元组，保留填写顺序。
- 返回 `models.py` 中的 `StudyResult`。

核心步骤：

```text
初始化各词计数、月份表、命中消息集合、出现位置列表
对研究范围中的每条记录：
    取 time 前 7 个字符作为月份，月份分母加 1
    对每个研究词：
        从正文起点查找，找到一次就登记一个 Occurrence
        下一次从本次结束位置继续查找
        若本条至少出现过一次：该词命中记录数加 1
        把本条下标加入任意词命中集合
返回总分母、每词统计、按月统计、出现位置
```

建议用 `str.find(term, cursor)` 查找，返回 `-1` 时结束。找到后 `end = start + len(term)`，再令 `cursor = end`。这是同一词不重叠匹配；不同词独立查找。位置采用 Python 字符下标 `[start, end)`，不是 UTF-8 字节下标。

这里维护三个不同的量：

| 量 | 如何计数 |
|---|---|
| 出现次数 | 找到一个词就加一次，同条记录可以加多次 |
| 每词命中记录数 | 一条记录包含该词就加一次 |
| 任意词命中记录数 | 用消息下标集合取并集，每条最多一次 |

月份分母要在查词前统计，没命中的记录同样进入分母。每千条命中率用 `hit_messages / record_count * 1000`，分母为 0 时显示无样本。不要相加各词命中记录数来求并集。

返回结构约定：

```python
StudyResult(
    record_count=len(corpus.eligible_indices),
    any_hit_messages=...,
    per_term={term: {"occurrences": ..., "hit_messages": ...} for term in config.terms},
    monthly={
        # 每个有研究记录的月份都建立一项，即使全部词语均未命中
        "YYYY-MM": {
            "record_count": ...,
            "first_record_date": "YYYY-MM-DD",
            "last_record_date": "YYYY-MM-DD",
            "per_term": {term: {"occurrences": ..., "hit_messages": ...} for term in config.terms}
        }
    },
    occurrences=[...],
)
```

`first_record_date`、`last_record_date` 是实际样本覆盖，不代表导出完整。不把没样本的整月当作零使用量。`occurrence_id` 可按固定遍历顺序生成 `occ-000001`，保证同一次运行内唯一；不要用原消息 ID 单独当唯一编号。

复杂度：直接逐词扫描约为 O(正文总长度 × 词数)，两三个词足够使用。保存全部出现位置的内存与命中次数成正比，暂不必引入复杂索引。

先核对这些情况：同条一个词多次出现、两个词同条出现、只有非命中记录的月份、空日期范围、正文正好等于词、匹配在正文末尾。同一词不重叠时，虚构正文 `哈哈哈` 查 `哈哈` 应只有一次。

## 2. Matplotlib 可视化：render(result, output_dir, show=False)

monthly_chart 使用 ax.plot 绘制每词及合计的每千条记录命中率；缺失月份填 NaN 使折线断开，有分母但无命中才是零。结果返回 Figure，便于继续修改。

word_cloud 使用 ax.text，字号按频次的 0.85 次幂缩放，范围 22 至 150。测量实际包围盒，通过固定随机种子的螺旋搜索紧凑横竖错排；画布不足时扩大，不缩小字号。仅统计配置词，排除合计项，不自动分词。无命中时显示空状态。

render 将两张 Figure 保存为 PNG 与 SVG，再生成本地 HTML 查看页。show=True 调用 plt.show() 弹窗；关闭窗口后外层发布结果。运行需要 matplotlib，首次安装执行 python -m pip install -r requirements.txt。优先选取微软雅黑等中文字体；没有中文字体时需自行安装系统中文字体。

## 输出隔离更新

命令行通过 service.run_request 组织任务，两个绘图函数已分别迁至 monthly_plot.py、cloud_plot.py。旧 visualization.render 作为兼容入口，返回每项输出状态；需要检查 status 是否为 failed。基础结果先发布，之后的报告与图表失败不会撤销基础统计或其他成功任务。--show 从已保存图片显示窗口，不阻塞文件发布。
