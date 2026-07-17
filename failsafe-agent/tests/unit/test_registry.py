import pytest
from typing import Optional, Union

from src.tools.registry import ToolRegistry


def test_registry_schema_generation() -> None:
    test_registry = ToolRegistry()
    
    @test_registry.tool
    def test_func(a: str, b: int, c: Optional[float] = None) -> str:
        """This is a test function.
        
        Detailed description here.
        """
        return f"{a}:{b}:{c}"
        
    schemas = test_registry.get_schemas()
    assert len(schemas) == 1
    
    schema = schemas[0]
    assert schema["name"] == "test_func"
    assert schema["description"] == "This is a test function."
    
    # Input schema tests
    input_schema = schema["input_schema"]
    assert input_schema["type"] == "object"
    
    properties = input_schema["properties"]
    assert properties["a"]["type"] == "string"
    assert properties["b"]["type"] == "integer"
    assert properties["c"]["type"] == "number"
    
    # Required parameters check (a and b are required, c is optional because it has a default)
    assert "a" in input_schema["required"]
    assert "b" in input_schema["required"]
    assert "c" not in input_schema["required"]


@pytest.mark.asyncio
async def test_registry_execution() -> None:
    test_registry = ToolRegistry()
    
    @test_registry.tool
    async def async_add(x: int, y: int) -> int:
        return x + y
        
    res = await test_registry.call("async_add", x=10, y=20)
    assert res == 30
