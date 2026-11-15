import math
from .plot_support import save_figure

def month_sequence(monthly):
    if not monthly:
        return []
    numbers = sorted(int(m[:4]) * 12 + int(m[5:7]) - 1 for m in monthly)
    return [f'{n // 12:04d}-{n % 12 + 1:02d}' for n in range(numbers[0], numbers[-1] + 1)]


def monthly_chart(result):
    import matplotlib.pyplot as plt
    months = month_sequence(result.monthly)
    fig, ax = plt.subplots(figsize=(max(10, min(22, len(months) * .45)), 6), layout='constrained')
    for term in result.per_term:
        values = []
        for month in months:
            bucket = result.monthly.get(month)
            values.append(bucket['per_term'][term]['hit_messages'] / bucket['record_count'] * 1000
                          if bucket and bucket['record_count'] else float('nan'))
        ax.plot(range(len(months)), values, marker='o', markersize=4, linewidth=1.8, label=term)
    if months:
        stride = max(1, math.ceil(len(months) / 18))
        ticks = sorted(set(range(0, len(months), stride)) | {len(months) - 1})
        ax.set_xticks(ticks, [months[i] for i in ticks], rotation=45, ha='right')
    else:
        ax.text(.5, .5, '当前范围无样本', transform=ax.transAxes, ha='center')
    ax.set(title='月度词语趋势', xlabel='月份（无样本月份断线）', ylabel='每千条记录命中数')
    ax.set_ylim(bottom=0)
    ax.grid(axis='y', alpha=.25)
    if result.per_term:
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=9)
    return fig


def run(result, folder):
    save_figure(monthly_chart, result, folder, "monthly_trend")
