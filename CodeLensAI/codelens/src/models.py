from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

class SourceType(str, Enum):
    """Source type of the document chunk."""
    ARCH_DOC = "ARCH_DOC"
    STANDARD = "STANDARD"
    PR_EXAMPLE = "PR_EXAMPLE"
    CODE = "CODE"

class IssueSeverity(str, Enum):
    """Severity of the review issue."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class IssueCategory(str, Enum):
    """Category of the review issue."""
    SECURITY = "SECURITY"
    PERF = "PERF"
    STYLE = "STYLE"
    LOGIC = "LOGIC"
    TEST = "TEST"

class ApprovalStatus(str, Enum):
    """Approval status of the PR review."""
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"

class FileDiff(BaseModel):
    """Represents a file difference inside a PR."""
    model_config = ConfigDict(use_enum_values=True)

    path: str = Field(..., description="File path within the repository", examples=["src/main.py"])
    status: str = Field(..., description="Status of the file (e.g. modified, added, deleted)", examples=["modified"])
    additions: int = Field(..., description="Number of lines added", examples=[12])
    deletions: int = Field(..., description="Number of lines deleted", examples=[3])
    patch: Optional[str] = Field(None, description="The patch string showing the git diff", examples=["@@ -1,3 +1,4 @@..."])

class PREvent(BaseModel):
    """Information representing a Pull Request event."""
    model_config = ConfigDict(use_enum_values=True)

    pr_id: int = Field(..., description="The unique pull request identifier", examples=[101])
    repo: str = Field(..., description="Repository full name", examples=["owner/repo"])
    commit_sha: str = Field(..., description="Latest commit SHA in the PR", examples=["a1b2c3d4e5f6"])
    title: str = Field(..., description="Title of the pull request", examples=["feat: add login endpoint"])
    body: Optional[str] = Field(None, description="Body/description of the pull request", examples=["This PR adds custom auth."])
    author: str = Field(..., description="Username of the PR author", examples=["octocat"])
    changed_files: List[FileDiff] = Field(..., description="List of changed files in this PR")
    jira_ticket_id: Optional[str] = Field(None, description="Associated Jira ticket ID", examples=["PROJ-123"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when PR was created")

class JiraTicket(BaseModel):
    """Information representing a Jira Ticket."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., description="Jira issue ID", examples=["PROJ-123"])
    summary: str = Field(..., description="Jira issue summary/title", examples=["As a user I want to log in"])
    description: Optional[str] = Field(None, description="Detailed description of the ticket", examples=["Detailed requirements..."])
    issue_type: str = Field(..., description="Type of the Jira issue", examples=["Story"])
    status: str = Field(..., description="Current status of the Jira issue", examples=["In Progress"])

class DocChunk(BaseModel):
    """A chunk of documentation or reference code."""
    model_config = ConfigDict(use_enum_values=True)

    chunk_id: str = Field(..., description="Unique chunk identifier", examples=["chunk_0"])
    content: str = Field(..., description="Text content of the chunk", examples=["This is a document content..."])
    source_type: SourceType = Field(..., description="The source type of the document")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Metadata dictionary associated with the chunk")

class ScoredChunk(DocChunk):
    """A document chunk scored during retrieval."""
    model_config = ConfigDict(use_enum_values=True)

    bm25_score: float = Field(..., description="BM25 relevance score", examples=[1.5])
    semantic_score: float = Field(..., description="Semantic embeddings similarity score", examples=[0.85])
    token_count: int = Field(..., description="Number of tokens in this chunk", examples=[120])

    @computed_field
    @property
    def final_score(self) -> float:
        """Calculates the weighted average of BM25 and semantic scores."""
        return 0.4 * self.bm25_score + 0.6 * self.semantic_score

class ContextPack(BaseModel):
    """A collection of context chunks retrieved for a PR."""
    model_config = ConfigDict(use_enum_values=True)

    pr_id: int = Field(..., description="The pull request identifier", examples=[101])
    chunks: List[ScoredChunk] = Field(..., description="List of scored context chunks")
    total_tokens: int = Field(..., description="Total tokens in all chunks", examples=[2400])
    budget_used: int = Field(..., description="Percentage or amount of token budget used", examples=[60])

class Issue(BaseModel):
    """A code quality/security issue found in code review."""
    model_config = ConfigDict(use_enum_values=True)

    file_path: str = Field(..., description="Path to the file containing the issue", examples=["src/auth.py"])
    line_number: Optional[int] = Field(None, description="Specific line number of the issue", examples=[42])
    severity: IssueSeverity = Field(..., description="Severity level of the issue")
    category: IssueCategory = Field(..., description="Type/category of the issue")
    message: str = Field(..., description="Description of the issue", examples=["Hardcoded credentials detected."])
    suggestion: str = Field(..., description="Actionable suggestion to resolve the issue", examples=["Use environment variables instead."])

class ReviewResponse(BaseModel):
    """Overall review response from the agent."""
    model_config = ConfigDict(use_enum_values=True)

    summary: str = Field(..., description="High-level summary of the review findings", examples=["PR looks clean overall, with minor style fixes."])
    issues: List[Issue] = Field(..., description="List of identified issues")
    suggestions: List[str] = Field(default_factory=list, description="General suggestions for improvements", examples=[["Add unit tests for helper functions."]])
    approval: ApprovalStatus = Field(..., description="Agent's PR approval status")
    confidence: float = Field(..., description="Review confidence score (0.0 to 1.0)", examples=[0.92])
    tokens_used: int = Field(..., description="Total LLM tokens consumed during review", examples=[1500])
    model_used: str = Field(..., description="Model name used for the review", examples=["llama3"])
    latency_ms: float = Field(..., description="Processing time in milliseconds", examples=[1200.5])

class AgentState(BaseModel):
    """State management for the CodeLens review agent workflow."""
    model_config = ConfigDict(use_enum_values=True)

    pr_event: PREvent = Field(..., description="The input Pull Request event")
    context_pack: Optional[ContextPack] = Field(None, description="Retrieved context information")
    review: Optional[ReviewResponse] = Field(None, description="Final review response")
    retry_count: int = Field(default=0, description="Workflow retry count")
    error: Optional[str] = Field(None, description="Error message if workflow failed")

