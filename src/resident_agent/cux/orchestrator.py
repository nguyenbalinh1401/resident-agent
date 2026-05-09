"""CUX Orchestrator - LLM-first conversation management with function calling.

This orchestrator uses LLM with tool calling to handle user messages.
No complex intent detection - the LLM decides what to do based on tool definitions.
"""

from typing import Optional, List, Dict, Any, AsyncGenerator
from pathlib import Path
import json
import re
import unicodedata
import yaml
import structlog
from openai import AsyncOpenAI

from resident_agent.core.config import Settings
from resident_agent.core.openai_client import OpenAIClient
from resident_agent.core.llm_client_factory import build_openai_client_kwargs
from resident_agent.clients.pulse_client import PulseClient
from resident_agent.schemas.chat_schemas import (
    ChatResponse,
    ActionButton,
    ActionStyle,
    ToolCall,
    SSEEvent,
    SSEEventType,
)
from resident_agent.cux.tools import TOOLS, execute_tool
from resident_agent.auth.permission_mapper import PermissionMapper
from resident_agent.cux.action_generator import ActionGenerator
from resident_agent.cux.state_manager import StateManager

logger = structlog.get_logger()


def _normalize_locale(locale: Optional[str]) -> str:
    raw = (locale or "").strip().lower()
    if raw.startswith("en"):
        return "en"
    return "vi"


def _localized_text(locale: str, vi: str, en: str) -> str:
    return en if _normalize_locale(locale) == "en" else vi


def _response_language_instruction(locale: str) -> str:
    if _normalize_locale(locale) == "en":
        return (
            "Respond in English by default. If the user explicitly switches to Vietnamese, "
            "you may reply in Vietnamese for that turn."
        )
    return (
        "Mặc định trả lời bằng tiếng Việt. Nếu người dùng chuyển sang tiếng Anh rõ ràng, "
        "hãy trả lời bằng tiếng Anh cho lượt đó."
    )


def _attachment_value(att: Any, key: str) -> Any:
    """Read attachment data from either dicts or Pydantic-style objects."""
    if isinstance(att, dict):
        return att.get(key)
    return getattr(att, key, None)


def _attachment_is_image(att: Any) -> bool:
    return str(_attachment_value(att, "type") or "").lower() == "image"


def _normalize_text_for_match(content: str) -> str:
    text = unicodedata.normalize("NFKD", content or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _looks_like_high_impact_success_claim(content: str) -> bool:
    text = _normalize_text_for_match(content)
    success_markers = [
        "đã tạo",
        "đã ghi nhận",
        "đã đặt",
        "đã báo cáo",
        "đã cập nhật",
        "đã xoá",
        "đã xóa",
        "đã huỷ",
        "đã hủy",
        "thành công",
        "da tao",
        "da ghi nhan",
        "da dat",
        "da bao cao",
        "da cap nhat",
        "da xoa",
        "da huy",
        "thanh cong",
        "created",
        "booked",
        "recorded",
        "updated",
        "deleted",
        "cancelled",
        "reported",
    ]
    return any(marker in text for marker in success_markers)


def _looks_like_clarification_question(content: str) -> bool:
    text = _normalize_text_for_match(content).strip()
    if "?" in text:
        return True
    question_starts = [
        "ban muon",
        "ban co muon",
        "vui long cho toi biet",
        "cho toi biet",
        "ban vui long",
        "hay cho toi biet",
        "bạn muốn",
        "bạn có muốn",
        "vui lòng cho tôi biết",
        "cho tôi biết",
        "bạn vui lòng",
        "hãy cho tôi biết",
    ]
    return any(text.startswith(prefix) for prefix in question_starts)


def _format_tool_error(error: Exception) -> Dict[str, Any]:
    details = getattr(error, "details", None)
    status_code = getattr(error, "status_code", None)
    payload: Dict[str, Any] = {"error": str(error)}
    if status_code is not None:
        payload["statusCode"] = status_code
    if details:
        payload["details"] = details
    return payload


def _sanitize_user_message(content: str, locale: str) -> str:
    """Remove internal implementation details from user-facing responses."""
    if not content:
        return content

    sanitized = content
    sanitized = re.sub(
        r"\b(?:get|create|update|delete|approve|reject|assign|register|notify|record|delegate|revoke|lookup|mark|submit|cancel|complete|preverify|bulk_update)_[a-z0-9_]+\(\)",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(?:using|via)\s+[a-z_]+\(\)",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(?:using|via)\s*(?=[\.,;:])",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(?:unit|user|ticket|request|package|parcel|notification|event|amenity|card)\s+id:\s*[A-Za-z0-9-]{6,}",
        _localized_text(locale, "căn hộ liên kết", "linked unit"),
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(?:public_?id|internal_?id|createdby|updatedby|requestdatajson|userid|unitid|ticketid|requestid|packageid|parcelid|eventid|amenityid|cardid)\b",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f-]{19,}\b",
        _localized_text(locale, "mã nội bộ đã được ẩn", "internal code hidden"),
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = sanitized.replace(" .", ".").replace(" ,", ",").strip()

    lines = []
    for line in sanitized.splitlines():
        lowered = line.lower()
        if re.search(r"\b[a-z]+_[a-z0-9_]+\(\)", lowered):
            continue
        lines.append(line)
    sanitized = "\n".join(lines).strip()

    return sanitized or _localized_text(
        locale,
        "Mình đã rà thông tin liên quan và có thể hỗ trợ bạn theo hướng nghiệp vụ tiếp theo.",
        "I reviewed the relevant information and can help you with the next business step.",
    )


def _permission_strings(
    permission_mapper: PermissionMapper,
    permissions: Optional[List[Dict[str, Any]]],
) -> List[str]:
    normalized = permission_mapper.normalize_permissions(permissions or [])
    result: List[str] = []
    for p in normalized:
        if p.get("resource") == "*":
            result.append("ADMIN")
        else:
            result.append(f"{p.get('resource')}.{p.get('action')}")
    return result


def _load_prompts(path: str) -> Dict[str, str]:
    """Load system prompts from a YAML file.

    Args:
        path: Path to the prompts YAML file.

    Returns:
        Dict mapping prompt names to their template strings.
    """
    prompts_file = Path(path)
    with open(prompts_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class CuxOrchestrator:
    """LLM-first orchestrator with function calling.

    This orchestrator coordinates:
    1. Message processing via LLM
    2. Tool execution (via PulseClient)
    3. Response generation with actions
    4. Conversation state management (Redis)
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        state_manager: Optional[StateManager] = None,
        action_generator: Optional[ActionGenerator] = None,
        permission_mapper: Optional[PermissionMapper] = None,
    ):
        """Initialize CUX Orchestrator.

        Args:
            settings: Application settings
            state_manager: State manager for conversation history
            action_generator: Action button generator
            permission_mapper: Permission to tool mapper
        """
        self.settings = settings or Settings.get()
        self.state_manager = state_manager or StateManager(self.settings)
        self.permission_mapper = permission_mapper or PermissionMapper()

        # Load prompts from YAML
        self._prompts = _load_prompts(self.settings.prompts_path)

        # Create AsyncOpenAI client for ActionGenerator
        self._openai_client = AsyncOpenAI(
            **build_openai_client_kwargs(self.settings)
        )

        # Get tool_permissions from PermissionMapper config
        tool_permissions = self.permission_mapper._config.get("tool_to_permission", {})

        # Initialize ActionGenerator with dependencies
        self.action_generator = action_generator or ActionGenerator(
            openai_client=self._openai_client,
            prompts=self._prompts,
            tool_permissions=tool_permissions,
            model=self.settings.openai_model,
        )

    async def process(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_client: Optional[PulseClient] = None,
        intent_type: str = "agentic_flow",
        attachments: Optional[List[Any]] = None,
        locale: str = "vi",
    ) -> ChatResponse:
        """Process a user message and return response.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload from JWT
            pulse_client: Authenticated PulseClient instance (injected via dependency)
            intent_type: Intent type (chitchat, agentic_flow, tool_call)
            attachments: Optional attachments (images, files)

        Returns:
            ChatResponse with message, actions, and tool calls
        """
        logger.info(
            "cux_process_start",
            session_id=session_id,
            user_id=user.get("sub"),
            intent_type=intent_type,
            message_preview=message[:50],
        )

        # Connect to Redis if needed
        if self.state_manager._redis is None:
            await self.state_manager.connect()

        # Add user message to history
        await self.state_manager.add_message(session_id, "user", message)

        # Get conversation history
        history = await self.state_manager.get_history_for_llm(session_id, limit=10)

        # Get user permissions
        permissions = self.permission_mapper.normalize_permissions(user.get("permissions", []))

        # Handle based on intent type
        if intent_type == "chitchat":
            response = await self._handle_chitchat(message, session_id, history, locale)
        elif intent_type == "tool_call":
            response = await self._handle_tool_call_direct(
                message, session_id, pulse_client, user, locale
            )
        else:  # agentic_flow
            response = await self._handle_agentic_flow(
                message,
                session_id,
                user,
                pulse_client,
                permissions,
                history,
                attachments,
                locale,
            )

        # Add assistant message to history
        await self.state_manager.add_message(session_id, "assistant", response.message)

        return response

    async def process_stream(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_client: Optional[PulseClient] = None,
        intent_type: str = "agentic_flow",
        attachments: Optional[List[Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a user message with streaming response.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload from JWT
            pulse_client: Authenticated PulseClient instance (injected via dependency)
            intent_type: Intent type
            attachments: Optional attachments

        Yields:
            SSE event strings
        """
        logger.info(
            "cux_stream_start",
            session_id=session_id,
            user_id=user.get("sub"),
            intent_type=intent_type,
        )

        # Connect to Redis
        if self.state_manager._redis is None:
            await self.state_manager.connect()

        # Add user message to history
        await self.state_manager.add_message(session_id, "user", message)

        # Get history
        history = await self.state_manager.get_history_for_llm(session_id, limit=10)

        permissions = self.permission_mapper.normalize_permissions(user.get("permissions", []))

        # Build messages for LLM
        messages = self._build_messages(history, message, attachments)

        # Get filtered tools
        tools = self.permission_mapper.get_filtered_tools(permissions)

        # Build system prompt
        system_prompt = self._prompts["stream"].format(
            user_name=user.get("name", "Cư dân"),
            unit=user.get("unit", "Resident"),
            permissions=", ".join(_permission_strings(self.permission_mapper, permissions)) if permissions else "basic",
        )

        messages.insert(0, {"role": "system", "content": system_prompt})

        accumulated_content = ""
        tool_calls_made = []
        last_tool_name = None

        async with OpenAIClient(self.settings) as client:
            # First call - might trigger tools
            # Note: chat_completion_stream returns an async generator, don't await it
            stream = client.chat_completion_stream(
                messages=messages,
                tools=tools if intent_type != "chitchat" else None,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle content streaming
                if delta.content:
                    accumulated_content += delta.content
                    event = SSEEvent(
                        type=SSEEventType.TOKEN,
                        session_id=session_id,
                        content=delta.content,
                    )
                    yield event.to_sse()

                # Handle tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        tool_calls_made.append(tool_call)

                if chunk.choices[0].finish_reason:
                    break

            # Log first stream response
            logger.debug(
                "llm_stream_response",
                context="stream_first_call",
                session_id=session_id,
                accumulated_content_length=len(accumulated_content),
                tool_calls_made=[
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in tool_calls_made
                ],
                finish_reason=chunk.choices[0].finish_reason if chunk.choices else None,
            )

            # If tools were called, execute them and continue
            if tool_calls_made and pulse_client:
                # Execute tools
                tool_results = []
                for tc in tool_calls_made:
                    tool_name = tc.function.name
                    params = json.loads(tc.function.arguments)
                    last_tool_name = tool_name

                    # Yield tool call event
                    event = SSEEvent(
                        type=SSEEventType.TOOL_CALL,
                        session_id=session_id,
                        tool_call=ToolCall(
                            tool=tool_name,
                            params=params,
                        ),
                    )
                    yield event.to_sse()

                    # Execute the tool
                    try:
                        result = await execute_tool(
                            tool_name,
                            params,
                            pulse_client,
                            user_permissions=permissions,
                        )
                        tool_results.append(
                            {
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "content": json.dumps(result, ensure_ascii=False),
                            }
                        )

                        # Store result
                        tool_calls_made[tool_calls_made.index(tc)] = ToolCall(
                            tool=tool_name,
                            params=params,
                            result=result,
                        )

                    except Exception as e:
                        logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                        tool_results.append(
                            {
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "content": json.dumps({"error": str(e)}),
                            }
                        )

                # Add tool results to messages and get final response
                messages.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls_made
                            if hasattr(tc, "id")
                        ],
                    }
                )
                messages.extend(tool_results)

                # Stream final response
                # Note: chat_completion_stream returns an async generator, don't await it
                final_stream = client.chat_completion_stream(messages=messages)

                async for chunk in final_stream:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    if delta.content:
                        accumulated_content += delta.content
                        event = SSEEvent(
                            type=SSEEventType.TOKEN,
                            session_id=session_id,
                            content=delta.content,
                        )
                        yield event.to_sse()

                    if chunk.choices[0].finish_reason:
                        break

                # Log final stream response
                logger.debug(
                    "llm_stream_response",
                    context="stream_final_response",
                    session_id=session_id,
                    accumulated_content_length=len(accumulated_content),
                    finish_reason=chunk.choices[0].finish_reason if chunk.choices else None,
                )

        # Generate actions
        actions = await self.action_generator.generate_actions(
            last_tool=last_tool_name,
            permissions=permissions,
            last_message=accumulated_content,
            locale="vi",
        )

        # Yield actions event
        event = SSEEvent(
            type=SSEEventType.ACTIONS,
            session_id=session_id,
            actions=actions,
        )
        yield event.to_sse()

        # Add to history
        await self.state_manager.add_message(session_id, "assistant", accumulated_content)

        # Yield complete event
        event = SSEEvent(
            type=SSEEventType.COMPLETE,
            session_id=session_id,
            content=accumulated_content,
        )
        yield event.to_sse()

    def _parse_agentic_json_response(
        self,
        content: str,
    ) -> tuple:
        """Parse the agentic LLM JSON response into message and actions.

        Args:
            content: Raw string content from the LLM response.

        Returns:
            Tuple of (message: str, actions: List[Dict]).
        """
        # Strip markdown code block wrapping if present (```...```)
        stripped = content.strip()
        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL)
        if code_block_match:
            stripped = code_block_match.group(1).strip()
        else:
            # Try to find first { ... } JSON object even without code block
            json_match = re.search(r"\{.*\}", stripped, re.DOTALL)
            if json_match:
                stripped = json_match.group(0)

        try:
            parsed = json.loads(stripped)
            message = parsed.get("message", content)
            actions = parsed.get("actions", [])

            if not isinstance(actions, list):
                logger.warning("agentic_actions_not_list", actions_type=type(actions).__name__)
                return message, []

            validated = []
            for action in actions[:3]:
                if isinstance(action, dict) and "tool" in action:
                    validated.append({
                        "tool": action["tool"],
                        "params": action.get("params", {}),
                        "allowed": action.get("allowed", True),
                    })

            return message, validated

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "agentic_json_parse_failed",
                error=str(e),
                content_preview=content[:200],
            )
            return content, []

    async def _execute_tool_calls(
        self,
        tool_calls: List[Any],
        pulse_client: Optional[PulseClient],
        permissions: List[Dict[str, str]],
        attachments: Optional[List[Any]] = None,
    ) -> tuple[List[Dict[str, Any]], List[ToolCall], Optional[str]]:
        tool_results: List[Dict[str, Any]] = []
        tool_calls_made: List[ToolCall] = []
        last_tool_name: Optional[str] = None

        for tc in tool_calls:
            tool_name = tc.function.name
            params = json.loads(tc.function.arguments)
            last_tool_name = tool_name

            logger.info("executing_tool", tool=tool_name, params=params)

            try:
                result = await execute_tool(
                    tool_name,
                    params,
                    pulse_client,
                    user_permissions=permissions,
                    attachments=attachments,
                )
                tool_results.append(
                    {
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
                tool_calls_made.append(
                    ToolCall(
                        tool=tool_name,
                        params=params,
                        result=result,
                    )
                )
            except Exception as e:
                logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                error_payload = _format_tool_error(e)
                tool_results.append(
                    {
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": json.dumps(error_payload, ensure_ascii=False),
                    }
                )
                tool_calls_made.append(
                    ToolCall(
                        tool=tool_name,
                        params=params,
                        result=error_payload,
                    )
                )

        return tool_results, tool_calls_made, last_tool_name

    async def _retry_agentic_call_with_tool_guard(
        self,
        client: OpenAIClient,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        session_id: str,
    ) -> Any:
        guarded_messages = list(messages)
        guarded_messages.insert(
            1,
            {
                "role": "system",
                "content": (
                    "For this turn, never claim that a create, update, delete, booking, "
                    "report, approval, or cancellation action succeeded unless you actually "
                    "call the correct tool in this response. If data is missing, ask a "
                    "clarification question instead."
                ),
            },
        )
        retry_response = await client.chat_completion(
            messages=guarded_messages,
            tools=tools,
        )
        self._log_llm_response(
            retry_response,
            context="agentic_retry_with_tool_guard",
            session_id=session_id,
        )
        return retry_response

    async def _handle_chitchat(
        self,
        message: str,
        session_id: str,
        history: List[Dict[str, str]],
        locale: str = "vi",
    ) -> ChatResponse:
        """Handle chitchat messages directly with LLM.

        Args:
            message: User message
            session_id: Session identifier
            history: Conversation history

        Returns:
            ChatResponse
        """
        system_prompt = (
            f"{self._prompts['chitchat']}\n\n"
            f"Language rule: {_response_language_instruction(locale)}"
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        async with OpenAIClient(self.settings) as client:
            response = await client.chat_completion(messages=messages)
            self._log_llm_response(response, context="chitchat", session_id=session_id)

            content = response.choices[0].message.content

            # Get contextual actions
            actions = await self.action_generator.generate_actions(
                last_message=message,  # user's message as context
                locale=locale,
            )

            return ChatResponse(
                message=_sanitize_user_message(content, locale),
                actions=actions,
                session_id=session_id,
            )

    async def _handle_agentic_flow(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_client: Optional[PulseClient],
        permissions: List[Dict[str, str]],
        history: List[Dict[str, str]],
        attachments: Optional[List[Any]],
        locale: str = "vi",
    ) -> ChatResponse:
        """Handle agentic flow with tool calling.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload
            pulse_client: Authenticated PulseClient instance
            permissions: User permissions from API
            history: Conversation history
            attachments: Optional attachments

        Returns:
            ChatResponse
        """
        # Build system prompt
        system_prompt = self._prompts["agentic"].format(
            user_name=user.get("name", "Cư dân"),
            unit=user.get("unit", "Resident"),
            permissions=", ".join(_permission_strings(self.permission_mapper, permissions)) if permissions else "basic",
        )

        system_prompt = (
            f"{system_prompt}\n\n"
            f"Language rule: {_response_language_instruction(locale)}\n"
            "Match the user's language in this turn. Do not default to Vietnamese when the user writes in English."
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # Add attachments if provided (override last user message with multimodal content)
        if attachments:
            # For multimodal support
            user_message = {"role": "user", "content": []}
            user_message["content"].append({"type": "text", "text": message})

            for att in attachments:
                if _attachment_is_image(att):
                    mime_type = _attachment_value(att, "mime_type")
                    data = _attachment_value(att, "data")
                    if not mime_type or not data:
                        continue
                    user_message["content"].append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{data}"
                            },
                        }
                    )

            messages[-1] = user_message

        # Get filtered tools
        tools = self.permission_mapper.get_filtered_tools(permissions)

        tool_calls_made = []
        last_tool_name = None

        async with OpenAIClient(self.settings) as client:
            # First LLM call
            response = await client.chat_completion(
                messages=messages,
                tools=tools,
            )
            self._log_llm_response(response, context="agentic_first_call", session_id=session_id)

            assistant_message = response.choices[0].message

            # Check if tool calls were made
            if assistant_message.tool_calls:
                tool_results, executed_calls, last_tool_name = await self._execute_tool_calls(
                    assistant_message.tool_calls,
                    pulse_client,
                    permissions,
                    attachments,
                )
                tool_calls_made.extend(executed_calls)

                # Add assistant message with tool calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in assistant_message.tool_calls
                        ],
                    }
                )
                messages.extend(tool_results)

                # Second LLM call with tool results - force JSON output
                final_response = await client.chat_completion(
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                self._log_llm_response(final_response, context="agentic_final_response", session_id=session_id)
                raw_content = final_response.choices[0].message.content
                message_text, actions = self._parse_agentic_json_response(raw_content)
                if (
                    not tool_calls_made
                    and _looks_like_high_impact_success_claim(message_text)
                    and not _looks_like_clarification_question(message_text)
                ):
                    message_text = (
                        "Mình đã ghi nhận yêu cầu của bạn nhưng chưa xác nhận được thao tác thành công trên hệ thống. "
                        "Bạn vui lòng thử lại hoặc cung cấp thêm thông tin để mình thực hiện đúng cách."
                    )
                    actions = []
            else:
                raw_content = assistant_message.content or '{"message": "Tôi không hiểu yêu cầu của bạn. Bạn có thể diễn đạt lại không?", "actions": []}'
                message_text, actions = self._parse_agentic_json_response(raw_content)

            if (
                not tool_calls_made
                and _looks_like_high_impact_success_claim(message_text)
                and not _looks_like_clarification_question(message_text)
            ):
                retry_response = await self._retry_agentic_call_with_tool_guard(
                    client=client,
                    messages=messages,
                    tools=tools,
                    session_id=session_id,
                )
                retry_message = retry_response.choices[0].message
                if retry_message.tool_calls:
                    assistant_message = retry_message
                    tool_results, executed_calls, last_tool_name = await self._execute_tool_calls(
                        assistant_message.tool_calls,
                        pulse_client,
                        permissions,
                        attachments,
                    )
                    tool_calls_made.extend(executed_calls)
                    messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in assistant_message.tool_calls
                            ],
                        }
                    )
                    messages.extend(tool_results)
                    final_response = await client.chat_completion(
                        messages=messages,
                        response_format={"type": "json_object"},
                    )
                    self._log_llm_response(
                        final_response,
                        context="agentic_final_response_after_late_retry",
                        session_id=session_id,
                    )
                    raw_content = final_response.choices[0].message.content
                    message_text, actions = self._parse_agentic_json_response(raw_content)
                else:
                    message_text = (
                        "Mình đã ghi nhận yêu cầu của bạn nhưng chưa xác nhận được thao tác thành công trên hệ thống. "
                        "Bạn vui lòng thử lại hoặc cung cấp thêm thông tin để mình thực hiện đúng cách."
                    )
                    actions = []

        return ChatResponse(
            message=_sanitize_user_message(message_text, locale),
            actions=actions,
            session_id=session_id,
            tool_calls=tool_calls_made,
        )

    async def _handle_tool_call_direct(
        self,
        action: str,
        session_id: str,
        pulse_client: Optional[PulseClient],
        user: Dict[str, Any],
        locale: str = "vi",
    ) -> ChatResponse:
        """Handle direct tool call (from UI action button).

        Uses LLM to:
        1. Check if action is valid and user has related permission
        2. Decide which tool to call
        3. Format response as markdown

        Args:
            action: Action type from UI (e.g., "view_bills", "report_incident")
            session_id: Session identifier
            pulse_client: Authenticated PulseClient instance
            user: User payload with permissions

        Returns:
            ChatResponse
        """
        permissions = self.permission_mapper.normalize_permissions(user.get("permissions", []))

        # Use ActionGenerator to validate action and decide tool
        tool_decision = await self.action_generator.resolve_action(action, permissions, locale)

        if not tool_decision.get("allowed"):
            logger.info(
                "action_not_allowed",
                action=action,
                reason=tool_decision.get("reason"),
                user_id=user.get("sub"),
            )
            return ChatResponse(
                message=tool_decision.get(
                    "message",
                    "Xin lỗi, tôi không hỗ trợ hành động này. Vui lòng thử hành động khác."
                ),
                session_id=session_id,
            )

        tool_name = tool_decision.get("tool")
        params = tool_decision.get("params", {})

        if not tool_name:
            return ChatResponse(
                message="Không thể xác định công cụ cho hành động này.",
                session_id=session_id,
            )

        try:
            result = await execute_tool(
                tool_name,
                params,
                pulse_client,
                user_permissions=permissions,
            )

            # Use ActionGenerator to format response as markdown
            message = await self.action_generator.format_tool_result(action, tool_name, result, locale)

            return ChatResponse(
                message=_sanitize_user_message(message, locale),
                session_id=session_id,
                tool_calls=[
                    ToolCall(
                        tool=tool_name,
                        params=params,
                        result=result,
                    )
                ],
            )

        except Exception as e:
            logger.error("direct_tool_call_failed", action=action, tool=tool_name, error=str(e))
            return ChatResponse(
                message=f"Không thể thực hiện hành động: {str(e)}",
                session_id=session_id,
            )

    def _log_llm_response(
        self,
        response: Any,
        context: str,
        session_id: str,
    ) -> None:
        """Log LLM response details for debugging.

        Args:
            response: OpenAI chat completion response object
            context: Description of the call context
            session_id: Session identifier
        """
        choice = response.choices[0] if response.choices else None

        logger.debug(
            "llm_response",
            context=context,
            session_id=session_id,
            model=getattr(response, "model", None),
            finish_reason=choice.finish_reason if choice else None,
            content=choice.message.content if choice and choice.message else None,
            tool_calls=[
                {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in (choice.message.tool_calls or [])
            ]
            if choice and choice.message and choice.message.tool_calls
            else None,
            usage=response.usage.model_dump() if response.usage else None,
        )

    def _build_messages(
        self,
        history: List[Dict[str, str]],
        message: str,
        attachments: Optional[List[Any]] = None,
    ) -> List[Dict]:
        """Build messages list for LLM.

        Args:
            history: Conversation history (already contains current user message)
            message: Current user message
            attachments: Optional attachments

        Returns:
            List of message dicts
        """
        messages = list(history)

        # If attachments, modify last user message to be multimodal
        if attachments and messages and messages[-1].get("role") == "user":
            content = [{"type": "text", "text": message}]
            for att in attachments:
                if _attachment_is_image(att) and _attachment_value(att, "data"):
                    mime_type = _attachment_value(att, "mime_type")
                    data = _attachment_value(att, "data")
                    if not mime_type or not data:
                        continue
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{data}"
                            },
                        }
                    )
            messages[-1]["content"] = content

        return messages
