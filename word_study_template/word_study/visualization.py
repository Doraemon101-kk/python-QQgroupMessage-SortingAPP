"""Compatibility facade; new workflow calls independent output tasks."""
from pathlib import Path
from .monthly_plot import month_sequence, monthly_chart
from .cloud_plot import word_cloud
from .plot_support import _font


def render(result, output_dir: Path, *, show=False):
    from .service import generate_outputs
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    statuses = generate_outputs(result, target, ['monthly_trend', 'word_cloud'])
    if show:
        from .display import show_saved
        show_saved(target, statuses)
    return statuses
