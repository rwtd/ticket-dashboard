#!/usr/bin/env python3
"""
Chart Components for Unified Analytics
=====================================
Interactive chart components using Plotly for rich visualizations
with backward compatibility support for matplotlib-based systems.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# --------------------------------------------------
# Configuration and Enums
# --------------------------------------------------

class ChartType(Enum):
    """Supported chart types"""
    TIME_SERIES = "time_series"
    BAR = "bar"
    PIE = "pie"
    MULTI_SERIES = "multi_series"
    SCATTER = "scatter"
    HEATMAP = "heatmap"


class ThemeMode(Enum):
    """Chart theme modes"""
    LIGHT = "plotly_white"
    DARK = "plotly_dark"
    MINIMAL = "simple_white"
    PRESENTATION = "presentation"


@dataclass
class ChartConfig:
    """Configuration settings for chart components"""
    width: int = 800
    height: int = 500
    theme: ThemeMode = ThemeMode.LIGHT
    show_legend: bool = True
    responsive: bool = True
    margin: Dict[str, int] = field(default_factory=lambda: {"l": 50, "r": 50, "t": 80, "b": 50})
    font_family: str = "Arial, sans-serif"
    font_size: int = 16
    color_palette: List[str] = field(default_factory=lambda: [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ])
    hover_template: Optional[str] = None
    animation_duration: int = 500


@dataclass
class InteractivityConfig:
    """Configuration for chart interactivity"""
    enable_zoom: bool = True
    enable_pan: bool = True
    enable_select: bool = True
    enable_hover: bool = True
    enable_crossfilter: bool = False
    show_toolbar: bool = True
    toolbar_orientation: str = "h"  # 'h' for horizontal, 'v' for vertical


# --------------------------------------------------
# Base Chart Component
# --------------------------------------------------

class ChartComponent(ABC):
    """
    Abstract base class for all chart components.
    Provides common functionality and interface for creating interactive charts.
    """
    
    def __init__(
        self,
        title: str,
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ):
        """
        Initialize chart component.
        
        Args:
            title: Chart title
            config: Chart configuration settings
            interactivity: Interactivity configuration
        """
        self.title = title
        self.config = config or ChartConfig()
        self.interactivity = interactivity or InteractivityConfig()
        self.figure: Optional[go.Figure] = None
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
    @abstractmethod
    def create_figure(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Create the Plotly figure for this chart type.
        
        Args:
            data: Source data for the chart
            **kwargs: Additional chart-specific parameters
            
        Returns:
            Configured Plotly figure
        """
        pass
    
    def apply_layout(self, figure: go.Figure) -> go.Figure:
        """
        Apply common layout settings to the figure.
        
        Args:
            figure: Plotly figure to configure
            
        Returns:
            Configured figure
        """
        layout_config = {
            "title": {
                "text": self.title,
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": self.config.font_size + 2}
            },
            "font": {
                "family": self.config.font_family,
                "size": self.config.font_size
            },
            "template": self.config.theme.value,
            "margin": self.config.margin,
            "showlegend": self.config.show_legend,
            "hovermode": "closest" if self.interactivity.enable_hover else False
        }
        
        if self.config.responsive:
            layout_config["autosize"] = True
        else:
            layout_config["width"] = self.config.width
            layout_config["height"] = self.config.height
            
        figure.update_layout(**layout_config)
        return figure
    
    def apply_interactivity(self, figure: go.Figure) -> go.Figure:
        """
        Apply interactivity settings to the figure.
        
        Args:
            figure: Plotly figure to configure
            
        Returns:
            Configured figure with interactivity settings
        """
        config = {
            "displayModeBar": self.interactivity.show_toolbar,
            "modeBarOrientation": self.interactivity.toolbar_orientation,
            "scrollZoom": self.interactivity.enable_zoom,
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"{self.title.lower().replace(' ', '_')}",
                "height": self.config.height,
                "width": self.config.width,
                "scale": 2
            }
        }
        
        # Configure toolbar buttons
        if not self.interactivity.enable_zoom:
            config["modeBarButtonsToRemove"] = config.get("modeBarButtonsToRemove", []) + ["zoom2d", "zoomIn2d", "zoomOut2d", "autoScale2d"]
        
        if not self.interactivity.enable_pan:
            config["modeBarButtonsToRemove"] = config.get("modeBarButtonsToRemove", []) + ["pan2d"]
            
        if not self.interactivity.enable_select:
            config["modeBarButtonsToRemove"] = config.get("modeBarButtonsToRemove", []) + ["select2d", "lasso2d"]
        
        figure.update_layout(dragmode="zoom" if self.interactivity.enable_zoom else False)
        return figure
    
    def render(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Render the complete chart with data.
        
        Args:
            data: Source data for the chart
            **kwargs: Additional chart-specific parameters
            
        Returns:
            Complete rendered Plotly figure
        """
        try:
            # Create the figure
            self.figure = self.create_figure(data, **kwargs)
            
            # Apply layout and interactivity
            self.figure = self.apply_layout(self.figure)
            self.figure = self.apply_interactivity(self.figure)
            
            return self.figure
            
        except Exception as e:
            self.logger.error(f"Error rendering chart '{self.title}': {str(e)}")
            raise ChartRenderError(f"Failed to render chart: {str(e)}") from e
    
    def to_html(self, include_plotlyjs: Union[bool, str] = "cdn", div_id: Optional[str] = None) -> str:
        """
        Convert the chart to HTML format for dashboard integration.
        
        Args:
            include_plotlyjs: How to include Plotly.js ('cdn', 'inline', True, False)
            div_id: Custom div ID for the chart container
            
        Returns:
            HTML string containing the chart
        """
        if not self.figure:
            raise ValueError("Chart must be rendered before converting to HTML")
        
        try:
            html = self.figure.to_html(
                include_plotlyjs=include_plotlyjs,
                div_id=div_id,
                config={
                    "displayModeBar": self.interactivity.show_toolbar,
                    "responsive": self.config.responsive
                }
            )
            
            # Wrap in a styled container div for dashboard integration
            container_class = f"chart-container {self.get_chart_type().value}-chart"
            wrapped_html = f'<div class="{container_class}">{html}</div>'
            
            return wrapped_html
            
        except Exception as e:
            self.logger.error(f"Error converting chart to HTML: {str(e)}")
            raise ChartRenderError(f"Failed to convert chart to HTML: {str(e)}") from e
    
    def to_json(self) -> str:
        """
        Convert the chart to JSON format for API usage.
        
        Returns:
            JSON string containing the chart configuration
        """
        if not self.figure:
            raise ValueError("Chart must be rendered before converting to JSON")
            
        return self.figure.to_json()
    
    @abstractmethod
    def get_chart_type(self) -> ChartType:
        """Return the chart type for this component"""
        pass
    
    def get_suggested_dimensions(self, data: pd.DataFrame) -> Tuple[int, int]:
        """
        Get suggested dimensions based on data characteristics.
        
        Args:
            data: Source data
            
        Returns:
            Tuple of (width, height)
        """
        return (self.config.width, self.config.height)


# --------------------------------------------------
# Specific Chart Components
# --------------------------------------------------

class TimeSeriesChart(ChartComponent):
    """Time series chart component for trend analysis"""
    
    def __init__(
        self,
        title: str = "Time Series Analysis",
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ):
        super().__init__(title, config, interactivity)
        
    def create_figure(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Create time series chart.
        
        Expected kwargs:
            x_column: Name of the datetime column
            y_column: Name of the value column
            color_column: Optional column for grouping/coloring
            line_mode: 'lines', 'markers', or 'lines+markers'
        """
        x_col = kwargs.get("x_column", data.columns[0])
        y_col = kwargs.get("y_column", data.columns[1])
        color_col = kwargs.get("color_column")
        line_mode = kwargs.get("line_mode", "lines+markers")
        
        if color_col and color_col in data.columns:
            # Multi-series time series
            fig = px.line(
                data,
                x=x_col,
                y=y_col,
                color=color_col,
                color_discrete_sequence=self.config.color_palette,
                markers=True if "markers" in line_mode else False
            )
        else:
            # Single series time series
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data[x_col],
                y=data[y_col],
                mode=line_mode,
                name=y_col,
                line=dict(color=self.config.color_palette[0])
            ))
        
        # Configure hover template
        hover_template = kwargs.get("hover_template", 
            f"<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>"
        )
        fig.update_traces(hovertemplate=hover_template)
        
        # Update axes
        fig.update_xaxes(title_text=x_col.replace("_", " ").title())
        fig.update_yaxes(title_text=y_col.replace("_", " ").title())
        
        return fig
    
    def get_chart_type(self) -> ChartType:
        return ChartType.TIME_SERIES


class BarChart(ChartComponent):
    """Bar chart component for categorical data"""
    
    def __init__(
        self,
        title: str = "Bar Chart Analysis",
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ):
        super().__init__(title, config, interactivity)
        
    def create_figure(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Create bar chart.
        
        Expected kwargs:
            x_column: Name of the category column
            y_column: Name of the value column
            orientation: 'v' for vertical, 'h' for horizontal
            color_column: Optional column for grouping/coloring
        """
        x_col = kwargs.get("x_column", data.columns[0])
        y_col = kwargs.get("y_column", data.columns[1])
        orientation = kwargs.get("orientation", "v")
        color_col = kwargs.get("color_column")
        
        if color_col and color_col in data.columns:
            # Grouped bar chart
            fig = px.bar(
                data,
                x=x_col if orientation == "v" else y_col,
                y=y_col if orientation == "v" else x_col,
                color=color_col,
                color_discrete_sequence=self.config.color_palette,
                orientation=orientation
            )
        else:
            # Simple bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=data[x_col] if orientation == "v" else data[y_col],
                y=data[y_col] if orientation == "v" else data[x_col],
                name=y_col,
                marker_color=self.config.color_palette[0],
                orientation=orientation
            ))
        
        # Configure hover template
        hover_template = kwargs.get("hover_template",
            f"<b>{x_col}</b>: %{{x}}<br><b>{y_col}</b>: %{{y}}<extra></extra>"
        )
        fig.update_traces(hovertemplate=hover_template)
        
        # Update axes
        if orientation == "v":
            fig.update_xaxes(title_text=x_col.replace("_", " ").title())
            fig.update_yaxes(title_text=y_col.replace("_", " ").title())
        else:
            fig.update_xaxes(title_text=y_col.replace("_", " ").title())
            fig.update_yaxes(title_text=x_col.replace("_", " ").title())
        
        return fig
    
    def get_chart_type(self) -> ChartType:
        return ChartType.BAR


class PieChart(ChartComponent):
    """Pie chart component for proportional data"""
    
    def __init__(
        self,
        title: str = "Distribution Analysis",
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ):
        super().__init__(title, config, interactivity)
        
    def create_figure(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Create pie chart.
        
        Expected kwargs:
            values_column: Name of the values column
            names_column: Name of the labels column
            hole_size: Size of hole for donut chart (0-0.9)
        """
        values_col = kwargs.get("values_column", data.columns[-1])
        names_col = kwargs.get("names_column", data.columns[0])
        hole_size = kwargs.get("hole_size", 0)
        
        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=data[names_col],
            values=data[values_col],
            hole=hole_size,
            marker=dict(colors=self.config.color_palette)
        ))
        
        # Configure hover template
        hover_template = kwargs.get("hover_template",
            "<b>%{label}</b><br>Value: %{value}<br>Percentage: %{percent}<extra></extra>"
        )
        fig.update_traces(hovertemplate=hover_template)
        
        return fig
    
    def get_chart_type(self) -> ChartType:
        return ChartType.PIE


class MultiSeriesChart(ChartComponent):
    """Multi-series chart component for complex comparative analytics"""
    
    def __init__(
        self,
        title: str = "Multi-Series Analysis",
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ):
        super().__init__(title, config, interactivity)
        
    def create_figure(self, data: pd.DataFrame, **kwargs) -> go.Figure:
        """
        Create multi-series chart with subplots or secondary axes.
        
        Expected kwargs:
            series_config: List of dicts with series configuration
            subplot_type: 'secondary_y', 'subplots', or 'overlay'
        """
        series_config = kwargs.get("series_config", [])
        subplot_type = kwargs.get("subplot_type", "overlay")
        
        if subplot_type == "secondary_y":
            fig = make_subplots(specs=[[{"secondary_y": True}]])
        elif subplot_type == "subplots":
            num_series = len(series_config)
            fig = make_subplots(rows=num_series, cols=1, shared_xaxes=True)
        else:
            fig = go.Figure()
        
        for i, series in enumerate(series_config):
            trace_type = series.get("type", "scatter")
            x_col = series.get("x_column")
            y_col = series.get("y_column")
            name = series.get("name", y_col)
            color = self.config.color_palette[i % len(self.config.color_palette)]
            
            if trace_type == "scatter":
                trace = go.Scatter(
                    x=data[x_col],
                    y=data[y_col],
                    mode=series.get("mode", "lines+markers"),
                    name=name,
                    line=dict(color=color)
                )
            elif trace_type == "bar":
                trace = go.Bar(
                    x=data[x_col],
                    y=data[y_col],
                    name=name,
                    marker_color=color
                )
            else:
                continue
            
            if subplot_type == "secondary_y":
                secondary = series.get("secondary_y", False)
                fig.add_trace(trace, secondary_y=secondary)
            elif subplot_type == "subplots":
                fig.add_trace(trace, row=i+1, col=1)
            else:
                fig.add_trace(trace)
        
        return fig
    
    def get_chart_type(self) -> ChartType:
        return ChartType.MULTI_SERIES


# --------------------------------------------------
# Chart Factory
# --------------------------------------------------

class ChartFactory:
    """Factory for creating chart components"""
    
    _chart_classes = {
        ChartType.TIME_SERIES: TimeSeriesChart,
        ChartType.BAR: BarChart,
        ChartType.PIE: PieChart,
        ChartType.MULTI_SERIES: MultiSeriesChart
    }
    
    @classmethod
    def create_chart(
        self,
        chart_type: ChartType,
        title: str,
        config: Optional[ChartConfig] = None,
        interactivity: Optional[InteractivityConfig] = None
    ) -> ChartComponent:
        """
        Create a chart component of the specified type.
        
        Args:
            chart_type: Type of chart to create
            title: Chart title
            config: Chart configuration
            interactivity: Interactivity configuration
            
        Returns:
            Chart component instance
        """
        if chart_type not in self._chart_classes:
            raise ValueError(f"Unsupported chart type: {chart_type}")
        
        chart_class = self._chart_classes[chart_type]
        return chart_class(title, config, interactivity)
    
    @classmethod
    def register_chart_type(
        self,
        chart_type: ChartType,
        chart_class: type
    ) -> None:
        """Register a new chart type with the factory"""
        if not issubclass(chart_class, ChartComponent):
            raise ValueError("Chart class must inherit from ChartComponent")
        
        self._chart_classes[chart_type] = chart_class


# --------------------------------------------------
# Predefined Chart Configurations
# --------------------------------------------------

class ChartPresets:
    """Predefined chart configurations for common use cases"""
    
    @staticmethod
    def dashboard_chart() -> ChartConfig:
        """Configuration optimized for dashboard display"""
        return ChartConfig(
            width=800,
            height=400,
            theme=ThemeMode.LIGHT,
            responsive=True,
            margin={"l": 60, "r": 40, "t": 80, "b": 60},
            font_size=16
        )
    
    @staticmethod
    def presentation_chart() -> ChartConfig:
        """Configuration optimized for presentations"""
        return ChartConfig(
            width=1000,
            height=600,
            theme=ThemeMode.PRESENTATION,
            responsive=False,
            margin={"l": 80, "r": 60, "t": 100, "b": 80},
            font_size=18
        )
    
    @staticmethod
    def mobile_chart() -> ChartConfig:
        """Configuration optimized for mobile displays"""
        return ChartConfig(
            width=400,
            height=300,
            theme=ThemeMode.MINIMAL,
            responsive=True,
            margin={"l": 40, "r": 20, "t": 60, "b": 40},
            font_size=14
        )
    
    @staticmethod
    def minimal_interactivity() -> InteractivityConfig:
        """Minimal interactivity for simple displays"""
        return InteractivityConfig(
            enable_zoom=False,
            enable_pan=False,
            enable_select=False,
            show_toolbar=False
        )
    
    @staticmethod
    def full_interactivity() -> InteractivityConfig:
        """Full interactivity for analysis dashboards"""
        return InteractivityConfig(
            enable_zoom=True,
            enable_pan=True,
            enable_select=True,
            enable_hover=True,
            show_toolbar=True
        )


# --------------------------------------------------
# Exceptions
# --------------------------------------------------

class ChartRenderError(Exception):
    """Raised when chart rendering fails"""
    pass


class ChartConfigError(Exception):
    """Raised when chart configuration is invalid"""
    pass


# --------------------------------------------------
# Utility Functions
# --------------------------------------------------

def validate_chart_data(data: pd.DataFrame, required_columns: List[str]) -> bool:
    """
    Validate that the data contains required columns.
    
    Args:
        data: DataFrame to validate
        required_columns: List of required column names
        
    Returns:
        True if valid, raises ValueError if not
    """
    missing_columns = set(required_columns) - set(data.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    if data.empty:
        raise ValueError("Data cannot be empty")
    
    return True


def auto_detect_chart_type(data: pd.DataFrame) -> ChartType:
    """
    Automatically detect the most appropriate chart type based on data characteristics.
    
    Args:
        data: DataFrame to analyze
        
    Returns:
        Suggested chart type
    """
    if len(data.columns) < 2:
        raise ValueError("Data must have at least 2 columns")
    
    # Check for datetime columns (time series)
    datetime_cols = data.select_dtypes(include=['datetime64']).columns
    if len(datetime_cols) > 0:
        return ChartType.TIME_SERIES
    
    # Check data types and characteristics
    numeric_cols = data.select_dtypes(include=['number']).columns
    categorical_cols = data.select_dtypes(include=['object', 'category']).columns
    
    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        # Check if suitable for pie chart (small number of categories)
        if len(categorical_cols) == 1 and data[categorical_cols[0]].nunique() <= 8:
            return ChartType.PIE
        else:
            return ChartType.BAR
    
    # Default to multi-series for complex data
    return ChartType.MULTI_SERIES