from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict, computed_field

class PermissionLevel(str, Enum):
    """Enumeration of access control permission levels."""
    READ_ONLY = "READ_ONLY"
    RESTRICTED = "RESTRICTED"
    INTERNAL = "INTERNAL"

class ToolInput(BaseModel):
    """Model representing the input parameters sent to a tool execution."""
    model_config = ConfigDict(use_enum_values=True)

    tool_name: str = Field(
        ..., 
        description="The name of the tool being executed", 
        examples=["query_postgres_billing"]
    )
    arguments: dict[str, Any] = Field(
        ..., 
        description="Key-value arguments passed to the tool", 
        examples=[{"limit": 10, "offset": 0}]
    )
    caller_context: str = Field(
        ..., 
        description="The context or task description prompting this tool call", 
        examples=["Fetch top paying customers for Q2 analysis"]
    )

class ToolOutput(BaseModel):
    """Model representing the result output of a tool execution."""
    model_config = ConfigDict(use_enum_values=True)

    tool_name: str = Field(
        ..., 
        description="The name of the executed tool", 
        examples=["query_postgres_billing"]
    )
    success: bool = Field(
        ..., 
        description="True if the tool executed successfully, False otherwise", 
        examples=[True]
    )
    result: Any = Field(
        ..., 
        description="The raw return payload of the tool", 
        examples=[{"status": "ok", "rows_fetched": 10}]
    )
    error: Optional[str] = Field(
        None, 
        description="Error message if success is False, otherwise None", 
        examples=["Connection timeout to host db"]
    )
    latency_ms: int = Field(
        ..., 
        description="Time taken to run the tool in milliseconds", 
        examples=[124]
    )

class ToolCall(BaseModel):
    """Model logging a complete tool invocation lifecycle."""
    model_config = ConfigDict(use_enum_values=True)

    input: ToolInput = Field(
        ..., 
        description="The input details of the tool call"
    )
    output: ToolOutput = Field(
        ..., 
        description="The output details of the tool call"
    )
    timestamp: datetime = Field(
        ..., 
        description="Timestamp when the tool call was recorded", 
        examples=["2026-06-07T23:23:00Z"]
    )

class QueryResult(BaseModel):
    """Model representing structured database query results."""
    model_config = ConfigDict(use_enum_values=True)

    columns: list[str] = Field(
        ..., 
        description="List of column names returned by the query", 
        examples=[["customer_id", "email", "subscription_status"]]
    )
    rows: list[list[Any]] = Field(
        ..., 
        description="List of database rows, each row being a list of values", 
        examples=[[[1, "user1@example.com", "active"], [2, "user2@example.com", "churned"]]]
    )
    row_count: int = Field(
        ..., 
        description="Total number of rows in the result set", 
        examples=[2]
    )
    query_name: str = Field(
        ..., 
        description="Name identifier of the database query executed", 
        examples=["get_active_subscriptions"]
    )

class ChurnSegment(BaseModel):
    """Model representing churn analysis metrics grouped by customer segment."""
    model_config = ConfigDict(use_enum_values=True)

    segment_name: str = Field(
        ..., 
        description="Name of the customer segment", 
        examples=["Enterprise Plan Users"]
    )
    churn_rate: float = Field(
        ..., 
        description="Churn rate percentage as a decimal (0.0 to 1.0)", 
        examples=[0.045]
    )
    customer_count: int = Field(
        ..., 
        description="Total count of customers in this segment", 
        examples=[1200]
    )
    period: str = Field(
        ..., 
        description="Timeframe of the segment analysis", 
        examples=["Q1 2026"]
    )

class IndustryBenchmark(BaseModel):
    """Model representing external industry standard performance metrics."""
    model_config = ConfigDict(use_enum_values=True)

    metric_name: str = Field(
        ..., 
        description="Name of the benchmarked metric", 
        examples=["SaaS LTV/CAC Ratio"]
    )
    value: float = Field(
        ..., 
        description="Target benchmark value", 
        examples=[3.5]
    )
    source: str = Field(
        ..., 
        description="Source of the benchmark data", 
        examples=["Gartner SaaS Survey 2025"]
    )
    retrieved_at: datetime = Field(
        ..., 
        description="Timestamp when the benchmark was fetched", 
        examples=["2026-06-07T23:23:00Z"]
    )

class PDFSummary(BaseModel):
    """Model representing the structured summarization of a PDF document."""
    model_config = ConfigDict(use_enum_values=True)

    filename: str = Field(
        ..., 
        description="Name of the analyzed PDF file", 
        examples=["quarterly_report.pdf"]
    )
    page_count: int = Field(
        ..., 
        description="Total page count of the PDF", 
        examples=[12]
    )
    summary: str = Field(
        ..., 
        description="Executive summary of the document contents", 
        examples=["The document covers Q1 financial performance and marketing cost allocations."]
    )
    key_points: list[str] = Field(
        ..., 
        description="List of primary takeaways or action items", 
        examples=[["Revenue up 15% YoY", "Marketing CAC decreased by 8%"]]
    )
    tokens_used: int = Field(
        ..., 
        description="Number of LLM tokens consumed for analysis", 
        examples=[4500]
    )

class ChartOutput(BaseModel):
    """Model representing the metadata of a generated analytical chart."""
    model_config = ConfigDict(use_enum_values=True)

    chart_type: str = Field(
        ..., 
        description="Type of the generated chart", 
        examples=["line_chart"]
    )
    filepath: str = Field(
        ..., 
        description="Local path to the saved chart image file", 
        examples=["/workspace/data/charts/churn_by_cohort_202606.png"]
    )
    title: str = Field(
        ..., 
        description="Title of the generated chart", 
        examples=["Customer Churn Rate by Monthly Cohort"]
    )
    data_summary: str = Field(
        ..., 
        description="Brief text summary of the trend shown in the chart", 
        examples=["Line chart depicting a steady decrease in churn rates starting from March 2026 cohort."]
    )

class AgentResponse(BaseModel):
    """Model representing the final comprehensive response from the agent."""
    model_config = ConfigDict(use_enum_values=True)

    query: str = Field(
        ..., 
        description="The original user query submitted to the agent", 
        examples=["Compare our Q1 churn rates against SaaS industry averages."]
    )
    answer: str = Field(
        ..., 
        description="Synthesized markdown answer resolving the query", 
        examples=["Our Q1 churn rate of 4.5% is slightly higher than the SaaS industry benchmark of 3.5%."]
    )
    tool_calls: list[ToolCall] = Field(
        ..., 
        description="List of tools invoked during the research process"
    )
    sources: list[str] = Field(
        ..., 
        description="List of source links, file paths, or references used to generate the answer", 
        examples=[["Gartner SaaS Survey 2025", "internal_billing_db.get_active_subscriptions"]]
    )
    chart_paths: list[str] = Field(
        ..., 
        description="List of local file paths for generated charts", 
        examples=[["/workspace/data/charts/churn_comparison.png"]]
    )
    total_latency_ms: int = Field(
        ..., 
        description="Total duration of agent reasoning and tool executions in milliseconds", 
        examples=[2450]
    )

    @computed_field
    @property
    def tool_count(self) -> int:
        """The total count of tools called during the agent's run."""
        return len(self.tool_calls)
