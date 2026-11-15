"""Shared plotting utilities; Matplotlib loads only when a chart runs."""
def _font():
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'SimSun', 'Arial Unicode MS'):
        if name in available:
            return name
    return 'DejaVu Sans'



def save_figure(create, result, folder, name):
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    previous = set(plt.get_fignums())
    with mpl.rc_context({'font.family': _font(), 'axes.unicode_minus': False,
                         'text.parse_math': False}):
        try:
            figure = create(result)
            figure.savefig(folder / f'{name}.png', dpi=160)
            figure.savefig(folder / f'{name}.svg')
        finally:
            for number in set(plt.get_fignums()) - previous:
                plt.close(number)
