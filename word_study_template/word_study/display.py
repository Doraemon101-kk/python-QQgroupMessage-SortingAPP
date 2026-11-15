"""Optional viewing of published images; display errors never delete outputs."""
def show_saved(target, statuses):
    import matplotlib.pyplot as plt
    figures = []
    try:
        for name in ('monthly_trend', 'word_cloud'):
            if statuses.get(name, {}).get('status') != 'ok':
                continue
            figure, ax = plt.subplots()
            figures.append(figure)
            figure.canvas.manager.set_window_title(name)
            ax.imshow(plt.imread(target / f'{name}.png'))
            ax.set_axis_off()
            figure.tight_layout()
        if figures:
            plt.show()
    finally:
        for figure in figures:
            plt.close(figure)
