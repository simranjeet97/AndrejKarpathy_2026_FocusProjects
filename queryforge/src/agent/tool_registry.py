import logging
from dataclasses import dataclass
from typing import Optional
from google.adk.tools import BaseTool, FunctionTool
from src.models import PermissionLevel

# Imports of all tool functions to be registered
from src.tools.database.churn_tools import (
    get_monthly_churn_by_segment,
    get_top_churned_segments,
    get_churn_trend,
    get_customer_count_by_segment,
    get_revenue_at_risk,
)
from src.tools.database.revenue_tools import (
    get_mrr_by_segment,
    get_ltv_by_segment,
    get_new_vs_churned_customers,
)
from src.tools.web.search_tool import (
    search_web,
    search_industry_benchmarks,
)
from src.tools.pdf.pdf_tool import PDFTool
from src.tools.charts.chart_tool import ChartTool
from src.tools.api.stripe_tools import (
    get_stripe_churn_events,
    get_stripe_mrr,
    get_stripe_customer_segment,
)
from src.tools.api.markdown_kb_tools import (
    search_markdown_kb,
    get_markdown_file_content,
    list_markdown_kb_files,
)

logger = logging.getLogger(__name__)

@dataclass
class ToolPermission:
    """Dataclass holding access control metadata for a tool."""
    name: str
    permission_level: PermissionLevel
    requires_auth: bool

class ToolRegistry:
    """Registry to manage and initialize Google Agents SDK compatible tools for QueryForge."""

    def __init__(self, settings, db_pool, ollama_client):
        """Initialize the ToolRegistry with settings, database pool, and Ollama client."""
        self.settings = settings
        self.db_pool = db_pool
        self.ollama_client = ollama_client

        # Instantiate class-based tools
        import os
        pdf_dir = os.path.abspath(os.path.join(settings.CHARTS_OUTPUT_DIR, "../pdfs"))
        self.pdf_tool = PDFTool(ollama_client, settings.MAX_PDF_PAGES, pdf_dir)
        self.chart_tool = ChartTool(settings.CHARTS_OUTPUT_DIR)

        self.tools = {}
        self.permissions = {}

    def register_all(self) -> list[BaseTool]:
        """Registers and returns all available tools as a list of BaseTool objects."""
        db_tools = self._register_database_tools()
        web_tools = self._register_web_tools()
        pdf_tools = self._register_pdf_tools()
        chart_tools = self._register_chart_tools()
        api_tools = self._register_api_tools()

        all_tools = db_tools + web_tools + pdf_tools + chart_tools + api_tools

        for tool in all_tools:
            self.tools[tool.name] = tool

        logger.info(f"Registered {len(self.tools)} tools: {list(self.tools.keys())}")
        return all_tools

    def _register_database_tools(self) -> list[BaseTool]:
        """Registers all database-specific query tools."""
        funcs = [
            get_monthly_churn_by_segment,
            get_top_churned_segments,
            get_churn_trend,
            get_customer_count_by_segment,
            get_revenue_at_risk,
            get_mrr_by_segment,
            get_ltv_by_segment,
            get_new_vs_churned_customers,
        ]
        tools = []
        for func in funcs:
            tool = FunctionTool(func)
            tools.append(tool)
            self.permissions[tool.name] = ToolPermission(
                name=tool.name,
                permission_level=PermissionLevel.READ_ONLY,
                requires_auth=False
            )
        return tools

    def _register_web_tools(self) -> list[BaseTool]:
        """Registers all DuckDuckGo web search and retrieval tools."""
        funcs = [
            search_web,
            search_industry_benchmarks,
        ]
        tools = []
        for func in funcs:
            tool = FunctionTool(func)
            tools.append(tool)
            self.permissions[tool.name] = ToolPermission(
                name=tool.name,
                permission_level=PermissionLevel.READ_ONLY,
                requires_auth=False
            )
        return tools

    def _register_pdf_tools(self) -> list[BaseTool]:
        """Registers PyMuPDF and Ollama-based PDF analysis tools."""
        funcs = [
            self.pdf_tool.summarize_pdf,
            self.pdf_tool.answer_question_from_pdf,
        ]
        tools = []
        for func in funcs:
            tool = FunctionTool(func)
            tools.append(tool)
            self.permissions[tool.name] = ToolPermission(
                name=tool.name,
                permission_level=PermissionLevel.READ_ONLY,
                requires_auth=False
            )
        return tools

    def _register_chart_tools(self) -> list[BaseTool]:
        """Registers visual data charting tools."""
        funcs = [
            self.chart_tool.generate_churn_chart,
            self.chart_tool.generate_trend_chart,
            self.chart_tool.generate_comparison_chart,
            self.chart_tool.generate_revenue_chart,
            self.chart_tool.generate_generic_chart,
        ]
        tools = []
        for func in funcs:
            tool = FunctionTool(func)
            tools.append(tool)
            self.permissions[tool.name] = ToolPermission(
                name=tool.name,
                permission_level=PermissionLevel.RESTRICTED,
                requires_auth=False
            )
        return tools

    def _register_api_tools(self) -> list[BaseTool]:
        """Registers Stripe and local markdown knowledge base API tools."""
        funcs = [
            get_stripe_churn_events,
            get_stripe_mrr,
            get_stripe_customer_segment,
            search_markdown_kb,
            get_markdown_file_content,
            list_markdown_kb_files,
        ]
        tools = []
        for func in funcs:
            tool = FunctionTool(func)
            tools.append(tool)
            self.permissions[tool.name] = ToolPermission(
                name=tool.name,
                permission_level=PermissionLevel.RESTRICTED,
                requires_auth=True
            )
        return tools

    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Looks up and returns a registered tool by its unique name."""
        return self.tools.get(name)

    def list_tool_names(self) -> list[str]:
        """Returns a list of all registered tool names."""
        return list(self.tools.keys())
