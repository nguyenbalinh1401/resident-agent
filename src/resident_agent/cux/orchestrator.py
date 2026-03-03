"""CUX Orchestrator - Central coordination for intent detection, allowance checking, and workflow routing.

This module implements the LLM-first approach for response generation,
combining intent detection with context-aware response creation.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import json
import random
import structlog

from openai import AsyncOpenAI

from .intent_detector import (
    HybridIntentDetector,
    IntentType,
    IntentCategory,
    DetectedIntent,
)
from .allowance_client import AllowanceClient
from .state_manager import ConversationStateManager
from ..core.config import Settings
from ..core.openai_client import OpenAIClient
from ..schemas.chat_schemas import ChatResponse, ActionButton, ActionStyle

logger = structlog.get_logger()


@dataclass
class CuxDecision:
    """Output of CUX Orchestrator processing."""
    decision_type: str  # "proceed", "refusal", "clarification", "confirmation"
    intent: DetectedIntent
    allowed: bool
    message_to_client: Optional[str] = None
    workflow_to_trigger: Optional[str] = None
    workflow_params: Optional[Dict[str, Any]] = None
    clarification_options: Optional[List[Dict]] = None
    confirmation_details: Optional[Dict] = None
    suggestions: Optional[List[Dict]] = None
    actions: List[ActionButton] = field(default_factory=list)


class CuxOrchestrator:
    """Central orchestration for CUX flow.

    This orchestrator coordinates:
    1. Intent detection (using hybrid approach)
    2. Allowance checking (user permissions)
    3. State management (conversation context)
    4. Workflow routing (to LangGraph)
    5. LLM response generation
    """

    # Chitchat responses for quick replies
    CHITCHAT_RESPONSES = {
        IntentType.GREETING: [
            "Xin chào! Tôi là Pulse AI. Tôi có thể giúp gì cho bạn hôm nay?",
            "Chào bạn! Bạn cần hỗ trợ gì về dịch vụ tòa nhà?",
            "Xin chào! Rất vui được phục vụ bạn. Bạn muốn hỗ trợ gì?",
        ],
        IntentType.FAREWELL: [
            "Tạm biệt! Chúc bạn một ngày tốt lành!",
            "Hẹn gặp lại! Đừng ngại liên hệ nếu cần hỗ trợ.",
            "Tạm biệt! Chúc bạn sức khỏe!",
        ],
        IntentType.THANKS: [
            "Không có gì! Rất vui được phục vụ bạn.",
            "Cảm ơn bạn đã sử dụng Pulse!",
            "Rất mong được giúp đỡ bạn!",
        ],
        IntentType.SMALL_TALK: [
            "Tôi là Pulse AI - trợ lý ảo 24/7 của bạn. Tôi có thể giúp gì?",
            "Tôi hoạt động để hỗ trợ cư dân như bạn. Bạn cần giúp gì?",
        ],
    }

    # LLM System Prompt for response generation
    LLM_SYSTEM_PROMPT = """You are Pulse AI - a Vietnamese intelligent resident services assistant.
Generate responses with suggested actions based on user's available capabilities.

## User's Available Capabilities
{capabilities_list}

## User Context
- Name: {user_name}
- Unit: {unit}
- Role: {role}

## Response Rules
1. ALWAYS respond in Vietnamese
2. Be polite, professional, and helpful (concierge-level service)
3. Suggest 2-4 relevant actions based on:
   - The user's query context
   - Their available capabilities ONLY (don't suggest actions they can't do)
4. For greetings/unclear queries: show service menu
5. For specific queries: answer first, then suggest follow-ups
6. Escalate emergency requests (fire, medical, security) immediately

## Response Format (JSON only)
{{
  "answer": "Your response in Vietnamese",
  "actions": [
    {{
      "label": "🎯 Button text",
      "action": "capability_id",
      "params": {{"key": "value"}},
      "style": "primary|secondary|outline"
    }}
  ],
  "intent": "detected_intent",
  "needs_tool": true/false
}}"""

    def __init__(
        self,
        intent_detector: Optional[HybridIntentDetector] = None,
        allowance_client: Optional[AllowanceClient] = None,
        state_manager: Optional[ConversationStateManager] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize CUX Orchestrator.

        Args:
            intent_detector: Intent detection component
            allowance_client: Allowance checking component
            state_manager: Conversation state manager
            settings: Application settings
        """
        self.intent_detector = intent_detector or HybridIntentDetector()
        self.allowance_client = allowance_client or AllowanceClient()
        self.state_manager = state_manager or ConversationStateManager()
        self.settings = settings or Settings.get()

        # LangGraph workflow mappings
        from ..workflows.registry import WorkflowName
        self.intent_to_workflow = {
            IntentType.INCIDENT_REPORT: WorkflowName.INCIDENT_REPORT,
            IntentType.PACKAGE_CHECK: WorkflowName.PACKAGE_CHECK,
            IntentType.BILL_VIEW: WorkflowName.BILL_VIEW,
            IntentType.AMENITY_BOOK: WorkflowName.AMENITY_BOOK,
            IntentType.SERVICE_REQUEST: WorkflowName.SERVICE_REQUEST,
            IntentType.INCIDENT_MANAGEMENT: WorkflowName.INCIDENT_MANAGEMENT,
            IntentType.BOOKING_FLOW: WorkflowName.BOOKING_FLOW,
            IntentType.PAYMENT_FLOW: WorkflowName.PAYMENT_FLOW,
        }

    async def process(
        self,
        session_id: str,
        user_id: str,
        message: str
    ) -> ChatResponse:
        """Main entry point for CUX processing.

        Args:
            session_id: Session identifier
            user_id: User identifier
            message: User message

        Returns:
            ChatResponse with message and suggested actions
        """
        logger.info(
            "cux_process_start",
            session_id=session_id,
            user_id=user_id,
            message_preview=message[:50]
        )

        # 1. Add user message to history
        await self.state_manager.add_message_to_history(
            session_id, "user", message
        )

        # 2. Detect intent
        conversation_history = await self._get_history_strings(session_id)
        intent = await self.intent_detector.detect(message, conversation_history)

        logger.info(
            "intent_detected",
            intent_type=intent.intent_type.value,
            category=intent.category.value,
            confidence=intent.confidence,
            method=intent.detection_method
        )

        # 3. Handle CHITCHAT - no allowance check needed
        if intent.category == IntentCategory.CHITCHAT:
            response = await self._handle_chitchat(session_id, intent)
            await self.state_manager.add_message_to_history(
                session_id, "assistant", response.message
            )
            return response

        # 4. Get user allowance
        allowance = await self.allowance_client.get_allowance(user_id)

        # 5. Check capability
        if intent.required_capability:
            if not self._check_allowance(intent.required_capability, allowance):
                response = await self._handle_refusal(session_id, intent, allowance)
                await self.state_manager.add_message_to_history(
                    session_id, "assistant", response.message
                )
                return response

        # 6. Check if clarification needed
        if self._needs_clarification(intent):
            response = await self._handle_clarification(session_id, intent)
            await self.state_manager.add_message_to_history(
                session_id, "assistant", response.message
            )
            return response

        # 7. Proceed with action - generate LLM response
        response = await self._generate_response(
            session_id, user_id, intent, allowance, message
        )

        # Add assistant response to history
        await self.state_manager.add_message_to_history(
            session_id, "assistant", response.message
        )

        return response

    async def _handle_chitchat(
        self,
        session_id: str,
        intent: DetectedIntent
    ) -> ChatResponse:
        """Handle chitchat intents directly."""
        responses = self.CHITCHAT_RESPONSES.get(intent.intent_type, [])
        response_text = random.choice(responses) if responses else "Tôi có thể giúp gì cho bạn?"

        # Update state
        await self.state_manager.update_state(session_id, {
            "last_intent": intent.intent_type.value,
            "last_category": intent.category.value,
        })

        # Build action suggestions for chitchat
        actions = self._get_default_actions()

        return ChatResponse(
            message=response_text,
            actions=actions,
            intent=intent.intent_type.value,
            session_id=session_id
        )

    async def _handle_refusal(
        self,
        session_id: str,
        intent: DetectedIntent,
        allowance: Dict
    ) -> ChatResponse:
        """Handle capability refusal with helpful alternatives."""
        alternatives = self.allowance_client.suggest_alternatives(
            intent.required_capability,
            allowance
        )

        message = f"Xin lỗi, bạn không có quyền thực hiện {intent.required_capability}."
        if alternatives:
            alt_labels = ", ".join([a["label"] for a in alternatives])
            message += f" Tuy nhiên, bạn có thể: {alt_labels}"

        actions = [
            ActionButton(
                id=alt["capability"],
                label=alt["label"],
                action_type=alt["capability"],
                style=ActionStyle.SECONDARY
            )
            for alt in alternatives
        ]

        return ChatResponse(
            message=message,
            actions=actions,
            intent=intent.intent_type.value,
            session_id=session_id
        )

    async def _handle_clarification(
        self,
        session_id: str,
        intent: DetectedIntent
    ) -> ChatResponse:
        """Request clarification from user."""
        options = self._generate_clarification_options(intent)

        message = "Tôi cần thêm thông tin để hỗ trợ bạn tốt hơn:"
        actions = [
            ActionButton(
                id=opt["id"],
                label=opt["label"],
                action_type=opt.get("action", opt["id"]),
                params=opt.get("params", {}),
                style=ActionStyle.OUTLINE
            )
            for opt in options
        ]

        return ChatResponse(
            message=message,
            actions=actions,
            intent=intent.intent_type.value,
            session_id=session_id
        )

    async def _generate_response(
        self,
        session_id: str,
        user_id: str,
        intent: DetectedIntent,
        allowance: Dict,
        user_message: str
    ) -> ChatResponse:
        """Generate LLM-powered response with actions."""
        try:
            client = OpenAIClient.get(self.settings)

            # Build context
            capabilities = allowance.get("allowed_capabilities", [])
            caps_list = "\n".join([f"- {cap}" for cap in capabilities])

            system_prompt = self.LLM_SYSTEM_PROMPT.format(
                capabilities_list=caps_list,
                user_name=user_id,
                unit="Resident",
                role=allowance.get("roles", ["resident"])[0]
            )

            response = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500
            )

            result = json.loads(response.choices[0].message.content)

            # Parse actions
            actions = []
            for action_data in result.get("actions", []):
                actions.append(ActionButton(
                    id=action_data.get("action", str(random.randint(1000, 9999))),
                    label=action_data.get("label", "Action"),
                    action_type=action_data.get("action", ""),
                    params=action_data.get("params", {}),
                    style=ActionStyle(action_data.get("style", "secondary"))
                ))

            return ChatResponse(
                message=result.get("answer", "Xin lỗi, tôi không thể xử lý yêu cầu này lúc này."),
                actions=actions,
                intent=intent.intent_type.value,
                session_id=session_id
            )

        except Exception as e:
            logger.error("llm_response_failed", error=str(e))
            # Fallback response
            return ChatResponse(
                message="Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.",
                actions=self._get_default_actions(),
                intent=intent.intent_type.value,
                session_id=session_id
            )

    def _check_allowance(self, capability: str, allowance: Dict) -> bool:
        """Check if user has required capability."""
        allowed = allowance.get("allowed_capabilities", [])
        roles = allowance.get("roles", [])

        # Admin has all capabilities
        if "admin" in roles or "*" in allowed:
            return True

        return capability in allowed

    def _needs_clarification(self, intent: DetectedIntent) -> bool:
        """Determine if clarification is needed."""
        # Low confidence needs clarification
        if intent.confidence < 0.6:
            return True

        # Agentic flows without enough slots need clarification
        if intent.category == IntentCategory.AGENTIC_FLOW:
            required_slots = {"facility", "timeframe"}
            if not required_slots.issubset(set(intent.slots.keys())):
                return True

        return False

    def _generate_clarification_options(self, intent: DetectedIntent) -> List[Dict]:
        """Generate clarification options based on intent."""
        if intent.category == IntentCategory.TOOL_CALL:
            return [
                {"id": "1", "label": "🔧 Báo sự cố", "action": "report_incident"},
                {"id": "2", "label": "📦 Kiểm tra bưu kiện", "action": "check_package"},
                {"id": "3", "label": "💳 Xem hóa đơn", "action": "view_bills"},
                {"id": "4", "label": "🏊 Đặt chỗ tiện ích", "action": "book_amenity"},
            ]
        return [
            {"id": "1", "label": "Tiếp tục", "action": "continue"},
            {"id": "2", "label": "Hủy bỏ", "action": "cancel"},
        ]

    def _get_default_actions(self) -> List[ActionButton]:
        """Get default action suggestions."""
        return [
            ActionButton(
                id="report_incident",
                label="🔧 Báo sự cố",
                action_type="report_incident",
                style=ActionStyle.PRIMARY
            ),
            ActionButton(
                id="check_package",
                label="📦 Kiểm tra bưu kiện",
                action_type="check_package",
                style=ActionStyle.SECONDARY
            ),
            ActionButton(
                id="view_bills",
                label="💳 Xem hóa đơn",
                action_type="view_bills",
                style=ActionStyle.SECONDARY
            ),
            ActionButton(
                id="book_amenity",
                label="🏊 Đặt chỗ tiện ích",
                action_type="book_amenity",
                style=ActionStyle.OUTLINE
            ),
        ]

    async def _get_history_strings(self, session_id: str) -> List[str]:
        """Get conversation history as list of strings."""
        history = await self.state_manager.get_history(session_id, limit=5)
        return [f"{msg['role']}: {msg['content']}" for msg in history]
