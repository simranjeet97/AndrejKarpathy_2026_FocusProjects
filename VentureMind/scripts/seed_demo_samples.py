import sqlite3
import json
import uuid
from datetime import datetime, timezone

DB_PATH = "data/reports/reports.db"

DEMO_DATA = [
    {
        "startup_name": "Linear",
        "investment_score": 8.6,
        "summary": "Linear provides a purpose-built issue tracking and product management platform tailored for high-growth engineering teams. It demonstrates best-in-class product execution, exceptional speed, and keyboard-first workflows, building strong developer love and word-of-mouth adoption. While competing against enterprise giants like Atlassian Jira and Asana, Linear's lightweight offline-first sync engine and developer ergonomics offer a durable competitive moat in the tech ecosystem.",
        "risk_flags": [
            "Heavy concentration in tech startups & scaleups",
            "Atlassian enterprise contract bundling pressure"
        ],
        "market": {
            "tam_usd": 12400000000.0,
            "sam_usd": 4200000000.0,
            "som_usd": 850000000.0,
            "cagr_pct": 14.8,
            "key_trends": [
                "Developer productivity and developer experience (DevEx) prioritization",
                "Migration away from bloated legacy enterprise suites (Jira)",
                "AI-assisted issue triage and PR correlation automation"
            ],
            "sources": [
                "Gartner DevSecOps & Agile Tools Market Guide",
                "IDC Worldwide Application Lifecycle Management Forecast",
                "Stack Overflow Developer Survey"
            ]
        },
        "competitors": {
            "startup_name": "Linear",
            "differentiation_score": 8.7,
            "positioning_summary": "Superior UI latency (<50ms interaction time), real-time sync engine, and native Git/GitHub integration give Linear high defensibility among developers.",
            "competitors": [
                {
                    "name": "Jira (Atlassian)",
                    "website": "https://atlassian.com/software/jira",
                    "founded_year": 2002,
                    "funding_usd": 1500000000.0,
                    "market_share_pct": 42.5,
                    "strengths": ["Enterprise compliance", "Broad plugin marketplace", "Established sales channels"],
                    "weaknesses": ["Slow UI", "Complex administrative configuration", "High developer frustration"]
                },
                {
                    "name": "Asana",
                    "website": "https://asana.com",
                    "founded_year": 2008,
                    "funding_usd": 453000000.0,
                    "market_share_pct": 16.0,
                    "strengths": ["Cross-functional marketing & ops adoption", "Visual timeline views"],
                    "weaknesses": ["Lacks deep Git / software engineering native primitives"]
                },
                {
                    "name": "Height",
                    "website": "https://height.app",
                    "founded_year": 2020,
                    "funding_usd": 18000000.0,
                    "market_share_pct": 2.1,
                    "strengths": ["Autonomous AI agent task updates", "Spreadsheet-like flexibility"],
                    "weaknesses": ["Smaller market brand awareness", "Early-stage enterprise controls"]
                }
            ]
        },
        "financials": {
            "startup_name": "Linear",
            "burn_rate_estimate": "$420k / month",
            "runway_estimate": "38+ months (Near Break-even)",
            "funding_rounds": [
                {"round": "Seed", "amount": 4200000, "date": "2019-11"},
                {"round": "Series A", "amount": 13000000, "date": "2020-12"},
                {"round": "Series B", "amount": 35000000, "date": "2023-09"}
            ],
            "signals": [
                {"metric_name": "Estimated ARR", "value": "$35,000,000+", "period": "2025", "source": "Sacra Research", "confidence": 0.88},
                {"metric_name": "Total Capital Raised", "value": "$52,200,000", "period": "Total", "source": "SEC Form D Filings", "confidence": 0.98},
                {"metric_name": "Implied Valuation", "value": "$400,000,000", "period": "Series B", "source": "PitchBook", "confidence": 0.92},
                {"metric_name": "Capital Efficiency (Burn Multiple)", "value": "0.35x (Top Decile)", "period": "2024", "source": "Venture Benchmarks", "confidence": 0.85}
            ]
        },
        "legal": {
            "startup_name": "Linear",
            "incorporation_status": "Delaware C-Corporation (Verified active)",
            "patent_count": 2,
            "trademark_count": 4,
            "flags": []
        }
    },
    {
        "startup_name": "Retool",
        "investment_score": 8.3,
        "summary": "Retool is the category-defining low-code development platform for internal enterprise tools, portals, and workflow apps. With deep database connectors (Postgres, GraphQL, REST, Snowflake), granular role-based access control (RBAC), and full code extensibility (JavaScript/Python), Retool has captured over 75% of Fortune 500 tech teams. Revenue retention is exceptional, though expansion into consumer-facing workflows remains a key frontier.",
        "risk_flags": [
            "Internal tools pricing ceiling per seat",
            "Open-source alternatives (Appsmith, ToolJet) targeting SMBs"
        ],
        "market": {
            "tam_usd": 28500000000.0,
            "sam_usd": 9200000000.0,
            "som_usd": 2100000000.0,
            "cagr_pct": 22.3,
            "key_trends": [
                "Democratization of internal tool building for operations engineers",
                "Integration of local AI workflows & LLM components inside business dashboards",
                "Enterprise security compliance shift towards self-hosted VPC instances"
            ],
            "sources": [
                "Gartner Magic Quadrant for Enterprise Low-Code Application Platforms",
                "Forrester Wave: Low-Code Platforms for Business Developers",
                "SEC Filings & TechCrunch Venture Reports"
            ]
        },
        "competitors": {
            "startup_name": "Retool",
            "differentiation_score": 8.4,
            "positioning_summary": "Extensive pre-built component library, robust on-premise VPC deployment options, and rich custom script hooks make Retool the standard choice for enterprise engineering teams.",
            "competitors": [
                {
                    "name": "Appsmith",
                    "website": "https://appsmith.com",
                    "founded_year": 2019,
                    "funding_usd": 51500000.0,
                    "market_share_pct": 8.5,
                    "strengths": ["Fully open-source core", "Self-hosting community adoption"],
                    "weaknesses": ["Fewer native enterprise governance controls"]
                },
                {
                    "name": "Microsoft PowerApps",
                    "website": "https://powerapps.microsoft.com",
                    "founded_year": 2015,
                    "funding_usd": 0.0,
                    "market_share_pct": 34.0,
                    "strengths": ["Office 365 bundled distribution", "Citizen-developer friendly"],
                    "weaknesses": ["Poor developer experience for pro-code software engineers"]
                },
                {
                    "name": "Superblocks",
                    "website": "https://superblocks.com",
                    "founded_year": 2021,
                    "funding_usd": 37000000.0,
                    "market_share_pct": 4.2,
                    "strengths": ["Backend orchestration focus", "Native scheduled jobs"],
                    "weaknesses": ["Smaller template ecosystem than Retool"]
                }
            ]
        },
        "financials": {
            "startup_name": "Retool",
            "burn_rate_estimate": "$1,150,000 / month",
            "runway_estimate": "45+ months (High cash reserves)",
            "funding_rounds": [
                {"round": "Seed", "amount": 2500000, "date": "2017-10"},
                {"round": "Series A", "amount": 25000000, "date": "2019-10"},
                {"round": "Series B", "amount": 50000000, "date": "2020-10"},
                {"round": "Series C", "amount": 45000000, "date": "2021-12"}
            ],
            "signals": [
                {"metric_name": "Estimated ARR", "value": "$95,000,000+", "period": "2025", "source": "Bloomberg Beta & Forbes", "confidence": 0.90},
                {"metric_name": "Total Capital Raised", "value": "$135,000,000", "period": "Total", "source": "SEC Form D Filings", "confidence": 0.99},
                {"metric_name": "Last Round Valuation", "value": "$3,200,000,000", "period": "Series C", "source": "Sequoia Capital Disclosures", "confidence": 0.95},
                {"metric_name": "Net Revenue Retention (NRR)", "value": "130%+", "period": "Enterprise Tier", "source": "Financial Benchmarks", "confidence": 0.86}
            ]
        },
        "legal": {
            "startup_name": "Retool",
            "incorporation_status": "Delaware C-Corporation (San Francisco, CA)",
            "patent_count": 3,
            "trademark_count": 6,
            "flags": []
        }
    },
    {
        "startup_name": "Supabase",
        "investment_score": 8.7,
        "summary": "Supabase has established itself as the leading open-source alternative to Google Firebase, offering a modular backend platform built directly on PostgreSQL. It packages Postgres with real-time subscriptions, Row Level Security (RLS), auto-generated REST/GraphQL APIs, Auth, Storage, and Edge Functions. Its open-source core has driven viral bottom-up developer adoption across 1M+ registered databases.",
        "risk_flags": [
            "Open-source community monetization conversion rate",
            "Cloud hosting margin pressure from hyperscalers (AWS/GCP)"
        ],
        "market": {
            "tam_usd": 34000000000.0,
            "sam_usd": 11500000000.0,
            "som_usd": 2400000000.0,
            "cagr_pct": 19.5,
            "key_trends": [
                "PostgreSQL standardization across cloud native applications",
                "Preference for open standards avoiding proprietary BaaS lock-in (Firebase)",
                "Vector database extensions (pgvector) fueling GenAI backends"
            ],
            "sources": [
                "DB-Engines Ranking & DBMS Popularity Trends",
                "Redpoint Ventures Cloud Infrastructure Index",
                "GitHub State of the Octoverse"
            ]
        },
        "competitors": {
            "startup_name": "Supabase",
            "differentiation_score": 8.9,
            "positioning_summary": "No proprietary lock-in, native SQL & pgvector capabilities, and full local Docker development environment make Supabase the go-to backend for modern web and AI founders.",
            "competitors": [
                {
                    "name": "Firebase (Google)",
                    "website": "https://firebase.google.com",
                    "founded_year": 2011,
                    "funding_usd": 0.0,
                    "market_share_pct": 46.0,
                    "strengths": ["Massive mobile SDK adoption", "GCP cloud ecosystem integration"],
                    "weaknesses": ["Proprietary NoSQL query limits", "Vendor lock-in", "High runaway bill risks"]
                },
                {
                    "name": "AWS Amplify",
                    "website": "https://aws.amazon.com/amplify",
                    "founded_year": 2017,
                    "funding_usd": 0.0,
                    "market_share_pct": 21.0,
                    "strengths": ["Deep AWS IAM integration", "Enterprise SLA"],
                    "weaknesses": ["Complex CloudFormation architecture", "Fragmented local testing"]
                },
                {
                    "name": "Appwrite",
                    "website": "https://appwrite.io",
                    "founded_year": 2019,
                    "funding_usd": 37000000.0,
                    "market_share_pct": 5.0,
                    "strengths": ["Clean REST endpoints", "Self-hosting simplicity"],
                    "weaknesses": ["Smaller ecosystem than Postgres-backed Supabase"]
                }
            ]
        },
        "financials": {
            "startup_name": "Supabase",
            "burn_rate_estimate": "$850,000 / month",
            "runway_estimate": "32 months",
            "funding_rounds": [
                {"round": "Seed", "amount": 6000000, "date": "2020-12"},
                {"round": "Series A", "amount": 30000000, "date": "2021-09"},
                {"round": "Series B", "amount": 80000000, "date": "2022-05"}
            ],
            "signals": [
                {"metric_name": "Estimated ARR", "value": "$40,000,000+", "period": "2025", "source": "Sacra & The Information", "confidence": 0.87},
                {"metric_name": "Total Capital Raised", "value": "$116,000,000", "period": "Total", "source": "SEC Form D Filings", "confidence": 0.99},
                {"metric_name": "Post-Money Valuation", "value": "$1,000,000,000+", "period": "Series B", "source": "Coatue & Felicis Ventures", "confidence": 0.94},
                {"metric_name": "Active Managed DBs", "value": "1,000,000+ instances", "period": "2025", "source": "Supabase Metrics", "confidence": 0.96}
            ]
        },
        "legal": {
            "startup_name": "Supabase",
            "incorporation_status": "Delaware C-Corporation (San Francisco / Singapore)",
            "patent_count": 1,
            "trademark_count": 5,
            "flags": []
        }
    },
    {
        "startup_name": "Stripe",
        "investment_score": 9.4,
        "summary": "Stripe is the foundational financial infrastructure platform for the global internet economy. Powering millions of businesses from early startups to Amazon, Uber, and Salesforce, Stripe processes over $1 Trillion in total payment volume (TPV) annually. With expanding moats in Tax, Radar (fraud detection), Billing, and Treasury, Stripe is solidly profitable and generates billions in annual free cash flow.",
        "risk_flags": [
            "Regulatory scrutiny on interchange fees and cross-border transfers",
            "High enterprise negotiation power from mega-volume merchants (Amazon, Shopify)"
        ],
        "market": {
            "tam_usd": 165000000000.0,
            "sam_usd": 68000000000.0,
            "som_usd": 18500000000.0,
            "cagr_pct": 16.2,
            "key_trends": [
                "E-commerce & SaaS global recurring billing dominance",
                "Consolidation of payment processing, fraud AI, and tax compliance into single API",
                "Embedded financial services and corporate card issuance (Stripe Issuing)"
            ],
            "sources": [
                "Bank for International Settlements (BIS) Payments Data",
                "McKinsey Global Payments Report 2025",
                "SEC Public Regulatory Disclosures & Stripe Annual Letters"
            ]
        },
        "competitors": {
            "startup_name": "Stripe",
            "differentiation_score": 9.5,
            "positioning_summary": "99.999% reliability SLA, unrivaled 7-line developer integration, and comprehensive international payment method acceptance in 135+ currencies provide an insurmountable moat.",
            "competitors": [
                {
                    "name": "Adyen",
                    "website": "https://adyen.com",
                    "founded_year": 2006,
                    "funding_usd": 0.0,
                    "market_share_pct": 24.0,
                    "strengths": ["Unified omnichannel POS & online settlement", "Direct banking acquiring licenses in EU/US"],
                    "weaknesses": ["Less developer-centric for self-serve SMBs"]
                },
                {
                    "name": "PayPal / Braintree",
                    "website": "https://paypal.com",
                    "founded_year": 1998,
                    "funding_usd": 0.0,
                    "market_share_pct": 28.0,
                    "strengths": ["Consumer brand recognition (PayPal wallet)", "Global presence"],
                    "weaknesses": ["Fragmented legacy APIs", "Slower innovation velocity"]
                },
                {
                    "name": "Checkout.com",
                    "website": "https://checkout.com",
                    "founded_year": 2012,
                    "funding_usd": 1800000000.0,
                    "market_share_pct": 9.5,
                    "strengths": ["Competitive processing fees in EMEA & APAC"],
                    "weaknesses": ["Smaller developer software ecosystem than Stripe"]
                }
            ]
        },
        "financials": {
            "startup_name": "Stripe",
            "burn_rate_estimate": "Net Cash-Flow Positive (+$2.5B+ FCF/yr)",
            "runway_estimate": "Infinite (>60 months, $4B+ Cash on Balance Sheet)",
            "funding_rounds": [
                {"round": "Series A - H Rounds", "amount": 2200000000, "date": "2011-2021"},
                {"round": "Employee Liquidity Round", "amount": 6500000000, "date": "2023-03"}
            ],
            "signals": [
                {"metric_name": "Total Payment Volume (TPV)", "value": "$1,000,000,000,000+ ($1T+)", "period": "Annual", "source": "Stripe Annual Letter", "confidence": 0.99},
                {"metric_name": "Net Revenue (GAAP)", "value": "$4,200,000,000+ ($4.2B)", "period": "2024", "source": "Wall Street Journal Audited Leaks", "confidence": 0.95},
                {"metric_name": "Current Private Valuation", "value": "$70,000,000,000 ($70B)", "period": "2024 Tender Offer", "source": "Goldman Sachs & Sequoia", "confidence": 0.98},
                {"metric_name": "EBITDA Margin", "value": "~30% Adjusted EBITDA", "period": "2024", "source": "Financial Disclosures", "confidence": 0.92}
            ]
        },
        "legal": {
            "startup_name": "Stripe",
            "incorporation_status": "Delaware C-Corporation (South San Francisco & Dublin)",
            "patent_count": 52,
            "trademark_count": 38,
            "flags": []
        }
    },
    {
        "startup_name": "Datadog",
        "investment_score": 9.1,
        "summary": "Datadog (NASDAQ: DDOG) is the gold standard cloud observability, security, and telemetry monitoring platform. Its unified agent ingests metrics, logs, and APM traces across multi-cloud environments (AWS, Azure, GCP, on-premise Kubernetes). Demonstrating stellar 115%+ net retention and strong operating leverage, Datadog continues expanding its product portfolio into cloud security posture management (CSPM) and LLM application observability.",
        "risk_flags": [
            "Customer cloud spending optimization headwinds during macro slowdowns",
            "OpenTelemetry (OTel) standard reducing proprietary agent lock-in"
        ],
        "market": {
            "tam_usd": 62000000000.0,
            "sam_usd": 24000000000.0,
            "som_usd": 6500000000.0,
            "cagr_pct": 18.4,
            "key_trends": [
                "Full-stack observability convergence (Metrics + Traces + Logs + Security)",
                "AI workload telemetry monitoring (LLM latency, token cost, prompt drift)",
                "Shift from fragmented point tools to single-pane-of-glass platforms"
            ],
            "sources": [
                "Gartner Magic Quadrant for APM and Observability (Leader)",
                "SEC Form 10-K Annual Filings (NASDAQ: DDOG)",
                "IDC Worldwide Cloud IT Operations Software Market Shares"
            ]
        },
        "competitors": {
            "startup_name": "Datadog",
            "differentiation_score": 9.1,
            "positioning_summary": "Single-agent architecture, 750+ turnkey out-of-the-box integrations, and high operational velocity maintain Datadog's market leadership against legacy enterprise suites.",
            "competitors": [
                {
                    "name": "Dynatrace",
                    "website": "https://dynatrace.com",
                    "founded_year": 2005,
                    "funding_usd": 0.0,
                    "market_share_pct": 22.0,
                    "strengths": ["Enterprise mainframe & heavy APM telemetry", "Davis AI root cause analysis"],
                    "weaknesses": ["Steeper learning curve", "Slower modern cloud-native developer adoption"]
                },
                {
                    "name": "New Relic",
                    "website": "https://newrelic.com",
                    "founded_year": 2008,
                    "funding_usd": 0.0,
                    "market_share_pct": 18.0,
                    "strengths": ["Established APM brand", "Consumption-based pricing"],
                    "weaknesses": ["Historical platform fragmentation prior to private equity take-private"]
                },
                {
                    "name": "Grafana Labs",
                    "website": "https://grafana.com",
                    "founded_year": 2014,
                    "funding_usd": 540000000.0,
                    "market_share_pct": 14.5,
                    "strengths": ["Massive open-source dashboard visualization love (Prometheus)"],
                    "weaknesses": ["Requires higher self-management and infrastructure setup"]
                }
            ]
        },
        "financials": {
            "startup_name": "Datadog",
            "burn_rate_estimate": "Net Cash-Flow Positive (+$650M+ FCF/year)",
            "runway_estimate": "Infinite (Publicly traded, $2.8B Cash & Equivalents)",
            "funding_rounds": [
                {"round": "Series A - D Venture Rounds", "amount": 148000000, "date": "2011-2016"},
                {"round": "Initial Public Offering (IPO)", "amount": 648000000, "date": "2019-09"}
            ],
            "signals": [
                {"metric_name": "Annual Revenue (TTM)", "value": "$2,600,000,000+ ($2.6B)", "period": "FY2024", "source": "SEC Form 10-K", "confidence": 1.0},
                {"metric_name": "Free Cash Flow (TTM)", "value": "$700,000,000+ ($700M)", "period": "FY2024", "source": "SEC Form 10-K", "confidence": 1.0},
                {"metric_name": "Market Capitalization", "value": "~$42,000,000,000 ($42B)", "period": "Public Market", "source": "NASDAQ: DDOG", "confidence": 1.0},
                {"metric_name": "Gross Margin (Non-GAAP)", "value": "81.5%", "period": "FY2024", "source": "Shareholder Letter", "confidence": 1.0}
            ]
        },
        "legal": {
            "startup_name": "Datadog",
            "incorporation_status": "Delaware C-Corporation (New York, NY)",
            "patent_count": 26,
            "trademark_count": 20,
            "flags": []
        }
    },
    {
        "startup_name": "Postman",
        "investment_score": 8.5,
        "summary": "Postman is the universal standard API collaboration and lifecycle platform, utilized by over 35 Million developers across 500,000 companies globally. Starting as an HTTP request testing tool, Postman has expanded into API documentation, mock servers, automated contract testing, security governance, and enterprise API workspaces. With deeply entrenched network effects in API specifications, it forms a central hub for microservice engineering.",
        "risk_flags": [
            "Lightweight open-source CLI clients (Bruno, HTTPie, Hoppscotch) attacking desktop foot-print",
            "Monetization friction moving individual developers to paid enterprise tiers"
        ],
        "market": {
            "tam_usd": 18200000000.0,
            "sam_usd": 6100000000.0,
            "som_usd": 1400000000.0,
            "cagr_pct": 21.0,
            "key_trends": [
                "Explosion of microservices and public API ecosystem connections",
                "Shift to API-first development workflows prior to code writing",
                "Automated API contract testing and LLM agent tool call validation"
            ],
            "sources": [
                "Postman State of the API Report 2025",
                "IDC Worldwide API Management Software Forecast",
                "Gartner API Testing Market Analysis"
            ]
        },
        "competitors": {
            "startup_name": "Postman",
            "differentiation_score": 8.6,
            "positioning_summary": "Massive 35M+ developer network effect, universal Postman Collection format (.json), and public API network create a high switching barrier.",
            "competitors": [
                {
                    "name": "Insomnia (Kong)",
                    "website": "https://insomnia.rest",
                    "founded_year": 2016,
                    "funding_usd": 0.0,
                    "market_share_pct": 14.0,
                    "strengths": ["Local-first storage", "Clean GraphQL debugging", "Kong Gateway integration"],
                    "weaknesses": ["Smaller public API sharing directory than Postman"]
                },
                {
                    "name": "Swagger / SmartBear",
                    "website": "https://swagger.io",
                    "founded_year": 2011,
                    "funding_usd": 0.0,
                    "market_share_pct": 22.0,
                    "strengths": ["OpenAPI specification governance", "Code generation tooling"],
                    "weaknesses": ["Less collaborative team workspace features"]
                },
                {
                    "name": "Hoppscotch",
                    "website": "https://hoppscotch.io",
                    "founded_year": 2019,
                    "funding_usd": 3000000.0,
                    "market_share_pct": 5.5,
                    "strengths": ["Web-based instant client", "Fast open-source lightweight footprint"],
                    "weaknesses": ["Early-stage enterprise compliance and workspace tooling"]
                }
            ]
        },
        "financials": {
            "startup_name": "Postman",
            "burn_rate_estimate": "$900,000 / month",
            "runway_estimate": "40+ months",
            "funding_rounds": [
                {"round": "Seed", "amount": 1000000, "date": "2015-05"},
                {"round": "Series A", "amount": 7000000, "date": "2016-10"},
                {"round": "Series B", "amount": 50000000, "date": "2019-06"},
                {"round": "Series C", "amount": 150000000, "date": "2020-06"},
                {"round": "Series D", "amount": 225000000, "date": "2021-08"}
            ],
            "signals": [
                {"metric_name": "Estimated ARR", "value": "$120,000,000+", "period": "2025", "source": "Forbes Cloud 100", "confidence": 0.91},
                {"metric_name": "Total Capital Raised", "value": "$433,000,000", "period": "Total", "source": "SEC Form D Filings", "confidence": 0.99},
                {"metric_name": "Last Valuation", "value": "$5,600,000,000 ($5.6B)", "period": "Series D", "source": "Insight Partners Disclosures", "confidence": 0.96},
                {"metric_name": "Registered Developers", "value": "35,000,000+ users", "period": "2025", "source": "Postman Official Platform Metrics", "confidence": 0.98}
            ]
        },
        "legal": {
            "startup_name": "Postman",
            "incorporation_status": "Delaware C-Corporation (San Francisco, CA & Bangalore)",
            "patent_count": 4,
            "trademark_count": 10,
            "flags": []
        }
    }
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Clear old records to avoid dirty data
    c.execute("DELETE FROM diligence_reports")
    c.execute("DELETE FROM agent_results")

    now = datetime.now(timezone.utc).isoformat()

    for item in DEMO_DATA:
        report_id = str(uuid.uuid4())
        name = item["startup_name"]
        score = item["investment_score"]

        # Synthetic agent telemetry
        agent_results = [
            {
                "agent_name": "market_research",
                "status": "SUCCESS",
                "data": item["market"],
                "error": None,
                "duration_ms": 3210,
                "sources": item["market"]["sources"]
            },
            {
                "agent_name": "competitor",
                "status": "SUCCESS",
                "data": item["competitors"],
                "error": None,
                "duration_ms": 4120,
                "sources": ["Company Registry", "G2 Crowd", "Crunchbase Intelligence"]
            },
            {
                "agent_name": "financial",
                "status": "SUCCESS",
                "data": item["financials"],
                "error": None,
                "duration_ms": 5890,
                "sources": ["SEC Form D Filings", "PitchBook Venture Index", "Company Disclosures"]
            },
            {
                "agent_name": "legal",
                "status": "SUCCESS",
                "data": item["legal"],
                "error": None,
                "duration_ms": 2840,
                "sources": ["USPTO Patent Database", "Delaware Division of Corporations", "Trademark Electronic Search System"]
            },
            {
                "agent_name": "summarization",
                "status": "SUCCESS",
                "data": {
                    "summary": item["summary"],
                    "investment_score": score,
                    "risk_flags": item["risk_flags"]
                },
                "error": None,
                "duration_ms": 6430,
                "sources": ["Orchestrator Synthesis Matrix"]
            }
        ]

        full_report = {
            "startup_name": name,
            "generated_at": now,
            "market": item["market"],
            "competitors": item["competitors"],
            "financials": item["financials"],
            "legal": item["legal"],
            "summary": item["summary"],
            "investment_score": score,
            "risk_flags": item["risk_flags"],
            "agent_results": agent_results
        }

        report_json = json.dumps(full_report)

        c.execute(
            """
            INSERT INTO diligence_reports (id, startup_name, generated_at, investment_score, report_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, name, now, score, report_json)
        )

        for ar in agent_results:
            ar_id = str(uuid.uuid4())
            c.execute(
                """
                INSERT INTO agent_results (id, startup_name, agent_name, status, duration_ms, created_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ar_id, name, ar["agent_name"], ar["status"], ar["duration_ms"], now, json.dumps(ar))
            )

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(DEMO_DATA)} high-fidelity diligence reports into {DB_PATH}")

if __name__ == "__main__":
    seed()
