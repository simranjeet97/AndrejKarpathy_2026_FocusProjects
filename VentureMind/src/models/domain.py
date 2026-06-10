from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, computed_field

class LegalFlagType(str, Enum):
    """Types of legal flags that can be identified."""
    LAWSUIT = "LAWSUIT"
    REGULATORY = "REGULATORY"
    IP_DISPUTE = "IP_DISPUTE"
    COMPLIANCE = "COMPLIANCE"
    NONE = "NONE"

class Severity(str, Enum):
    """Severity levels for legal flags."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"

class AgentStatus(str, Enum):
    """Execution status of a specialist agent."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"

class StartupProfile(BaseModel):
    """General information and background profile of the startup."""
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., examples=["VentureMind Inc."])
    website: str = Field(..., examples=["https://venturemind.ai"])
    founded_year: int = Field(..., examples=[2025])
    headquarters: str = Field(..., examples=["San Francisco, CA"])
    industry: str = Field(..., examples=["Enterprise AI"])
    description: str = Field(..., examples=["A multi-agent startup due diligence platform."])
    founders: list[str] = Field(..., examples=[["Alice Smith", "Bob Jones"]])

class MarketData(BaseModel):
    """Market size metrics, trends, and data sources."""
    model_config = ConfigDict(use_enum_values=True)

    tam_usd: float = Field(..., examples=[10000000000.0])
    sam_usd: float = Field(..., examples=[2500000000.0])
    som_usd: float = Field(..., examples=[500000000.0])
    cagr_pct: float = Field(..., examples=[15.4])
    key_trends: list[str] = Field(..., examples=[["Generative AI automation", "Decentralized data scaling"]])
    sources: list[str] = Field(..., examples=[["Gartner 2026", "IDC Report"]])

class Competitor(BaseModel):
    """Detailed profile of a direct or indirect competitor."""
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., examples=["CompetitorCorp"])
    website: str = Field(..., examples=["https://competitorcorp.com"])
    founded_year: int = Field(..., examples=[2023])
    funding_usd: float | None = Field(None, examples=[12000000.0])
    market_share_pct: float | None = Field(None, examples=[5.2])
    strengths: list[str] = Field(..., examples=[["Early market entry", "Strong brand"]])
    weaknesses: list[str] = Field(..., examples=[["High churn rate", "Legacy tech stack"]])

class CompetitorLandscape(BaseModel):
    """Analysis of the startup's competitive ecosystem and positioning."""
    model_config = ConfigDict(use_enum_values=True)

    startup_name: str = Field(..., examples=["VentureMind Inc."])
    competitors: list[Competitor] = Field(..., examples=[[]])
    positioning_summary: str = Field(..., examples=["Strong tech differentiation but trailing in sales reach."])
    differentiation_score: float = Field(..., examples=[8.5])

class FinancialSignal(BaseModel):
    """A specific financial metric signal extracted from external sources."""
    model_config = ConfigDict(use_enum_values=True)

    metric_name: str = Field(..., examples=["Revenue Growth"])
    value: str = Field(..., examples=["150% YoY"])
    period: str = Field(..., examples=["FY2025"])
    source: str = Field(..., examples=["PitchBook"])
    confidence: float = Field(..., examples=[0.9])

class FinancialProfile(BaseModel):
    """Financial standing, funding history, and runway estimations."""
    model_config = ConfigDict(use_enum_values=True)

    startup_name: str = Field(..., examples=["VentureMind Inc."])
    signals: list[FinancialSignal] = Field(..., examples=[[]])
    funding_rounds: list[dict] = Field(..., examples=[[{"round": "Seed", "amount": 2000000}]])
    burn_rate_estimate: str = Field(..., examples=["$150k/month"])
    runway_estimate: str = Field(..., examples=["18 months"])

class LegalFlag(BaseModel):
    """A specific legal issue or risk identified for the startup."""
    model_config = ConfigDict(use_enum_values=True)

    flag_type: LegalFlagType = Field(..., examples=[LegalFlagType.COMPLIANCE])
    description: str = Field(..., examples=["GDPR compliance gap identified in user data collection."])
    severity: Severity = Field(..., examples=[Severity.MEDIUM])
    source: str = Field(..., examples=["Terms of Service Audit"])

class LegalProfile(BaseModel):
    """Legal compliance status, lawsuits, and intellectual property holdings."""
    model_config = ConfigDict(use_enum_values=True)

    startup_name: str = Field(..., examples=["VentureMind Inc."])
    incorporation_status: str = Field(..., examples=["Delaware C-Corp"])
    flags: list[LegalFlag] = Field(..., examples=[[]])
    patent_count: int = Field(..., examples=[3])
    trademark_count: int = Field(..., examples=[1])

class AgentResult(BaseModel):
    """Execution metadata and output data of an individual agent."""
    model_config = ConfigDict(use_enum_values=True)

    agent_name: str = Field(..., examples=["Market Research Agent"])
    status: AgentStatus = Field(..., examples=[AgentStatus.SUCCESS])
    data: dict | None = Field(None, examples=[{"tam": 1000000000}])
    error: str | None = Field(None, examples=[None])
    duration_ms: int = Field(..., examples=[4500])
    sources: list[str] = Field(..., examples=[["DuckDuckGo", "Wikipedia"]])

class DiligenceReport(BaseModel):
    """Comprehensive due diligence report synthesized from all agent analyses."""
    model_config = ConfigDict(use_enum_values=True)

    startup_name: str = Field(..., examples=["VentureMind Inc."])
    generated_at: datetime = Field(..., examples=["2026-06-11T00:00:00Z"])
    market: MarketData | None = Field(None)
    competitors: CompetitorLandscape | None = Field(None)
    financials: FinancialProfile | None = Field(None)
    legal: LegalProfile | None = Field(None)
    summary: str = Field(..., examples=["Overall solid startup with clean legal profile and strong financials."])
    investment_score: float = Field(..., examples=[8.2])
    risk_flags: list[str] = Field(..., examples=[["GDPR compliance gap"]])
    agent_results: list[AgentResult] = Field(..., examples=[[]])

    @property
    def passed_agents(self) -> int:
        """Count of agents that executed successfully."""
        return sum(1 for r in self.agent_results if r.status == AgentStatus.SUCCESS or r.status == "SUCCESS")

    @computed_field
    @property
    def overall_confidence(self) -> float:
        """Mean of all agent confidence signals in the financial profile."""
        if not self.financials or not self.financials.signals:
            return 0.0
        confidences = [s.confidence for s in self.financials.signals]
        return sum(confidences) / len(confidences) if confidences else 0.0
