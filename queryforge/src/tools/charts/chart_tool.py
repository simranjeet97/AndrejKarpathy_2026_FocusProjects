import os
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
import numpy as np
from src.models import ChurnSegment, IndustryBenchmark, ChartOutput

class ChartTool:
    """Tool for generating various data visualization charts using Matplotlib with a dark Red/Yellow theme."""

    def __init__(self, output_dir: str):
        """Initialize the ChartTool with the output directory path."""
        self.output_dir = os.path.abspath(output_dir)
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _apply_dark_theme(self, fig, ax):
        """Apply a premium dark HUD theme (Red, Yellow, Black) to Matplotlib figure/axes."""
        # Set face colors
        fig.patch.set_facecolor('#08080a') # Pitch black
        ax.set_facecolor('#0c0c0e')        # Dark charcoal card background
        
        # Grid lines (subtle dark gray)
        ax.grid(True, color='#222225', linestyle=':', linewidth=0.5)
        
        # Color ticks and labels
        ax.tick_params(colors='#f3f4f6', labelsize=9)
        ax.xaxis.label.set_color('#f3f4f6')
        ax.yaxis.label.set_color('#f3f4f6')
        ax.title.set_color('#ffd33d')      # Neon Yellow titles
        
        # Color spine borders
        for spine in ax.spines.values():
            spine.set_color('#333336')

    def _resolve_segments(self, segments: list) -> list[ChurnSegment]:
        resolved = []
        if not segments:
            return resolved
        for s in segments:
            if isinstance(s, ChurnSegment):
                resolved.append(s)
            elif isinstance(s, dict):
                try:
                    resolved.append(ChurnSegment(**s))
                except Exception:
                    resolved.append(ChurnSegment(
                        segment_name=s.get("segment_name", "Unknown"),
                        churn_rate=float(s.get("churn_rate", 0.0)),
                        customer_count=int(s.get("customer_count", 0)),
                        period=s.get("period", "N/A")
                    ))
            elif isinstance(s, str):
                import sqlite3
                try:
                    conn = sqlite3.connect("queryforge.db")
                    cursor = conn.cursor()
                    # Query active customer count
                    cursor.execute("SELECT COUNT(*) FROM customers WHERE segment = ? AND (cancelled_at IS NULL OR date(cancelled_at) > date('now'))", (s,))
                    active = cursor.fetchone()[0]
                    # Query churned customer count in the last 30 days
                    cursor.execute("SELECT COUNT(*) FROM churn_events WHERE segment = ? AND date(churned_at) >= date('now', '-30 day')", (s,))
                    churned = cursor.fetchone()[0]
                    conn.close()
                    rate = churned / active if active > 0 else 0.0
                    resolved.append(ChurnSegment(
                        segment_name=s,
                        churn_rate=rate,
                        customer_count=active,
                        period="Last 30 Days"
                    ))
                except Exception:
                    resolved.append(ChurnSegment(segment_name=s, churn_rate=0.0, customer_count=0, period="N/A"))
            else:
                resolved.append(ChurnSegment(segment_name=str(s), churn_rate=0.0, customer_count=0, period="N/A"))
        return resolved

    def generate_churn_chart(self, segments: list = None, title: str = "Churn by Segment") -> ChartOutput:
        """Horizontal bar chart: churn rate by segment.
        
        Args:
            segments: List of ChurnSegment objects, dictionaries, or segment names (strings).
            title: Title of the chart.
        """
        # Parse inputs
        if isinstance(segments, str):
            import json
            try:
                segments = json.loads(segments)
            except Exception:
                segments = [segments]

        if not segments:
            import sqlite3
            try:
                conn = sqlite3.connect("queryforge.db")
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT segment FROM customers")
                segments = [row[0] for row in cursor.fetchall()]
                conn.close()
            except Exception:
                segments = []

        resolved_segs = self._resolve_segments(segments)
        sorted_segs = sorted(resolved_segs, key=lambda s: s.churn_rate)
        names = [s.segment_name for s in sorted_segs]
        rates = [s.churn_rate for s in sorted_segs]

        # Determine colors based on thresholds matching Red/Yellow theme
        colors = []
        for r in rates:
            if r > 0.05:
                colors.append("#ff334b")  # Crimson Red
            elif r > 0.02:
                colors.append("#ffd33d")  # Gold Yellow
            else:
                colors.append("#ffea79")  # Soft Light Yellow

        fig = Figure(figsize=(8, 4))
        ax = fig.subplots()
        self._apply_dark_theme(fig, ax)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        bars = ax.barh(names, [r * 100 for r in rates], color=colors)

        # Add labels at the end of the bars
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + 0.1,
                bar.get_y() + bar.get_height() / 2,
                f"{width:.1f}%",
                va='center',
                ha='left',
                color='#f3f4f6',
                fontsize=9
            )

        ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
        ax.set_xlabel("Churn Rate (%)", fontsize=10)

        filename = f"churn_by_segment_{int(datetime.utcnow().timestamp())}.png"
        filepath = self._save_chart(fig, filename)

        summary = f"Horizontal bar chart showing customer churn rate by segment: " + ", ".join([f"{name}: {rate*100:.1f}%" for name, rate in zip(names, rates)])

        return ChartOutput(
            chart_type="horizontal_bar",
            filepath=filepath,
            title=title,
            data_summary=summary
        )

    def generate_trend_chart(self, trend_data: list, segment: str) -> ChartOutput:
        """Line chart: churn trend over time for a segment.
        
        Args:
            trend_data: List of dictionaries containing "month" and "churn_rate".
            segment: Name of the segment.
        """
        months = [d["month"] for d in trend_data]
        rates = [d["churn_rate"] * 100 for d in trend_data]

        fig = Figure(figsize=(8, 4))
        ax = fig.subplots()
        self._apply_dark_theme(fig, ax)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Crimson Red line for churn trend
        ax.plot(months, rates, marker='o', color='#ff334b', linewidth=2, label="Churn Rate")

        # Add dashed average line in Neon Yellow
        avg_rate = sum(rates) / len(rates) if rates else 0.0
        ax.axhline(avg_rate, color='#ffd33d', linestyle='--', linewidth=1.5, label=f"Average ({avg_rate:.1f}%)")

        ax.set_title(f"Churn Trend: {segment}", fontsize=12, fontweight='bold', pad=15)
        ax.set_ylabel("Churn Rate (%)", fontsize=10)
        ax.set_xlabel("Month", fontsize=10)
        ax.set_ylim(0, max(rates + [avg_rate, 5]) + 1)
        
        # Style legend
        legend = ax.legend(loc="upper right")
        legend.get_frame().set_facecolor('#0c0c0e')
        legend.get_frame().set_edgecolor('#333336')
        for text in legend.get_texts():
            text.set_color('#f3f4f6')

        # Rotate x ticks
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)

        filename = f"churn_trend_{segment.lower().replace(' ', '_')}_{int(datetime.utcnow().timestamp())}.png"
        filepath = self._save_chart(fig, filename)

        summary = f"Line chart showing the monthly churn rate trend for {segment} over {len(months)} months. Current average churn rate is {avg_rate:.1f}%."

        return ChartOutput(
            chart_type="line_chart",
            filepath=filepath,
            title=f"Churn Trend: {segment}",
            data_summary=summary
        )

    def generate_comparison_chart(
        self, internal: list, benchmarks: list, metric: str
    ) -> ChartOutput:
        """Side-by-side bar: internal data vs industry benchmarks.
        
        Args:
            internal: List of ChurnSegment objects or dicts.
            benchmarks: List of IndustryBenchmark objects or dicts.
            metric: The name of the metric being compared.
        """
        resolved_internal = self._resolve_segments(internal)
        segment_names = [s.segment_name for s in resolved_internal]
        internal_values = [s.churn_rate * 100 for s in resolved_internal]

        # Use benchmark average or default if no benchmarks are found
        benchmark_value = sum(b.value * 100 if b.value < 1.0 else b.value for b in benchmarks) / len(benchmarks) if benchmarks else 3.5

        x = np.arange(len(segment_names))
        width = 0.35

        fig = Figure(figsize=(8, 4))
        ax = fig.subplots()
        self._apply_dark_theme(fig, ax)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Internal: Crimson Red, Benchmark: Amber Yellow
        rects1 = ax.bar(x - width/2, internal_values, width, label='Internal', color='#ff334b')
        rects2 = ax.bar(x + width/2, [benchmark_value] * len(segment_names), width, label='Industry Benchmark', color='#ffd33d')

        ax.set_ylabel('Rate (%)')
        ax.set_title(f'Internal vs Benchmark: {metric}', fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(segment_names)
        
        # Rotate x ticks
        for tick in ax.get_xticklabels():
            tick.set_rotation(15)

        # Style legend
        legend = ax.legend()
        legend.get_frame().set_facecolor('#0c0c0e')
        legend.get_frame().set_edgecolor('#333336')
        for text in legend.get_texts():
            text.set_color('#f3f4f6')

        # Helper to label values on top of bars
        for rect in rects1:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, color='#f3f4f6')

        for rect in rects2:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, color='#f3f4f6')

        filename = f"comparison_{metric.lower().replace(' ', '_')}_{int(datetime.utcnow().timestamp())}.png"
        filepath = self._save_chart(fig, filename)

        summary = f"Grouped bar chart comparing internal {metric} rates across segments with the industry benchmark of {benchmark_value:.1f}%."

        return ChartOutput(
            chart_type="comparison_bar",
            filepath=filepath,
            title=f"Internal vs Benchmark: {metric}",
            data_summary=summary
        )

    def generate_revenue_chart(self, revenue_data: dict = None) -> ChartOutput:
        """Stacked bar or pie chart depending on segment count representing MRR.
        
        Args:
            revenue_data: Dictionary mapping segment names to MRR values.
        """
        # Robustly parse data
        parsed_data = {}
        if isinstance(revenue_data, str):
            import json
            try:
                revenue_data = json.loads(revenue_data)
            except Exception:
                pass
        
        if isinstance(revenue_data, list):
            new_data = {}
            for item in revenue_data:
                if isinstance(item, dict):
                    label = item.get("segment") or item.get("name") or item.get("label") or (list(item.keys())[0] if item.keys() else None)
                    value = item.get("mrr") or item.get("value") or item.get("mrr_usd") or (list(item.values())[0] if item.values() else None)
                    if label is not None:
                        new_data[str(label)] = value
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    new_data[str(item[0])] = item[1]
            revenue_data = new_data

        if isinstance(revenue_data, dict):
            for k, v in revenue_data.items():
                if v is not None:
                    try:
                        parsed_data[str(k)] = float(v)
                    except (ValueError, TypeError):
                        continue
        
        revenue_data = parsed_data

        if not revenue_data or sum(revenue_data.values()) == 0:
            import sqlite3
            try:
                conn = sqlite3.connect("queryforge.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT segment, COALESCE(SUM(mrr_cents), 0) / 100.0 as mrr_usd
                    FROM customers
                    WHERE cancelled_at IS NULL OR date(cancelled_at) > date('now')
                    GROUP BY segment
                """)
                revenue_data = {row[0]: float(row[1]) for row in cursor.fetchall()}
                conn.close()
            except Exception:
                revenue_data = {"No Data": 0.0}

        segments = list(revenue_data.keys())
        mrr_values = list(revenue_data.values())
        total_mrr = sum(mrr_values)

        fig = Figure(figsize=(6, 6))
        fig.patch.set_facecolor('#08080a')
        ax = fig.subplots()
        ax.set_facecolor('#0c0c0e')

        # Colors matching the red/yellow theme
        theme_colors = ['#ff334b', '#ffd33d', '#ffea79', '#cc112a', '#e0b320']

        if len(segments) <= 5:
            wedges, texts, autotexts = ax.pie(
                mrr_values,
                labels=segments,
                autopct='%1.1f%%',
                startangle=140,
                colors=theme_colors[:len(segments)]
            )
            for text in texts:
                text.set_color('#f3f4f6')
            for autotext in autotexts:
                autotext.set_color('#08080a')
                autotext.set_weight('bold')
            chart_type = "pie_chart"
            title = "MRR Contribution by Segment"
        else:
            self._apply_dark_theme(fig, ax)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            y_pos = range(len(segments))
            ax.barh(y_pos, mrr_values, color=theme_colors[0])
            ax.set_yticks(y_pos)
            ax.set_yticklabels(segments)
            ax.set_xlabel("MRR (USD)", fontsize=10)
            chart_type = "horizontal_bar"
            title = "MRR by Segment"

            # Add value labels
            for i, v in enumerate(mrr_values):
                ax.text(v + (total_mrr * 0.01 if total_mrr > 0 else 0.1), i, f"${v:,.2f}", va='center', ha='left', color='#f3f4f6', fontsize=9)

        ax.set_title(title, fontsize=12, fontweight='bold', pad=15, color='#ffd33d')

        filename = f"revenue_mrr_{int(datetime.utcnow().timestamp())}.png"
        filepath = self._save_chart(fig, filename)

        summary = f"Chart showing MRR contribution by segment (Total: ${total_mrr:,.2f}). " + ", ".join([f"{seg}: ${val:,.2f}" for seg, val in revenue_data.items()])

        return ChartOutput(
            chart_type=chart_type,
            filepath=filepath,
            title=title,
            data_summary=summary
        )

    def generate_generic_chart(self, data: dict = None, title: str = "Metric Chart", value_label: str = "Value") -> ChartOutput:
        """Generate a bar or pie chart representing any key-value data (e.g. customer counts).
        
        Args:
            data: A dictionary mapping label names (str) to values (numeric).
            title: The title of the chart.
            value_label: Label for the values (e.g., 'Customer Count', 'Active Users').
        """
        # Robustly parse data
        parsed_data = {}
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                pass
        
        if isinstance(data, list):
            new_data = {}
            for item in data:
                if isinstance(item, dict):
                    label = item.get("segment") or item.get("name") or item.get("label") or (list(item.keys())[0] if item.keys() else None)
                    value = item.get("count") or item.get("value") or item.get("mrr") or (list(item.values())[0] if item.values() else None)
                    if label is not None:
                        new_data[str(label)] = value
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    new_data[str(item[0])] = item[1]
            data = new_data

        if isinstance(data, dict):
            for k, v in data.items():
                if v is not None:
                    try:
                        parsed_data[str(k)] = float(v)
                    except (ValueError, TypeError):
                        continue
        
        data = parsed_data

        if not data or sum(data.values()) == 0:
            import sqlite3
            try:
                conn = sqlite3.connect("queryforge.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT segment, COUNT(*) as count 
                    FROM customers 
                    WHERE cancelled_at IS NULL OR date(cancelled_at) > date('now')
                    GROUP BY segment
                """)
                data = {row[0]: float(row[1]) for row in cursor.fetchall()}
                conn.close()
                if not title or title == "Metric Chart":
                    title = "Active Customers by Segment"
                value_label = "Customer Count"
            except Exception:
                data = {"No Data": 0.0}

        labels = list(data.keys())
        values = list(data.values())
        total_value = sum(values)

        fig = Figure(figsize=(8, 4))
        fig.patch.set_facecolor('#08080a')
        ax = fig.subplots()
        self._apply_dark_theme(fig, ax)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Colors matching the red/yellow theme
        colors = ['#ff334b', '#ffd33d', '#ffea79', '#cc112a', '#e0b320'][:len(labels)]
        while len(colors) < len(labels):
            colors.extend(colors)
        colors = colors[:len(labels)]

        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color=colors)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel(value_label, fontsize=10)
        
        ax.set_title(title, fontsize=12, fontweight='bold', pad=15)

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + (total_value * 0.01 if total_value > 0 else 0.1),
                bar.get_y() + bar.get_height() / 2,
                f"{width:,.0f}" if width.is_integer() else f"{width:,.2f}",
                va='center',
                ha='left',
                color='#f3f4f6',
                fontsize=9
            )

        filename = f"generic_chart_{int(datetime.utcnow().timestamp())}.png"
        filepath = self._save_chart(fig, filename)

        summary = f"Horizontal bar chart representing {title}: " + ", ".join([f"{l}: {v}" for l, v in data.items()])

        return ChartOutput(
            chart_type="horizontal_bar",
            filepath=filepath,
            title=title,
            data_summary=summary
        )

    def _save_chart(self, fig, filename: str) -> str:
        """Save a Matplotlib figure to the output directory and return its absolute filepath."""
        filepath = os.path.abspath(os.path.join(self.output_dir, filename))
        fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor(), transparent=False)
        return filepath
