"""CUX Orchestrator - LLM-first conversation management with function calling.

This orchestrator uses LLM with tool calling to handle user messages.
No complex intent detection - the LLM decides what to do based on tool definitions.
"""

from typing import Optional, List, Dict, Any, AsyncGenerator
import json
import random
import structlog

from resident_agent.core.config import Settings
from resident_agent.core.openai_client import OpenAIClient
from resident_agent.schemas.chat_schemas import (
    ChatResponse,
    ActionButton,
    ActionStyle,
    ToolCall,
    SSEEvent,
    SSEEventType,
)
from .tools import TOOLS, get_tools_for_capabilities, execute_tool
from .action_generator import ActionGenerator
from .state_manager import StateManager

logger = structlog.get_logger()


class CuxOrchestrator:
    """LLM-first orchestrator with function calling.

    This orchestrator coordinates:
    1. Message processing via LLM
    2. Tool execution (via PulseClient)
    3. Response generation with actions
    4. Conversation state management (Redis)
    """

    # System prompts
    CHITCHAT_SYSTEM_PROMPT = """You are Pulse AI - a Vietnamese intelligent resident services assistant.
Be friendly, helpful, and respond naturally in Vietnamese.

## Your role
- 24/7 virtual concierge for residents
- Help with building management, billing, amenities, and support

## Response style
- Be polite and professional
- Keep responses concise but helpful
- Use natural Vietnamese language
- For greetings: welcome and offer assistance
- For questions: answer directly"""

    AGENTIC_SYSTEM_PROMPT = """You are Pulse AI - a Vietnamese intelligent resident services assistant.
You have access to tools for helping residents manage their apartment and services.

## Available Tools
You can call these tools to help users:
- get_bills: View utility bills
- get_bill_detail: View specific bill details
- make_payment: Pay a bill
- get_amenities: View available facilities
- book_amenity: Book a facility
- get_my_bookings: View user's bookings
- cancel_booking: Cancel a booking
- create_incident: Report an issue
- get_my_incidents: View reported issues
- get_packages: Check packages
- get_announcements: View building announcements

## Response Rules
1. ALWAYS respond in Vietnamese
2. Call tools when needed to get real data
3. After getting tool results, summarize them clearly
4. If parameters are missing, ask the user for clarification
5. Be helpful and suggest next actions

## User Context
- Name: {user_name}
- Unit: {unit}
- Available capabilities: {capabilities}"""

    STREAM_SYSTEM_PROMPT = """You are Pulse AI - a Vietnamese intelligent resident services assistant.
Respond naturally in Vietnamese. Be helpful and concise.

## User Context
- Name: {user_name}
- Unit: {unit}
- Available capabilities: {capabilities}

## Guidelines
1. Respond in Vietnamese only
2. Be helpful and professional
3. If you need data, call the appropriate tool
4. After tool results, summarize clearly"""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        state_manager: Optional[StateManager] = None,
        action_generator: Optional[ActionGenerator] = None,
    ):
        """Initialize CUX Orchestrator.

        Args:
            settings: Application settings
            state_manager: State manager for conversation history
            action_generator: Action button generator
        """
        self.settings = settings or Settings.get()
        self.state_manager = state_manager or StateManager(self.settings)
        self.action_generator = action_generator or ActionGenerator()

    async def process(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_token: Optional[str] = None,
        intent_type: str = "agentic_flow",
        attachments: Optional[List[Dict]] = None,
    ) -> ChatResponse:
        """Process a user message and return response.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload from JWT
            pulse_token: Pulse Backend token for API access
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

        # Get user capabilities
        capabilities = user.get("capabilities", [])

        # Handle based on intent type
        if intent_type == "chitchat":
            response = await self._handle_chitchat(message, session_id, history)
        elif intent_type == "tool_call":
            response = await self._handle_tool_call_direct(
                message, session_id, pulse_token
            )
        else:  # agentic_flow
            response = await self._handle_agentic_flow(
                message,
                session_id,
                user,
                pulse_token,
                capabilities,
                history,
                attachments,
            )

        # Add assistant message to history
        await self.state_manager.add_message(session_id, "assistant", response.message)

        return response

    async def process_stream(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_token: Optional[str] = None,
        intent_type: str = "agentic_flow",
        attachments: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a user message with streaming response.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload from JWT
            pulse_token: Pulse Backend token for API access
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

        capabilities = user.get("capabilities", [])

        # Build messages for LLM
        messages = self._build_messages(history, message, attachments)

        # Get filtered tools
        tools = get_tools_for_capabilities(capabilities)

        # Build system prompt
        system_prompt = self.STREAM_SYSTEM_PROMPT.format(
            user_name=user.get("name", "Cư dân"),
            unit=user.get("unit", "Resident"),
            capabilities=", ".join(capabilities) if capabilities else "basic",
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

            # If tools were called, execute them and continue
            if tool_calls_made and pulse_token:
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
                            pulse_token,
                            self.settings.pulse_backend_url,
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

        # Generate actions
        actions = self.action_generator.generate_actions(
            last_tool=last_tool_name,
            capabilities=capabilities,
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

    async def _handle_chitchat(
        self,
        message: str,
        session_id: str,
        history: List[Dict[str, str]],
    ) -> ChatResponse:
        """Handle chitchat messages directly with LLM.

        Args:
            message: User message
            session_id: Session identifier
            history: Conversation history

        Returns:
            ChatResponse
        """
        messages = [{"role": "system", "content": self.CHITCHAT_SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        async with OpenAIClient(self.settings) as client:
            response = await client.chat_completion(messages=messages)

            content = response.choices[0].message.content

            # Get default actions
            actions = self.action_generator.generate_actions()

            return ChatResponse(
                message=content,
                actions=actions,
                session_id=session_id,
            )

    async def _handle_agentic_flow(
        self,
        message: str,
        session_id: str,
        user: Dict[str, Any],
        pulse_token: Optional[str],
        capabilities: List[str],
        history: List[Dict[str, str]],
        attachments: Optional[List[Dict]],
    ) -> ChatResponse:
        """Handle agentic flow with tool calling.

        Args:
            message: User message
            session_id: Session identifier
            user: User payload
            pulse_token: Pulse Backend token
            capabilities: User capabilities
            history: Conversation history
            attachments: Optional attachments

        Returns:
            ChatResponse
        """
        # Build system prompt
        system_prompt = self.AGENTIC_SYSTEM_PROMPT.format(
            user_name=user.get("name", "Cư dân"),
            unit=user.get("unit", "Resident"),
            capabilities=", ".join(capabilities) if capabilities else "basic",
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Add attachments if provided
        if attachments:
            # For multimodal support
            user_message = {"role": "user", "content": []}
            user_message["content"].append({"type": "text", "text": message})

            for att in attachments:
                if att.get("type") == "image":
                    user_message["content"].append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{att['mime_type']};base64,{att['data']}"
                            },
                        }
                    )

            messages[-1] = user_message

        # Get filtered tools
        tools = get_tools_for_capabilities(capabilities)

        tool_calls_made = []
        last_tool_name = None

        async with OpenAIClient(self.settings) as client:
            # First LLM call
            response = await client.chat_completion(
                messages=messages,
                tools=tools,
            )

            assistant_message = response.choices[0].message

            # Check if tool calls were made
            if assistant_message.tool_calls:
                # Execute tools
                tool_results = []
                for tc in assistant_message.tool_calls:
                    tool_name = tc.function.name
                    params = json.loads(tc.function.arguments)
                    last_tool_name = tool_name

                    logger.info("executing_tool", tool=tool_name, params=params)

                    try:
                        result = await execute_tool(
                            tool_name,
                            params,
                            pulse_token,
                            self.settings.pulse_backend_url,
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
                        tool_results.append(
                            {
                                "tool_call_id": tc.id,
                                "role": "tool",
                                "content": json.dumps({"error": str(e)}),
                            }
                        )
                        tool_calls_made.append(
                            ToolCall(
                                tool=tool_name,
                                params=params,
                                result={"error": str(e)},
                            )
                        )

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

                # Second LLM call with tool results
                final_response = await client.chat_completion(messages=messages)
                content = final_response.choices[0].message.content
            else:
                content = assistant_message.content or "Tôi không hiểu yêu cầu của bạn. Bạn có thể diễn đạt lại không?"

        # Generate actions
        actions = self.action_generator.generate_actions(
            last_tool=last_tool_name,
            capabilities=capabilities,
        )

        return ChatResponse(
            message=content,
            actions=actions,
            session_id=session_id,
            tool_calls=tool_calls_made,
        )

    async def _handle_tool_call_direct(
        self,
        action: str,
        session_id: str,
        pulse_token: Optional[str],
    ) -> ChatResponse:
        """Handle direct tool call (from UI action button).

        Args:
            action: Action type to execute
            session_id: Session identifier
            pulse_token: Pulse Backend token

        Returns:
            ChatResponse
        """
        # Map action types to tool names
        action_to_tool = {
            "view_bills": ("get_bills", {}),
            "check_package": ("get_packages", {}),
            "view_bookings": ("get_my_bookings", {}),
            "view_incidents": ("get_my_incidents", {}),
            "report_incident": ("create_incident", {}),
            "book_amenity": ("get_amenities", {}),
            "view_amenities": ("get_amenities", {}),
        }

        if action not in action_to_tool:
            return ChatResponse(
                message="Tôi không thể thực hiện hành động này.",
                session_id=session_id,
            )

        tool_name, params = action_to_tool[action]

        try:
            result = await execute_tool(
                tool_name,
                params,
                pulse_token,
                self.settings.pulse_backend_url,
            )

            # Generate response based on tool result
            # This could be enhanced with LLM summarization
            message = self._summarize_tool_result(tool_name, result)

            return ChatResponse(
                message=message,
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
            logger.error("direct_tool_call_failed", action=action, error=str(e))
            return ChatResponse(
                message=f"Không thể thực hiện hành động: {str(e)}",
                session_id=session_id,
            )

    def _build_messages(
        self,
        history: List[Dict[str, str]],
        message: str,
        attachments: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Build messages list for LLM.

        Args:
            history: Conversation history
            message: Current user message
            attachments: Optional attachments

        Returns:
            List of message dicts
        """
        messages = list(history)

        if attachments:
            # Multimodal message
            content = [{"type": "text", "text": message}]
            for att in attachments:
                if att.get("type") == "image" and att.get("data"):
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{att['mime_type']};base64,{att['data']}"
                            },
                        }
                    )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": message})

        return messages

    def _summarize_tool_result(
        self,
        tool_name: str,
        result: Any,
    ) -> str:
        """Generate a summary of tool result (simple version without LLM).

        Args:
            tool_name: Name of the tool that was executed
            result: Tool execution result

        Returns:
            Summary string
        """
        if tool_name == "get_bills":
            bills = result if isinstance(result, list) else []
            if not bills:
                return "Bạn không có hóa đơn nào."
            unpaid = [b for b in bills if b.get("status") == "Unpaid"]
            if unpaid:
                total = sum(b.get("amount", 0) for b in unpaid)
                return f"Bạn có {len(unpaid)} hóa đơn chưa thanh toán với tổng số {total:,.0f}đ."
            return f"Bạn có {len(bills)} hóa đơn đã thanh toán."

        if tool_name == "get_packages":
            packages = result if isinstance(result, list) else []
            if not packages:
                return "Hiện tại không có bưu kiện nào cho căn hộ của bạn."
            return f"Bạn có {len(packages)} bưu kiện."

        if tool_name == "get_my_bookings":
            bookings = result if isinstance(result, list) else []
            if not bookings:
                return "Bạn chưa có đặt chỗ nào."
            return f"Bạn có {len(bookings)} đặt chỗ."

        if tool_name == "get_amenities":
            amenities = result if isinstance(result, list) else []
            if not amenities:
                return "Không có tiện ích nào để đặt."
            return f"Có {len(amenities)} tiện ích có sẵn để đặt."

        # Default fallback
        return "Đã thực hiện thành công."
