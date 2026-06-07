import json
import re
from typing import AsyncGenerator, Optional
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from src.llm.ollama_client import OllamaClient

class OllamaADKModel(BaseLlm):
    """Google Agents SDK (google-adk) integration model for Ollama local inference."""

    client: OllamaClient
    """The underlying Ollama client instance."""

    @classmethod
    def supported_models(cls) -> list[str]:
        """Returns regex patterns matching models supported by this subclass."""
        return [r"ollama/.*", r"local/.*", r"qwen.*"]

    def format_tools_for_prompt(self, tools: list[dict]) -> str:
        """Renders tool schemas as a JSON block the model can reference in prompts."""
        if not tools:
            return ""
        return json.dumps(tools, indent=2)

    def _extract_function_call(self, text: str) -> Optional[types.FunctionCall]:
        """Parse function call JSON from response text, handling fences and raw JSON."""
        cleaned_text = text.strip()
        markdown_code_block_pattern = re.compile(
            r'```(?:(json|tool_code))?\s*(.*?)\s*```', re.DOTALL
        )
        block_match = markdown_code_block_pattern.search(cleaned_text)
        json_candidate = block_match.group(2).strip() if block_match else cleaned_text

        try:
            # Find the starting brace of the JSON object
            first_brace = json_candidate.find('{')
            if first_brace != -1:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(json_candidate[first_brace:])
                name = obj.get("name") or obj.get("function")
                params = obj.get("parameters") or obj.get("args") or {}
                if name:
                    return types.FunctionCall(name=name, args=params)
        except Exception:
            pass
        return None

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generates content asynchronously from the given request contents and tools."""
        messages = []

        # Start with the defined system instruction
        system_instruction = llm_request.config.system_instruction or ""

        # Extract tool schemas if present
        all_tools = []
        if llm_request.config.tools:
            for tool_item in llm_request.config.tools:
                if isinstance(tool_item, types.Tool) and tool_item.function_declarations:
                    for decl in tool_item.function_declarations:
                        if hasattr(decl, "model_dump"):
                            all_tools.append(decl.model_dump(exclude_none=True))
                        else:
                            all_tools.append(dict(decl))

        # Inject tools instructions if any tools are registered
        if all_tools:
            tools_json = self.format_tools_for_prompt(all_tools)
            tool_instructions = (
                "You have access to the following functions:\n"
                f"{tools_json}\n\n"
                "When you need to call a function, you MUST respond in the format of a JSON object containing the function name and parameters:\n"
                '{"name": "function_name", "parameters": {"param1": "value1", ...}}\n'
                "When you call a function, you MUST NOT include any other text in the response.\n"
            )
            if system_instruction:
                system_instruction = f"{system_instruction}\n\n{tool_instructions}"
            else:
                system_instruction = tool_instructions

        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        # Append conversation messages
        for content_item in llm_request.contents:
            role = content_item.role or "user"
            if role == "model":
                role = "assistant"

            parts_text = []
            for part in content_item.parts:
                if part.text:
                    parts_text.append(part.text)
                elif part.function_call:
                    fc_dict = {
                        "name": part.function_call.name,
                        "parameters": part.function_call.args
                    }
                    parts_text.append(json.dumps(fc_dict))
                elif part.function_response:
                    parts_text.append(
                        f"Invoking tool `{part.function_response.name}` produced: "
                        f"`{json.dumps(part.function_response.response)}`."
                    )

            messages.append({"role": role, "content": "\n".join(parts_text)})

        try:
            response_text = await self.client.chat(messages)
        except Exception as e:
            yield LlmResponse(
                error_code="OLLAMA_CHAT_ERROR",
                error_message=f"Ollama chat execution failed: {e}"
            )
            return

        # Check for function call
        func_call = self._extract_function_call(response_text)
        if func_call:
            content = types.Content(
                role="model",
                parts=[types.Part(function_call=func_call)]
            )
        else:
            content = types.Content(
                role="model",
                parts=[types.Part(text=response_text)]
            )

        yield LlmResponse(
            content=content,
            model_version=self.model,
            turn_complete=True
        )

    async def generate_content(self, prompt: str, tools: list[dict] = None) -> LlmResponse:
        """Single-turn generation wrapper compatible with ADK model generation."""
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        config = types.GenerateContentConfig()
        if tools:
            decls = []
            for t in tools:
                if isinstance(t, dict):
                    decls.append(types.FunctionDeclaration(**t))
                else:
                    decls.append(t)
            config.tools = [types.Tool(function_declarations=decls)]

        llm_request = LlmRequest(
            model=self.model,
            contents=[content],
            config=config
        )

        responses = []
        async for resp in self.generate_content_async(llm_request):
            responses.append(resp)
        if responses:
            return responses[0]

        return LlmResponse(
            error_code="NO_RESPONSE",
            error_message="No response received from Ollama model"
        )
