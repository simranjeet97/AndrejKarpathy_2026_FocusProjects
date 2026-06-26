from typing import List, Dict, Any, Optional

class DashboardRenderer:
    """
    Renders Jinja2 HTML templates for the evaluation dashboard.
    Leverages vanilla CSS and embeds Chart.js script tags for visual tracking.
    """

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the dashboard renderer.

        Args:
            templates_dir (str, optional): Target directory for HTML templates.
        """
        pass

    def render_summary_page(
        self, runs: List[Dict[str, Any]], stats: Dict[str, Any]
    ) -> str:
        """
        Generate the HTML markup for the main dashboard overview page.

        Args:
            runs (List[Dict[str, Any]]): List of historical runs.
            stats (Dict[str, Any]): Aggregated run metrics (pass rates, latencies).

        Returns:
            str: Valid HTML response body.
        """
        pass

    def render_run_detail(self, run_details: Dict[str, Any]) -> str:
        """
        Generate HTML markup for a single evaluation run's detailed breakdown.

        Args:
            run_details (Dict[str, Any]): Run settings, metrics, and per-task results.

        Returns:
            str: Valid HTML response body.
        """
        pass

    def render_comparison_dashboard(
        self, comparison_summary: Dict[str, Any], pairwise_records: List[Dict[str, Any]]
    ) -> str:
        """
        Generate HTML markup displaying the pairwise comparison delta and win/loss rates.

        Args:
            comparison_summary (Dict[str, Any]): Aggregate win rates, loss rates, ties.
            pairwise_records (List[Dict[str, Any]]): Individual comparison records.

        Returns:
            str: Valid HTML response body.
        """
        pass
