import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Union, get_args, get_origin, get_type_hints
import structlog

from src.config import settings
from src.tools.customer_tool import CustomerRepository
from src.tools.escalation_tool import escalate_to_human as raw_escalate_to_human
from src.tools.policy_tool import PolicyStore
from src.tools.stripe_tools import (
    check_refund_eligibility as stripe_check_refund_eligibility,
    issue_refund as stripe_issue_refund,
    lookup_charge as stripe_lookup_charge,
)

logger = structlog.get_logger()


class ToolRegistry:
    """Registry that manages python tool functions and formats their metadata into Anthropic schemas."""
    def __init__(self) -> None:
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def tool(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to register a tool and build its Anthropic-compatible JSON schema."""
        name = func.__name__
        doc = func.__doc__ or ""
        description = doc.strip().split("\n")[0] if doc else f"Execute {name}."

        sig = inspect.signature(func)
        hints = get_type_hints(func)
        
        properties: Dict[str, Any] = {}
        required: List[str] = []
        
        for param_name, param in sig.parameters.items():
            # Skip infrastructure injected variables
            if param_name in ("self", "cls", "redis_client", "db_pool"):
                continue
                
            param_type = hints.get(param_name, Any)
            is_optional = param.default != inspect.Parameter.empty
            
            origin = get_origin(param_type)
            args = get_args(param_type)
            
            resolved_type = param_type
            if origin is Union:
                # Handle Optional[T] / Union[T, None]
                if type(None) in args:
                    is_optional = True
                    non_none_args = [a for a in args if a is not type(None)]
                    if non_none_args:
                        resolved_type = non_none_args[0]
                else:
                    resolved_type = args[0]
            
            # Map Python types to JSON Schema types
            type_str = "string"
            if resolved_type is int:
                type_str = "integer"
            elif resolved_type is float:
                type_str = "number"
            elif resolved_type is bool:
                type_str = "boolean"
            elif resolved_type is list or get_origin(resolved_type) is list:
                type_str = "array"
            elif resolved_type is dict or get_origin(resolved_type) is dict:
                type_str = "object"
                
            properties[param_name] = {
                "type": type_str,
                "description": f"The {param_name} parameter."
            }
            
            if not is_optional:
                required.append(param_name)

        schema = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        
        self.tools[name] = func
        self.schemas[name] = schema
        return func

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns schemas for all registered tools."""
        return list(self.schemas.values())

    async def call(self, tool_name: str, **kwargs: Any) -> Any:
        """Executes a registered tool by name with keyword arguments."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registry.")
        
        func = self.tools[tool_name]
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)


# Global instance of registry
registry = ToolRegistry()

# Initialize global stores / repositories for wrappers
policy_store = PolicyStore()
customer_repo = CustomerRepository(dsn=settings.DATABASE_URL.get_secret_value())


# --- 3.1: Stripe Tool Wrappers ---
@registry.tool
async def check_refund_eligibility(charge_id: str) -> Dict[str, Any]:
    """Check if a Stripe charge is eligible for refund."""
    return await stripe_check_refund_eligibility(charge_id=charge_id)


@registry.tool
async def issue_refund(charge_id: str, amount_cents: int, reason: str, redis_client: Optional[Any] = None) -> Dict[str, Any]:
    """Issue a Stripe refund with built-in idempotency."""
    return await stripe_issue_refund(charge_id=charge_id, amount_cents=amount_cents, reason=reason, redis_client=redis_client)


@registry.tool
async def lookup_charge(charge_id: str) -> Dict[str, Any]:
    """Retrieve full charge details from Stripe."""
    return await stripe_lookup_charge(charge_id=charge_id)


# --- 3.2: Policy Tool Wrappers ---
@registry.tool
async def search_policy(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Search customer policies using semantic query string."""
    return await policy_store.search_policy(query=query, top_k=top_k)


@registry.tool
def get_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full details of a policy by its ID."""
    return policy_store.get_policy(policy_id=policy_id)


# --- 3.3: Customer Tool Wrappers ---
@registry.tool
async def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve customer details by ID."""
    return await customer_repo.get_customer(customer_id=customer_id)


@registry.tool
async def get_order_history(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve order history list for a customer."""
    return await customer_repo.get_order_history(customer_id=customer_id, limit=limit)


# --- 3.4: Escalation Tool Wrapper ---
@registry.tool
async def escalate_to_human(
    conversation_id: str,
    customer_id: str,
    reason: str,
    confidence_score: float,
    conversation_history: List[Dict[str, Any]],
    tool_call_log: List[Dict[str, Any]],
    db_pool: Any,
    redis_client: Any,
) -> Dict[str, Any]:
    """Escalate conversation state to a human support agent."""
    return await raw_escalate_to_human(
        conversation_id=conversation_id,
        customer_id=customer_id,
        reason=reason,
        confidence_score=confidence_score,
        conversation_history=conversation_history,
        tool_call_log=tool_call_log,
        db_pool=db_pool,
        redis_client=redis_client,
    )


# Smoke test to print generated schemas
if __name__ == "__main__":
    print(json.dumps(registry.get_schemas(), indent=2))
