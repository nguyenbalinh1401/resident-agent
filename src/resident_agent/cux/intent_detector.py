"""Hybrid intent detection with rule-based, ML, and LLM approaches.

Implements a cascading detection strategy:
1. Rule-based (instant, free) - handles 60-70% of requests
2. ML classifier (fast, cheap) - handles 20-25% of requests
3. LLM fallback (slow, expensive) - handles 5-10% of requests
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import re
import json
import structlog

from ..core.config import Settings
from ..core.openai_client import OpenAIClient

logger = structlog.get_logger()


class IntentType(Enum):
    """Types of intents the system can detect."""
    # Chitchat
    GREETING = "greeting"
    FAREWELL = "farewell"
    THANKS = "thanks"
    SMALL_TALK = "small_talk"

    # General Ask
    POLICY_QUESTION = "policy_question"
    SERVICE_INFO = "service_info"
    CONTACT_INFO = "contact_info"
    OPERATING_HOURS = "operating_hours"

    # Tool Call - Resident Services
    INCIDENT_REPORT = "incident_report"
    PACKAGE_CHECK = "package_check"
    BILL_VIEW = "bill_view"
    AMENITY_BOOK = "amenity_book"
    SERVICE_REQUEST = "service_request"

    # Agentic - Multi-step workflows
    INCIDENT_MANAGEMENT = "incident_management"
    BOOKING_FLOW = "booking_flow"
    PAYMENT_FLOW = "payment_flow"

    # Fallback
    UNKNOWN = "unknown"


class IntentCategory(Enum):
    """Categories of intents."""
    CHITCHAT = "chitchat"
    GENERAL_ASK = "general_ask"
    TOOL_CALL = "tool_call"
    AGENTIC_FLOW = "agentic_flow"
    UNKNOWN = "unknown"


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    intent_type: IntentType
    category: IntentCategory
    confidence: float
    slots: Dict[str, str]
    required_capability: Optional[str]
    detection_method: str  # "rule", "ml", "llm"


class RuleBasedDetector:
    """Fast pattern matching for common intents.

    Uses pre-compiled regex patterns for instant detection.
    Handles greetings, common commands, and known patterns.
    """

    # Greeting patterns (multi-language)
    GREETING_PATTERNS = [
        r"^(xin\s*)?chào",
        r"^hello",
        r"^hi\b",
        r"^hey\b",
        r"^chào\s+(bạn|anh|chị|em)",
        r"^good\s*(morning|afternoon|evening)",
    ]

    # Farewell patterns
    FAREWELL_PATTERNS = [
        r"^(tạm\s*biệt|bye|goodbye|see\s*you)",
        r"^hẹn\s*gặp\s*lại",
    ]

    # Thanks patterns
    THANKS_PATTERNS = [
        r"(cảm\s*ơn|thank|thanks)",
    ]

    # Tool trigger patterns with slot extraction
    TOOL_PATTERNS = {
        IntentType.INCIDENT_REPORT: [
            (r"(báo|report|sự\s*cố|hỏng)\s+(?:tại\s+)?(.+)", ["action", "location"]),
            (r"(đèn|điện|nước|máy\s*lạnh|hệ\s*thống|hành\s*lang)\s+(hỏng|chạy|sự\s*cô)", ["facility", "issue"]),
            (r"(.+)\s+(hỏng|sự\s*cố|chạy)", ["location", "issue"]),
            (r"(bàn\s*giao|bếp|phòng\s*ngủ|nhà\s*vệ\ssinh)\s+(hỏng|sự\s*cô)", ["location", "issue"]),
        ],
        IntentType.PACKAGE_CHECK: [
            (r"(kiểm\s*tra|check|bưu\s*kiện|package|hàng)", ["action"]),
            (r"(có|nhận\s*được)\s+(hàng|bưu\s*kiện)\s+(chưa| chưa\?)", ["status", "type"]),
        ],
        IntentType.BILL_VIEW: [
            (r"(xem|check|giá|tiền)\s+(hóa\s*đơn|bill|phí)", ["action", "type"]),
            (r"(phí\s*quản\s*lý|điện|nước)\s+(tháng\s*nay|nay)", ["type", "period"]),
        ],
        IntentType.AMENITY_BOOK: [
            (r"(đặt|book|đặt\s*chỗ)\s+(bể\s*bơi|gym|sân|tennis|bbq)", ["action", "facility"]),
            (r"(check|kiểm\s*tra)\s+(trống\s*chỗ|available)", ["action", "status"]),
        ],
        IntentType.SERVICE_REQUEST: [
            (r"(đăng\s*ký|xin|yêu\s*cầu)\s+(thẻ\s*cư\s*dân|thẻ\s*đón|thẻ\s*gui|xe)", ["action", "service_type"]),
            (r"(thủ\s*tục|hồ\s*sơ)\s+(cư\s*dân|đăng\s*ký)", ["type", "action"]),
        ],
    }

    # Agentic patterns (complex multi-step)
    AGENTIC_PATTERNS = {
        IntentType.INCIDENT_MANAGEMENT: [
            r"(sửa\s*chữa|bảo\s*trì)\s+(thiết\s*bị|facility)",
            r"(theo\s*dõi|status)\s+(phiếu\s*sửa\s*chữa|ticket)",
        ],
        IntentType.BOOKING_FLOW: [
            r"(kiểm\s*tra|xem)\s+(lịch\s*trống|availability)\s+và\s*(đặt|book)",
            r"(đặt\s*lịch|schedule)\s+(sử\sdụng|dùng)",
        ],
        IntentType.PAYMENT_FLOW: [
            r"(xem\s*chi\s*tiết|detail)\s+và\s*(thanh\s*toán|pay)",
            r"(lịch\s*sử|history)\s+(thanh\s*toán|payment)",
        ],
    }

    # Question patterns for general ask
    QUESTION_PATTERNS = [
        r"^(what|when|where|why|how|who|which)",
        r"(là\s*gì|là\s*sao|như\s*thế\s*nào)",
        r"^(giải\s*thích|explain)",
        r"^(so\s*sánh|compare)",
    ]

    def __init__(self):
        """Initialize and pre-compile all regex patterns."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        self.compiled_greetings = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.GREETING_PATTERNS
        ]
        self.compiled_farewells = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.FAREWELL_PATTERNS
        ]
        self.compiled_thanks = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.THANKS_PATTERNS
        ]
        self.compiled_questions = [
            re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.QUESTION_PATTERNS
        ]

        self.compiled_tools = {}
        for intent_type, patterns in self.TOOL_PATTERNS.items():
            self.compiled_tools[intent_type] = [
                (re.compile(p, re.IGNORECASE | re.UNICODE), slots)
                for p, slots in patterns
            ]

        self.compiled_agentic = {}
        for intent_type, patterns in self.AGENTIC_PATTERNS.items():
            self.compiled_agentic[intent_type] = [
                re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns
            ]

    def detect(self, message: str) -> Optional[DetectedIntent]:
        """Attempt rule-based intent detection.

        Args:
            message: User message text

        Returns:
            DetectedIntent if confident match found, None otherwise
        """
        message = message.strip()

        # 1. Check greetings (highest priority for short messages)
        if len(message) < 50:
            for pattern in self.compiled_greetings:
                if pattern.search(message):
                    return DetectedIntent(
                        intent_type=IntentType.GREETING,
                        category=IntentCategory.CHITCHAT,
                        confidence=0.95,
                        slots={},
                        required_capability=None,
                        detection_method="rule"
                    )

        # 2. Check farewells
        for pattern in self.compiled_farewells:
            if pattern.search(message):
                return DetectedIntent(
                    intent_type=IntentType.FAREWELL,
                    category=IntentCategory.CHITCHAT,
                    confidence=0.95,
                    slots={},
                    required_capability=None,
                    detection_method="rule"
                )

        # 3. Check thanks
        for pattern in self.compiled_thanks:
            if pattern.search(message):
                return DetectedIntent(
                    intent_type=IntentType.THANKS,
                    category=IntentCategory.CHITCHAT,
                    confidence=0.90,
                    slots={},
                    required_capability=None,
                    detection_method="rule"
                )

        # 4. Check agentic patterns (before tool patterns - more specific)
        for intent_type, patterns in self.compiled_agentic.items():
            for pattern in patterns:
                if pattern.search(message):
                    return DetectedIntent(
                        intent_type=intent_type,
                        category=IntentCategory.AGENTIC_FLOW,
                        confidence=0.85,
                        slots=self._extract_agentic_slots(message),
                        required_capability=self._get_capability(intent_type),
                        detection_method="rule"
                    )

        # 5. Check tool patterns with slot extraction
        for intent_type, compiled_patterns in self.compiled_tools.items():
            for pattern, slot_names in compiled_patterns:
                match = pattern.search(message)
                if match:
                    slots = {}
                    for i, slot_name in enumerate(slot_names):
                        if i < len(match.groups()):
                            slots[slot_name] = match.group(i + 1)

                    return DetectedIntent(
                        intent_type=intent_type,
                        category=IntentCategory.TOOL_CALL,
                        confidence=0.85,
                        slots=slots,
                        required_capability=self._get_capability(intent_type),
                        detection_method="rule"
                    )

        # 6. Check if it's a general question
        for pattern in self.compiled_questions:
            if pattern.search(message):
                return DetectedIntent(
                    intent_type=IntentType.POLICY_QUESTION,
                    category=IntentCategory.GENERAL_ASK,
                    confidence=0.70,  # Lower confidence, might need LLM
                    slots={"question": message},
                    required_capability="GENERAL_QA",
                    detection_method="rule"
                )

        # No confident match - return None for fallback
        return None

    def _extract_agentic_slots(self, message: str) -> Dict[str, str]:
        """Extract entities for agentic flows."""
        slots = {"raw_query": message}

        # Extract facility/location names
        facility_patterns = [
            (r"(bể\s*bơi|pool)", "swimming_pool"),
            (r"(gym|fitness)", "gym"),
            (r"(sân\s*tennis)", "tennis_court"),
            (r"(bbq|nướng)", "bbq_area"),
        ]
        for pattern, value in facility_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                slots["facility"] = value

        # Extract time references
        time_patterns = [
            (r"(hôm\s*nay|today)", "today"),
            (r"(ngày\s*mai|tomorrow)", "tomorrow"),
            (r"(tuần|week)", "week"),
            (r"(tháng|month)", "month"),
        ]
        for pattern, value in time_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                slots["timeframe"] = value
                break

        return slots

    def _get_capability(self, intent_type: IntentType) -> str:
        """Map intent type to required capability."""
        mapping = {
            IntentType.INCIDENT_REPORT: "REPORT_INCIDENT",
            IntentType.PACKAGE_CHECK: "CHECK_PACKAGE",
            IntentType.BILL_VIEW: "VIEW_BILLS",
            IntentType.AMENITY_BOOK: "BOOK_AMENITY",
            IntentType.SERVICE_REQUEST: "SERVICE_REQUEST",
            IntentType.INCIDENT_MANAGEMENT: "INCIDENT_MANAGEMENT",
            IntentType.BOOKING_FLOW: "BOOKING_FLOW",
            IntentType.PAYMENT_FLOW: "PAYMENT_FLOW",
        }
        return mapping.get(intent_type, "GENERAL")


class LLMIntentDetector:
    """LLM-based intent detection for complex queries.

    Used as fallback when rule-based detection fails.
    """

    SYSTEM_PROMPT = """You are an intent classification system for a Vietnamese resident services assistant.
Analyze the user message and respond with JSON only.

Available intents:
- CHITCHAT: greeting, farewell, thanks, small_talk
- GENERAL_ASK: policy_question, service_info, contact_info, operating_hours
- TOOL_CALL: incident_report, package_check, bill_view, amenity_book, service_request
- AGENTIC_FLOW: incident_management, booking_flow, payment_flow

Required capabilities (for TOOL_CALL and AGENTIC_FLOW):
- REPORT_INCIDENT: Report maintenance issues
- CHECK_PACKAGE: Check package status
- VIEW_BILLS: View unpaid bills
- BOOK_AMENITY: Book facilities
- SERVICE_REQUEST: Request resident services

Response format:
{
  "intent_type": "<specific intent>",
  "category": "<CHITCHAT|GENERAL_ASK|TOOL_CALL|AGENTIC_FLOW>",
  "confidence": <0.0-1.0>,
  "required_capability": "<capability or null>",
  "slots": {
    "key": "value"
  },
  "reasoning": "<brief explanation>"
}"""

    def __init__(self, settings: Settings = None):
        """Initialize LLM detector.

        Args:
            settings: Application settings (optional, uses default if not provided)
        """
        self.settings = settings or Settings.get()

    async def detect(
        self,
        message: str,
        conversation_history: Optional[List[str]] = None
    ) -> DetectedIntent:
        """Use LLM for intent detection.

        Args:
            message: User message text
            conversation_history: Recent messages for context

        Returns:
            DetectedIntent with LLM-detected intent
        """
        client = OpenAIClient.get(self.settings)

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        # Add conversation context if available
        if conversation_history:
            context = "\n".join([f"- {msg}" for msg in conversation_history[-3:]])
            messages.append({
                "role": "user",
                "content": f"Recent conversation:\n{context}\n\nCurrent message: {message}"
            })
        else:
            messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )

        result = json.loads(response.choices[0].message.content)

        intent_type_str = result["intent_type"]
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        try:
            category = IntentCategory(result["category"])
        except ValueError:
            category = IntentCategory.UNKNOWN

        return DetectedIntent(
            intent_type=intent_type,
            category=category,
            confidence=result["confidence"],
            slots=result.get("slots", {}),
            required_capability=result.get("required_capability"),
            detection_method="llm"
        )


class HybridIntentDetector:
    """Cascading intent detection with cost optimization.

    Detection flow:
    1. Rule-based (instant, free) - handles 60-70% of requests
    2. ML classifier (fast, cheap) - handles 20-25% of requests
    3. LLM fallback (slow, expensive) - handles 5-10% of requests
    """

    def __init__(
        self,
        rule_detector: Optional[RuleBasedDetector] = None,
        llm_detector: Optional[LLMIntentDetector] = None,
        llm_threshold: float = 0.6
    ):
        """Initialize hybrid detector.

        Args:
            rule_detector: Rule-based detector instance
            llm_detector: LLM-based detector instance
            llm_threshold: Minimum confidence to avoid LLM fallback
        """
        self.rule_detector = rule_detector or RuleBasedDetector()
        self.llm_detector = llm_detector
        self.llm_threshold = llm_threshold

    async def detect(
        self,
        message: str,
        conversation_history: Optional[List[str]] = None,
        force_llm: bool = False
    ) -> DetectedIntent:
        """Detect intent using cascading approach.

        Args:
            message: User message text
            conversation_history: Recent messages for context
            force_llm: Skip rule-based and use LLM directly

        Returns:
            DetectedIntent with highest confidence
        """
        # Force LLM for complex queries
        if force_llm and self.llm_detector:
            return await self.llm_detector.detect(message, conversation_history)

        # Step 1: Try rule-based (instant)
        result = self.rule_detector.detect(message)
        if result and result.confidence >= 0.8:
            logger.debug(
                "rule_based_detection",
                intent=result.intent_type.value,
                confidence=result.confidence
            )
            return result

        # Step 2: Use lower confidence result if available
        if result and result.confidence >= self.llm_threshold:
            return result

        # Step 3: Fallback to LLM (expensive but accurate)
        if self.llm_detector:
            logger.debug("llm_fallback", message=message[:50])
            return await self.llm_detector.detect(message, conversation_history)

        # If no LLM detector, return rule result or unknown
        if result:
            return result

        return DetectedIntent(
            intent_type=IntentType.UNKNOWN,
            category=IntentCategory.UNKNOWN,
            confidence=0.0,
            slots={},
            required_capability=None,
            detection_method="fallback"
        )
