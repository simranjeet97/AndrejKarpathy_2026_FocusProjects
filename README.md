# AI Systems Engineering Project Roadmap by Andrej Karpathy

A curated set of projects designed to help you master the **boring things that actually compound** in modern AI systems:

**Context Engineering • Tool Design • Agent Orchestration • Eval Discipline • Reliability Engineering • MCP • Harness Mindset**

These projects move you from building flashy demos to building production-grade AI systems that companies actually need.

---

# 1. CodeLens AI — Autonomous PR Review Agent

## Overview

Build an AI-powered GitHub pull request reviewer that analyzes code changes and provides meaningful feedback by understanding changed files, coding standards documentation, previous pull request examples, architecture documents, and Jira ticket context.

The system should intelligently decide what information matters for a specific PR instead of dumping everything into the prompt.

## Tech Stack

GitHub API, OpenAI API or Anthropic API, Pinecone or Weaviate, Redis, Jira API, vector databases, prompt orchestration frameworks.

## Impact

This project teaches you how real-world context engineering works by forcing you to solve problems around context packing, retrieval ranking, prompt layering, short-term memory, long-term memory, and reducing irrelevant token usage.

## Key Learning

The advanced challenge is building automatic context compression where the system identifies only the most relevant files from hundreds of changed files.

---

# 2. QueryForge — Multi-Tool Research Agent

## Overview

Build an intelligent agent that can query PostgreSQL databases, search the web, summarize PDFs, call internal APIs, and generate charts.

A user should be able to ask something like: *“Find our highest churn customer segment and compare it with industry trends.”*

The agent must decide which tools to use and in what sequence.

## Tech Stack

PostgreSQL, Stripe API, Notion API, Apache Airflow, OpenAI function calling, chart generation libraries.

## Impact

This project teaches tool design by helping you understand schema design, deterministic outputs, permission boundaries, and preventing tool misuse.

## Key Learning

You’ll learn why narrowly scoped tools outperform generic tools. Designing `get_monthly_churn_by_segment()` is far safer than allowing unrestricted SQL execution.

---

# 3. VentureMind — Startup Due Diligence Multi-Agent System

## Overview

Build a multi-agent system that analyzes startups before investment.

The system should include a market research agent, competitor analysis agent, financial analysis agent, legal analysis agent, and summarization agent.

A user provides a startup name and receives a full due diligence report.

## Tech Stack

CrewAI, LangChain, Microsoft AutoGen, financial APIs, legal document parsing tools.

## Impact

This project teaches task decomposition, parallel execution, dependency management, agent handoffs, and workflow orchestration.

## Key Learning

You’ll understand how to coordinate multiple specialized agents instead of trying to make one agent do everything.

---

# 4. EvalOps — LLM Regression Testing Platform

## Overview

Build a testing platform that automatically evaluates prompts, workflows, and model changes.

Every time something changes, the platform should run benchmark tasks, compare outputs, detect regressions, score hallucination rates, and track latency and cost.

Think of this as CI/CD for prompts and AI agents.

## Tech Stack

Weights & Biases, LangSmith, Arize AI, OpenAI evaluation pipelines, experiment tracking tools.

## Impact

This project teaches evaluation discipline and helps you build systems that improve reliably over time.

## Key Learning

You’ll learn how golden datasets, LLM-as-a-judge systems, pairwise comparisons, and human feedback loops improve production AI systems.

---

# 5. FailSafe AI — Autonomous Customer Support Agent

## Overview

Build a customer support agent that handles refund requests, policy lookups, payment API calls, and customer interactions.

The system should retry failures, use fallback models, manage timeouts, escalate uncertain situations to humans, and maintain observability.

## Tech Stack

Stripe API, customer support APIs, monitoring tools, fallback model orchestration systems.

## Impact

This project teaches reliability engineering, which is often ignored in AI demos.

## Key Learning

You’ll learn that making an AI system resilient is often more valuable than making it more intelligent.

---

# 6. BridgeProtocol — Build Your Own MCP Server

## Overview

Build an MCP server that connects external platforms such as Google Calendar, Gmail, Notion, Slack, and GitHub.

Then integrate it with clients like Claude, OpenAI tools, Cursor, and Windsurf.

## Tech Stack

Model Context Protocol, OAuth authentication systems, API integrations, backend infrastructure.

## Impact

This project teaches protocol design, authentication handling, permission management, tool schemas, and state management.

## Key Learning

You’ll understand why MCP is becoming the integration layer for AI systems.

---

# 7. AutoForge — Autonomous Software Engineering Sandbox

## Overview

Build an autonomous coding agent that receives GitHub issues, writes code, runs tests, validates outputs, opens pull requests, and rolls back failures.

This project focuses heavily on building the surrounding infrastructure required to make autonomous coding reliable.

## Tech Stack

GitHub API, Docker sandboxes, CI/CD systems, automated testing frameworks, logging systems.

## Impact

This project teaches harness engineering through sandboxing, execution isolation, verification loops, artifact logging, and recovery systems.

## Key Learning

You’ll learn that the surrounding infrastructure often matters more than the model itself.

---

# Ultimate Project: SentinelOps — AI DevOps Incident Response Agent

## Overview

Build an AI system that detects outages, pulls logs, queries metrics, searches runbooks, coordinates multiple agents, calls infrastructure tools, evaluates solution quality, escalates uncertainty, and maintains audit logs.

This project combines everything from the previous projects into one production-grade AI system.

## Tech Stack

Monitoring platforms, logging systems, cloud APIs, orchestration frameworks, MCP integrations, evaluation pipelines.

## Impact

This project teaches full-stack AI systems engineering and mirrors where enterprise AI infrastructure is heading.

## Key Learning

This single project covers context engineering, tool design, orchestration, evaluations, reliability engineering, MCP integration, and harness engineering.

---

# Recommended Learning Path

Start with CodeLens AI, move to QueryForge, then build VentureMind, followed by EvalOps, BridgeProtocol, AutoForge, and finally SentinelOps.

This progression takes you from **“I can build AI demos”** to **“I can build production-grade autonomous systems.”**

That’s where the real moat is.
