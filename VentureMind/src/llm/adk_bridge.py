import json
import re
from pydantic import BaseModel, Field, ConfigDict
from .ollama_client import OllamaClient

class ADKResponse(BaseModel):
    """Response wrapper bridging Ollama completions to Google Agents SDK model expectations."""
    model_config = ConfigDict(use_enum_values=True)

    text: str
    tool_calls: list[dict] = Field(default_factory=list)
    model: str

class OllamaADKModel:
    """Bridges the custom Ollama client to the Google Agents SDK model interface."""

    def __init__(self, ollama_client: OllamaClient, model_name: str):
        self.ollama_client = ollama_client
        self.model_name = model_name

    async def generate_content(
        self,
        prompt: str,
        tools: list[dict] = None,
        system: str = None,
    ) -> ADKResponse:
        """Generate content from the model, supporting tool prompts and tool call parsing."""
        full_prompt = prompt
        if tools:
            tool_instructions = self.format_tools_for_prompt(tools)
            if tool_instructions:
                full_prompt = f"{tool_instructions}\n\nUser Request: {prompt}"

        response_text = await self.ollama_client.generate(
            prompt=full_prompt,
            model=self.model_name,
            system=system,
            expect_json=False,
        )

        tool_calls = self._parse_tool_calls(response_text)
        return ADKResponse(
            text=response_text,
            tool_calls=tool_calls,
            model=self.model_name,
        )

    def format_tools_for_prompt(self, tools: list[dict]) -> str:
        """Format a list of tool definitions into instructions for prompt injection."""
        if not tools:
            return ""

        formatted_tools = []
        for tool in tools:
            name = tool.get("name", "Unknown")
            desc = tool.get("description", "No description provided.")
            params = tool.get("parameters", {})
            formatted_tools.append(
                f"TOOL: {name}\n"
                f"DESCRIPTION: {desc}\n"
                f"PARAMETERS: {json.dumps(params)}"
            )

        tools_str = "\n\n".join(formatted_tools)

        instruction = (
            "You have access to the following tools:\n\n"
            f"{tools_str}\n\n"
            "If you need to call a tool to answer the request, you MUST respond ONLY with a JSON block "
            "in the following format (no other text, markdown fences are allowed):\n"
            "```json\n"
            "{\n"
            '  "tool_call": {\n'
            '    "name": "tool_name",\n'
            '    "arguments": {\n'
            '      "param_name": "value"\n'
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "If no tool is needed, respond with your regular text answer."
        )
        return instruction

    def _parse_tool_calls(self, response_text: str) -> list[dict]:
        """Extract tool calls from the model response text using balanced regex matching."""
        tool_calls = []
        
        # Regex matching curly brace blocks with up to 2 levels of nesting
        nested_json_pattern = r'(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})'
        matches = re.findall(nested_json_pattern, response_text)

        for match in matches:
            if "tool_call" in match:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and "tool_call" in parsed:
                        call_info = parsed["tool_call"]
                        if isinstance(call_info, dict) and "name" in call_info:
                            tool_calls.append({
                                "name": call_info["name"],
                                "arguments": call_info.get("arguments", {})
                            })
                except json.JSONDecodeError:
                    continue

        return tool_calls
