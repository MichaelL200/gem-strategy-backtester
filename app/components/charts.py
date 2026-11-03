"""Pure Plotly chart builders used by the Streamlit application."""

import pandas as pd
import plotly.express as px


def fit_legend(fig, mobile: bool):
    """Place legends below charts on narrow screens."""
    if mobile:
        fig.update_layout(legend={"orientation": "h", "x": 0, "y": -0.12, "yanchor": "top"})
    return fig


def create_main_chart(
    compare_df: pd.DataFrame,
    line_names: dict[str, str],
    line_colors: dict[str, str],
    show_benchmarks: bool,
    mobile: bool,
    color_order: list[str] | None = None,
):
    """Create the strategy, asset, and optional benchmark comparison chart."""
    title = (
        "Strategy vs. benchmarks & assets (start = 1)"
        if show_benchmarks
        else "Strategy vs. assets held alone (start = 1)"
    )
    colors = {
        name: px.colors.qualitative.Plotly[i % 10]
        for i, name in enumerate(color_order or compare_df.columns)
    }
    fig = px.line(compare_df, log_y=True, title=title, color_discrete_map=colors)
    fig.update_traces(line_width=1.2)
    for name, line_name in line_names.items():
        fig.update_traces(
            line={"width": 3.5, "color": line_colors[name]},
            selector={"name": line_name},
        )
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", margin={"t": 60})
    return fit_legend(fig, mobile), colors


def create_drawdown_chart(results: dict, line_colors: dict[str, str], mobile: bool, both: bool):
    """Create a drawdown chart for one or both strategies."""
    if both:
        fig = px.line(
            pd.DataFrame({name: result.drawdown * 100 for name, result in results.items()}),
            title="Strategy drawdown (%)",
            color_discrete_map=line_colors,
        )
    else:
        fig = px.area(next(iter(results.values())).drawdown * 100, title="Strategy drawdown (%)")
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="")
    return fit_legend(fig, mobile) if both else fig


def create_composition_chart(result, label_map: dict, colors: dict, mobile: bool, strategy_name: str, both: bool):
    """Create a portfolio composition chart."""
    fig = px.area(
        result.composition.rename(columns=label_map) * 100,
        groupnorm="percent",
        title="Portfolio composition (%)" + (f" · {strategy_name}" if both else ""),
        color_discrete_map=colors,
    )
    fig.update_layout(legend_title_text="", xaxis_title="", yaxis_title="", yaxis_ticksuffix="%")
    return fit_legend(fig, mobile)
