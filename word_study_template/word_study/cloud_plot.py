import math
from .plot_support import save_figure

def word_cloud(result):
    """Seeded spiral packing with a visible minimum font and strong contrast."""
    import random
    import matplotlib.pyplot as plt
    items = sorted(((term, values['occurrences']) for term, values in result.per_term.items()
                    if values['occurrences'] > 0 and term not in result.term_groups),
                   key=lambda item: (-item[1], item[0]))
    fig = plt.figure(figsize=(11, 6), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    if not items:
        ax.text(.5, .5, '没有命中的研究词', transform=ax.transAxes, ha='center', fontsize=22)
        return fig
    rng = random.Random(42)
    palette = ('#123b66', '#d45113', '#007f78', '#8d306b', '#4c579c', '#947019')
    minimum, maximum = 22, 150
    texts = []
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for i, (term, count) in enumerate(items):
        size = max(minimum, maximum * (count / items[0][1]) ** .85)
        text = ax.text(0, 0, term, fontsize=size, fontweight='bold',
                       color=palette[i % len(palette)], ha='center', va='center',
                       rotation=90 if i and rng.random() < .32 else 0, parse_math=False)
        texts.append(text)
    # Grow the canvas instead of shrinking words below the legible minimum.
    bounds = [text.get_window_extent(renderer) for text in texts]
    width = max(1100, math.ceil(max(box.width for box in bounds) + 100))
    area = sum((box.width + 12) * (box.height + 12) for box in bounds)
    height = max(550, math.ceil(area / width * 2.0), math.ceil(max(b.height for b in bounds) + 100))
    for attempt in range(12):
        fig.set_size_inches(width / 100, height / 100)
        ax.set_xlim(0, width)
        ax.set_ylim(0, height)
        placed = []
        complete = True
        for i, text in enumerate(texts):
            phase = rng.random() * math.tau
            box = text.get_window_extent(renderer)
            half_width, half_height = box.width / 2 + 5, box.height / 2 + 5
            for step in range(6000):
                angle = step * 2.3999632297 + phase
                radius = .72 * math.sqrt(step / 6000)
                x = width / 2 + radius * math.cos(angle) * width
                y = height / 2 + radius * math.sin(angle) * height
                candidate = (x-half_width, y-half_height, x+half_width, y+half_height)
                x0, y0, x1, y1 = candidate
                if (x0 < 22 or y0 < 22 or x1 > width-22 or y1 > height-22
                        or any(x0 < b[2] and x1 > b[0] and y0 < b[3] and y1 > b[1] for b in placed)):
                    continue
                text.set_position((x, y))
                placed.append(candidate)
                break
            else:
                complete = False
                break
        if complete:
            break
        width = math.ceil(width * 1.15)
        height = math.ceil(height * 1.15)
    else:
        plt.close(fig)
        raise ValueError('词表过密，无法在保持最小字号时完成词云布局，请缩小研究词表')
    return fig


def run(result, folder):
    save_figure(word_cloud, result, folder, "word_cloud")
