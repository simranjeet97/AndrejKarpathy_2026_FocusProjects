import os
from datetime import datetime
import docx
from ..models.domain import DiligenceReport, MarketData, CompetitorLandscape, FinancialProfile, LegalProfile

class ReportRenderer:
    """Class responsible for generating Markdown and PDF reports based on DiligenceReport domain data."""

    def __init__(self, output_dir: str):
        """Initialize renderer and ensure output directory exists."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def render_markdown(self, report: DiligenceReport) -> str:
        """Generate full Markdown report string."""
        badge = self._render_score_badge(report.investment_score)
        formatted_date = datetime.now().strftime("%B %d, %Y")
        
        toc = (
            "## Table of Contents\n"
            "1. [Executive Summary](#executive-summary)\n"
            "2. [Risk Assessment](#risk-assessment)\n"
            "3. [Market Opportunity](#market-opportunity)\n"
            "4. [Competitive Landscape](#competitive-landscape)\n"
            "5. [Financial Profile](#financial-profile)\n"
            "6. [Legal Standing](#legal-standing)\n"
            "7. [Sources & Bibliography](#sources-bibliography)\n"
            "8. [Diligence Pipeline Metadata](#diligence-pipeline-metadata)\n"
        )
        
        metadata_rows = []
        for r in report.agent_results:
            metadata_rows.append(f"| {r.agent_name} | {r.status} | {r.duration_ms} ms | {r.error or 'None'} |")
            
        metadata_table = (
            "| Agent Name | Status | Execution Time | Error Info |\n"
            "| --- | --- | --- | --- |\n" +
            "\n".join(metadata_rows)
        )
        
        # Gather sources
        all_sources = []
        for r in report.agent_results:
            if r.sources:
                all_sources.extend(r.sources)
        sources_list = "\n".join(f"- {src}" for src in sorted(list(set(all_sources))) if src.startswith("http"))
        if not sources_list:
            sources_list = "No external data source URLs recorded."

        return (
            f"# VentureMind Due Diligence Report: {report.startup_name}\n\n"
            f"**Generated On:** {formatted_date}\n"
            f"**Investment Recommendation:** {badge}\n\n"
            f"{toc}\n\n"
            "### Executive Summary\n\n"
            f"{report.summary}\n\n"
            "### Risk Assessment\n\n"
            f"{self._format_risk_flags(report.risk_flags)}\n\n"
            f"{self._render_market_section(report.market)}\n\n"
            f"{self._render_competitor_section(report.competitors)}\n\n"
            f"{self._render_financial_section(report.financials)}\n\n"
            f"{self._render_legal_section(report.legal)}\n\n"
            "### Sources & Bibliography\n\n"
            f"{sources_list}\n\n"
            "### Diligence Pipeline Metadata\n\n"
            f"{metadata_table}\n"
        )

    def render_pdf(self, report: DiligenceReport) -> str:
        """Generate DOCX file (representing PDF report layout format) and return its filepath."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = report.startup_name.lower().replace(' ', '_')
        filepath = os.path.join(self.output_dir, f"{safe_name}_{timestamp}.pdf")
        
        doc = docx.Document()
        doc.add_heading(f"VentureMind Due Diligence Report: {report.startup_name}", 0)
        
        badge = self._render_score_badge(report.investment_score)
        doc.add_paragraph(f"Generated On: {datetime.now().strftime('%B %d, %Y')}")
        doc.add_paragraph(f"Recommendation: {badge}")
        
        # Executive Summary
        doc.add_heading("Executive Summary", level=1)
        doc.add_paragraph(report.summary)
        
        # Risk Assessment
        doc.add_heading("Risk Assessment", level=1)
        for flag in report.risk_flags:
            doc.add_paragraph(f"• {flag}")
            
        # Market
        if report.market:
            doc.add_heading("Market Opportunity", level=1)
            doc.add_paragraph(f"CAGR: {report.market.cagr_pct:.1f}%")
            
            table = doc.add_table(rows=4, cols=2)
            table.cell(0, 0).text = "Metric"
            table.cell(0, 1).text = "Value (USD)"
            table.cell(1, 0).text = "TAM"
            table.cell(1, 1).text = f"${report.market.tam_usd:,.2f}"
            table.cell(2, 0).text = "SAM"
            table.cell(2, 1).text = f"${report.market.sam_usd:,.2f}"
            table.cell(3, 0).text = "SOM"
            table.cell(3, 1).text = f"${report.market.som_usd:,.2f}"
            
            doc.add_heading("Key Trends", level=2)
            for trend in report.market.key_trends:
                doc.add_paragraph(f"• {trend}")
        else:
            doc.add_heading("Market Opportunity", level=1)
            doc.add_paragraph("Data unavailable.")
                
        # Competitor
        if report.competitors:
            doc.add_heading("Competitive Landscape", level=1)
            doc.add_paragraph(f"Differentiation Score: {report.competitors.differentiation_score:.2f}")
            doc.add_paragraph(f"Positioning Summary: {report.competitors.positioning_summary}")
            
            table = doc.add_table(rows=1, cols=4)
            table.cell(0, 0).text = "Competitor"
            table.cell(0, 1).text = "Founded"
            table.cell(0, 2).text = "Funding"
            table.cell(0, 3).text = "Market Share"
            
            for c in report.competitors.competitors:
                row_cells = table.add_row().cells
                row_cells[0].text = c.name
                row_cells[1].text = str(c.founded_year)
                row_cells[2].text = f"${c.funding_usd:,.2f}" if c.funding_usd else "unknown"
                row_cells[3].text = f"{c.market_share_pct:.1f}%" if c.market_share_pct else "unknown"
        else:
            doc.add_heading("Competitive Landscape", level=1)
            doc.add_paragraph("Data unavailable.")
                
        # Financials
        if report.financials:
            doc.add_heading("Financial Profile", level=1)
            doc.add_paragraph(f"Estimated Burn: {report.financials.burn_rate_estimate}")
            doc.add_paragraph(f"Estimated Runway: {report.financials.runway_estimate}")
            
            doc.add_heading("Funding Rounds", level=2)
            for r in report.financials.funding_rounds:
                doc.add_paragraph(f"• {r.get('round')}: {r.get('amount_str')} ({r.get('date_str')})")
        else:
            doc.add_heading("Financial Profile", level=1)
            doc.add_paragraph("Data unavailable.")
                
        # Legal
        if report.legal:
            doc.add_heading("Legal Standing", level=1)
            doc.add_paragraph(f"Incorporation: {report.legal.incorporation_status}")
            doc.add_paragraph(f"Patents: {report.legal.patent_count}")
            doc.add_paragraph(f"Trademarks: {report.legal.trademark_count}")
            
            doc.add_heading("Legal & Compliance Flags", level=2)
            for f in report.legal.flags:
                doc.add_paragraph(f"• [{f.flag_type} - {f.severity}] {f.description}")
        else:
            doc.add_heading("Legal Standing", level=1)
            doc.add_paragraph("Data unavailable.")
                
        doc.save(filepath)
        return filepath

    def render_executive_summary(self, report: DiligenceReport) -> str:
        """Short 1-page Markdown summary."""
        badge = self._render_score_badge(report.investment_score)
        top_risks = "\n".join(f"- ⚠️ {r}" for r in report.risk_flags[:3]) if report.risk_flags else "No major risks identified."
        
        return (
            f"# Executive Summary: {report.startup_name}\n\n"
            f"**Investment Recommendation:** {badge}\n\n"
            f"{report.summary}\n\n"
            "#### Top Risk Flags\n"
            f"{top_risks}\n"
        )

    def _render_market_section(self, market: MarketData | None) -> str:
        """Render the market research and TAM/SAM/SOM findings section."""
        if not market:
            return "### Market Opportunity\nData unavailable.\n"
        
        table = (
            "| Metric | Value (USD) |\n"
            "| --- | --- |\n"
            f"| TAM (Total Addressable Market) | ${market.tam_usd:,.2f} |\n"
            f"| SAM (Serviceable Addressable Market) | ${market.sam_usd:,.2f} |\n"
            f"| SOM (Serviceable Obtainable Market) | ${market.som_usd:,.2f} |\n"
        )
        
        trends_list = "\n".join(f"- {trend}" for trend in market.key_trends)
        
        return (
            "### Market Opportunity\n\n"
            f"**Compound Annual Growth Rate (CAGR):** {market.cagr_pct:.1f}%\n\n"
            "#### Market Sizing\n"
            f"{table}\n\n"
            "#### Key Industry Trends\n"
            f"{trends_list}\n"
        )

    def _render_competitor_section(self, competitors: CompetitorLandscape | None) -> str:
        """Render the competitive landscape and positioning section."""
        if not competitors:
            return "### Competitive Landscape\nData unavailable.\n"
        
        comp_rows = []
        for c in competitors.competitors:
            funding = f"${c.funding_usd:,.2f}" if c.funding_usd else "unknown"
            share = f"{c.market_share_pct:.1f}%" if c.market_share_pct else "unknown"
            comp_rows.append(f"| {c.name} | {c.founded_year} | {funding} | {share} |")
            
        table = (
            "| Competitor Name | Founded Year | Total Funding | Market Share |\n"
            "| --- | --- | --- | --- |\n" +
            "\n".join(comp_rows)
        )
        
        return (
            "### Competitive Landscape\n\n"
            f"**Differentiation Score:** {competitors.differentiation_score:.2f} / 1.00\n\n"
            f"**Positioning Summary:**\n{competitors.positioning_summary}\n\n"
            "#### Direct Competitor Matrix\n"
            f"{table}\n"
        )

    def _render_financial_section(self, financials: FinancialProfile | None) -> str:
        """Render the financial standing and metrics overview section."""
        if not financials:
            return "### Financial Profile\nData unavailable.\n"
        
        round_rows = []
        for r in financials.funding_rounds:
            round_rows.append(f"- **{r.get('round', 'Unknown')}**: {r.get('amount_str', 'unknown')} on {r.get('date_str', 'unknown')} (Source: {r.get('source', 'unknown')})")
            
        rounds_timeline = "\n".join(round_rows) if round_rows else "No funding rounds recorded."
        
        signals_rows = []
        for s in financials.signals:
            signals_rows.append(f"| {s.metric_name} | {s.value} | {s.period} | {s.source} | {s.confidence:.2f} |")
            
        signals_table = (
            "| Metric | Value | Period | Source | Confidence |\n"
            "| --- | --- | --- | --- | --- |\n" +
            "\n".join(signals_rows)
        )
        
        return (
            "### Financial Profile\n\n"
            f"**Estimated Burn Rate:** {financials.burn_rate_estimate}\n"
            f"**Estimated Runway:** {financials.runway_estimate}\n\n"
            "#### Financial Signals & Metrics\n"
            f"{signals_table}\n\n"
            "#### Funding Rounds Timeline\n"
            f"{rounds_timeline}\n"
        )

    def _render_legal_section(self, legal: LegalProfile | None) -> str:
        """Render the incorporation, IP, litigation, and regulatory flags section."""
        if not legal:
            return "### Legal Standing\nData unavailable.\n"
        
        flag_rows = []
        for f in legal.flags:
            flag_rows.append(f"| {f.flag_type} | {f.severity} | {f.description} |")
            
        flags_table = (
            "| Issue / Flag Type | Severity | Description |\n"
            "| --- | --- | --- |\n" +
            "\n".join(flag_rows)
        ) if flag_rows else "No active legal or regulatory flags identified."
        
        return (
            "### Legal Standing\n\n"
            f"**Incorporation Status:** {legal.incorporation_status}\n"
            f"**Patent Count Estimate:** {legal.patent_count}\n"
            f"**Trademark Count Estimate:** {legal.trademark_count}\n\n"
            "#### Legal & Compliance Flags\n"
            f"{flags_table}\n"
        )

    def _render_score_badge(self, score: float) -> str:
        """Returns visual score badge string like '⭐ 7.2/10 — STRONG OPPORTUNITY'"""
        if 0.0 <= score < 3.0:
            return f"🔴 {score:.1f}/10 — NOT INVESTABLE"
        elif 3.0 <= score < 5.0:
            return f"🟡 {score:.1f}/10 — HIGH RISK"
        elif 5.0 <= score < 7.0:
            return f"🟠 {score:.1f}/10 — MODERATE OPPORTUNITY"
        elif 7.0 <= score < 9.0:
            return f"🟢 {score:.1f}/10 — STRONG OPPORTUNITY"
        else:
            return f"⭐ {score:.1f}/10 — EXCEPTIONAL OPPORTUNITY"

    def _format_risk_flags(self, flags: list[str]) -> str:
        """Format a list of risk flags into a structured Markdown block."""
        if not flags:
            return "No significant risk flags identified."
        return "\n".join(f"- ⚠️ {flag}" for flag in flags)
