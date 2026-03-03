# CUX Orchestrator - Detailed Integration Guide

## 📋 Overview

Tài liệu này mô tả chi tiết implementation của **CUX Orchestrator** - thành phần trung tâm điều phối intent detection, allowance checking, và conversation state management trong InferFlow Protocol v2.

---

## 🎯 CUX Orchestrator Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                      CUX ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INTENT DETECTION                                            │
│     ├─ Parse user message                                       │
│     ├─ Classify intent type                                     │
│     ├─ Extract slots/entities                                   │
│     └─ Determine required capability                            │
│                                                                 │
│  2. ALLOWANCE CHECK                                             │
│     ├─ Get user allowance from service                          │
│     ├─ Match capability vs allowance                            │
│     └─ Generate safe refusal if not allowed                     │
│                                                                 │
│  3. CONVERSATION STATE                                          │
│     ├─ Load current state                                       │
│     ├─ Update state after actions                               │
│     └─ Determine if clarification needed                        │
│                                                                 │
│  4. FLOW ROUTING                                                │
│     ├─ Route to appropriate workflow                            │
│     ├─ Generate next suggestions                                │
│     └─ Handle multi-turn conversations                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Intent Detection Deep Dive

### Intent Classification Hierarchy

```
Intent Types
├── CHITCHAT (General conversation)
│   ├── GREETING          → "xin chào", "hello", "hi"
│   ├── FAREWELL          → "tạm biệt", "bye"
│   ├── THANKS            → "cảm ơn", "thank you"
│   ├── SMALL_TALK        → "bạn khỏe không?", "how are you?"
│   └── OFF_TOPIC         → Unrelated to domain
│
├── GENERAL_ASK (Simple Q&A, no tools needed)
│   ├── POLICY_QUESTION   → "Quy định về bể bơi?"
│   ├── SERVICE_INFO      → "Dịch vụ có sẵn?"
│   ├── CONTACT_INFO      → "Liên hệ ban quản lý"
│   └── OPERATING_HOURS   → "Giờ mở cửa gym?"
│
├── TOOL_CALL (Single tool invocation)
│   ├── INCIDENT_REPORT   → "Báo sự cố điện"
│   ├── PACKAGE_CHECK     → "Kiểm tra bưu kiện"
│   ├── BILL_VIEW         → "Xem hóa đơn tháng này"
│   ├── AMENITY_BOOK      → "Đặt sân tennis"
│   └── SERVICE_REQUEST   → "Đăng ký thẻ cư dân"
│
└── AGENTIC_FLOW (Multi-step workflows)
    ├── INCIDENT_MANAGEMENT → "Báo cáo và theo dõi sửa chữa"
    ├── BOOKING_FLOW       → "Kiểm tra và đặt chỗ tiện ích"
    ├── PAYMENT_FLOW       → "Xem và thanh toán hóa đơn"
    └── COMPLEX_REQUEST    → Multiple services + reasoning
```

### Intent Detection Strategies

#### Strategy 1: Rule-Based (Fast, Low Cost)

**Pros**: Instant, no API cost, deterministic
**Cons**: Limited coverage, maintenance burden
**Use for**: Greetings, common patterns, domain keywords

```python
# src/be_inferflow_protocol/cux/intent_detector.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Tuple
import re

class IntentType(Enum):
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
    CHITCHAT = "chitchat"
    GENERAL_ASK = "general_ask"
    TOOL_CALL = "tool_call"
    AGENTIC_FLOW = "agentic_flow"
    UNKNOWN = "unknown"

@dataclass
class DetectedIntent:
    intent_type: IntentType
    category: IntentCategory
    confidence: float
    slots: Dict[str, str]
    required_capability: Optional[str]
    detection_method: str  # "rule", "ml", "llm"

class RuleBasedDetector:
    """Fast pattern matching for common intents"""
    
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
            (r"(đèn|điện|nước|máy\s*lạnh|hệ\s*thống)\s+(hỏng|chạy|sự\s*cô)", ["facility", "issue"]),
            (r"(bàn\s*giao|bếp|phòng\s*ngủ|nhà\s*vệ\s*sinh)\s+(hỏng|sự\s*cô)", ["location", "issue"]),
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
            (r"(check|kiểm\s*tra)\s+(trống\s*chỗ|available)\s+(.+", ["action", "status", "facility"]),
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
            r"(đặt\s*lịch|schedule)\s+(sử\dung|dùng)\s+(.+\s*)+(vào|lúc)",
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
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        self.compiled_greetings = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.GREETING_PATTERNS]
        self.compiled_farewells = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.FAREWELL_PATTERNS]
        self.compiled_thanks = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.THANKS_PATTERNS]
        self.compiled_questions = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.QUESTION_PATTERNS]
        
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
        """
        Attempt rule-based detection.
        Returns None if no confident match (fallback to ML/LLM needed).
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
                    intent_type=IntentType.FACTUAL_QUESTION,
                    category=IntentCategory.GENERAL_ASK,
                    confidence=0.70,  # Lower confidence, might need LLM
                    slots={"question": message},
                    required_capability="GENERAL_QA",
                    detection_method="rule"
                )
        
        # No confident match - return None for fallback
        return None
    
    def _extract_agentic_slots(self, message: str) -> Dict[str, str]:
        """Extract entities for agentic flows"""
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
        """Map intent to required capability"""
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
```

#### Strategy 2: ML-Based (Fast, Medium Cost)

**Pros**: Good accuracy, fast inference, handles variations
**Cons**: Training data needed, may miss edge cases
**Use for**: Intent classification when rules don't match

```python
# src/be_inferflow_protocol/cux/ml_intent_classifier.py

from typing import Optional, List
import numpy as np
from dataclasses import dataclass

class MLIntentClassifier:
    """
    Lightweight ML classifier for intent detection.
    Uses pre-trained sentence embeddings + simple classifier.
    
    Options:
    1. sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2)
    2. FastText for Vietnamese
    3. ONNX-exported small transformer
    """
    
    def __init__(self, model_path: str = None):
        self.model = None
        self.label_encoder = None
        self._load_model(model_path)
    
    def _load_model(self, model_path: str):
        """Load pre-trained classifier"""
        # Option 1: Sentence Transformers + Logistic Regression
        try:
            from sentence_transformers import SentenceTransformer
            import joblib
            
            self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            if model_path:
                self.classifier = joblib.load(f"{model_path}/classifier.joblib")
                self.label_encoder = joblib.load(f"{model_path}/label_encoder.joblib")
            else:
                # Use default/fallback
                self.classifier = None
        except ImportError:
            self.embedder = None
            self.classifier = None
    
    def classify(self, message: str) -> Optional[DetectedIntent]:
        """
        Classify intent using ML model.
        Returns None if model not available or low confidence.
        """
        if not self.embedder or not self.classifier:
            return None
        
        # Get embedding
        embedding = self.embedder.encode([message])[0]
        
        # Predict with probabilities
        proba = self.classifier.predict_proba([embedding])[0]
        predicted_idx = np.argmax(proba)
        confidence = proba[predicted_idx]
        
        # Threshold check
        if confidence < 0.6:
            return None
        
        intent_label = self.label_encoder.inverse_transform([predicted_idx])[0]
        intent_type = IntentType(intent_label)
        
        return DetectedIntent(
            intent_type=intent_type,
            category=self._get_category(intent_type),
            confidence=float(confidence),
            slots={},  # ML doesn't extract slots
            required_capability=self._get_capability(intent_type),
            detection_method="ml"
        )
    
    def _get_category(self, intent_type: IntentType) -> IntentCategory:
        """Map intent type to category"""
        chitchat = {IntentType.GREETING, IntentType.FAREWELL, IntentType.THANKS, IntentType.SMALL_TALK}
        general_ask = {IntentType.FACTUAL_QUESTION, IntentType.EXPLANATION, IntentType.COMPARISON}
        tool_call = {IntentType.SEARCH, IntentType.LOOKUP, IntentType.CALCULATE, IntentType.GENERATE}
        agentic = {IntentType.ANALYSIS, IntentType.RESEARCH, IntentType.PLANNING}
        
        if intent_type in chitchat:
            return IntentCategory.CHITCHAT
        elif intent_type in general_ask:
            return IntentCategory.GENERAL_ASK
        elif intent_type in tool_call:
            return IntentCategory.TOOL_CALL
        elif intent_type in agentic:
            return IntentCategory.AGENTIC_FLOW
        return IntentCategory.UNKNOWN


# Training script (run offline)
def train_intent_classifier(training_data: List[Tuple[str, str]], output_path: str):
    """
    Train a simple classifier on labeled data.
    
    training_data: List of (message, intent_label) tuples
    """
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    import joblib
    
    embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    messages, labels = zip(*training_data)
    embeddings = embedder.encode(list(messages))
    
    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)
    
    classifier = LogisticRegression(max_iter=1000, multi_class='multinomial')
    classifier.fit(embeddings, encoded_labels)
    
    joblib.dump(classifier, f"{output_path}/classifier.joblib")
    joblib.dump(label_encoder, f"{output_path}/label_encoder.joblib")
```

#### Strategy 3: LLM-Based (Accurate, High Cost)

**Pros**: Handles anything, extracts slots, understands context
**Cons**: Latency, API cost, rate limits
**Use for**: Complex/ambiguous queries, slot extraction, agentic flows

```python
# src/be_inferflow_protocol/cux/llm_intent_detector.py

import json
from typing import Optional
from openai import AsyncOpenAI

class LLMIntentDetector:
    """
    Use LLM for complex intent detection and slot extraction.
    Reserved for cases where rule-based and ML fail.
    """
    
    SYSTEM_PROMPT = """You are an intent classification system for a financial AI assistant.
Analyze the user message and respond with JSON only.

Available intents:
- CHITCHAT: greeting, farewell, thanks, small_talk, off_topic
- GENERAL_ASK: factual_question, explanation, comparison, opinion
- TOOL_CALL: search, lookup, calculate, generate
- AGENTIC_FLOW: analysis, research, planning, complex_task

Required capabilities (for TOOL_CALL and AGENTIC_FLOW):
- NEWS_SEARCH: Search for news articles
- PRICE_LOOKUP: Get current price of assets
- CALCULATE: Perform calculations
- GENERATE_REPORT: Generate reports
- ANALYZE_TRENDS: Technical/fundamental analysis
- SUMMARIZE_REPORT: Summarize documents
- INVESTMENT_PLANNING: Create investment plans

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

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def detect(self, message: str, conversation_history: List[str] = None) -> DetectedIntent:
        """
        Use LLM for intent detection.
        Include conversation history for context-aware detection.
        """
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
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return DetectedIntent(
            intent_type=IntentType(result["intent_type"]),
            category=IntentCategory(result["category"]),
            confidence=result["confidence"],
            slots=result.get("slots", {}),
            required_capability=result.get("required_capability"),
            detection_method="llm"
        )
```

#### Strategy 4: Hybrid Approach (Recommended)

```python
# src/be_inferflow_protocol/cux/hybrid_intent_detector.py

class HybridIntentDetector:
    """
    Cascading intent detection:
    1. Rule-based (instant, free) - handles 60-70% of requests
    2. ML classifier (fast, cheap) - handles 20-25% of requests
    3. LLM fallback (slow, expensive) - handles 5-10% of requests
    """
    
    def __init__(
        self,
        rule_detector: RuleBasedDetector,
        ml_classifier: MLIntentClassifier,
        llm_detector: LLMIntentDetector,
        llm_threshold: float = 0.6
    ):
        self.rule_detector = rule_detector
        self.ml_classifier = ml_classifier
        self.llm_detector = llm_detector
        self.llm_threshold = llm_threshold
    
    async def detect(
        self, 
        message: str, 
        conversation_history: List[str] = None,
        force_llm: bool = False
    ) -> DetectedIntent:
        """
        Cascading detection with cost optimization.
        """
        # Force LLM for complex queries
        if force_llm:
            return await self.llm_detector.detect(message, conversation_history)
        
        # Step 1: Try rule-based (instant)
        result = self.rule_detector.detect(message)
        if result and result.confidence >= 0.8:
            return result
        
        # Step 2: Try ML classifier (fast)
        ml_result = self.ml_classifier.classify(message)
        if ml_result and ml_result.confidence >= 0.7:
            # Merge slots from rule-based if available
            if result:
                ml_result.slots.update(result.slots)
            return ml_result
        
        # Step 3: Use lower confidence result if available
        if result and result.confidence >= self.llm_threshold:
            return result
        if ml_result and ml_result.confidence >= self.llm_threshold:
            return ml_result
        
        # Step 4: Fallback to LLM (expensive but accurate)
        return await self.llm_detector.detect(message, conversation_history)
```

---

## 🔍 Example: Parsing "Xin chào"

### Step-by-Step Analysis

```python
message = "xin chào"

# Step 1: Rule-Based Detection
detector = RuleBasedDetector()
result = detector.detect(message)

# Pattern matched: r"^(xin\s*)?chào"
# Result:
DetectedIntent(
    intent_type=IntentType.GREETING,
    category=IntentCategory.CHITCHAT,
    confidence=0.95,
    slots={},
    required_capability=None,  # No capability needed for chitchat
    detection_method="rule"
)

# Processing time: < 1ms
# Cost: $0
```

### Decision Flow

```
"xin chào"
    │
    ▼
┌───────────────────┐
│ Rule-Based Check  │ ◄─── Pattern: ^(xin\s*)?chào
└─────────┬─────────┘
          │ MATCH (confidence: 0.95)
          ▼
┌───────────────────┐
│ Return GREETING   │ ◄─── No ML/LLM needed
│ Category: CHITCHAT│
│ Capability: None  │
└───────────────────┘
```

### More Examples

| Message | Detection Method | Intent | Category | Capability |
|---------|------------------|--------|----------|------------|
| "xin chào" | Rule | GREETING | CHITCHAT | None |
| "hello" | Rule | GREETING | CHITCHAT | None |
| "Đèn hành lang bị hỏng" | Rule | INCIDENT_REPORT | TOOL_CALL | REPORT_INCIDENT |
| "Kiểm tra bưu kiện cho tôi" | Rule | PACKAGE_CHECK | TOOL_CALL | CHECK_PACKAGE |
| "Bể bơi mở cửa mấy giờ?" | Rule | OPERATING_HOURS | GENERAL_ASK | POLICY_INFO |
| "Đặt chỗ sân tennis 3h chiều nay" | ML | BOOKING_FLOW | AGENTIC_FLOW | AMENITY_BOOK |
| "Xem hóa đơn tháng này và thanh toán" | LLM | PAYMENT_FLOW | AGENTIC_FLOW | BILL_VIEW |

---

## 🔄 CUX Orchestrator Implementation

```python
# src/be_inferflow_protocol/cux/orchestrator.py

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum
import structlog

from .hybrid_intent_detector import HybridIntentDetector
from .allowance_client import AllowanceClient
from .state_manager import ConversationStateManager

logger = structlog.get_logger()

@dataclass
class CuxDecision:
    """Output of CUX Orchestrator"""
    decision_type: str  # "proceed", "refusal", "clarification", "confirmation"
    intent: DetectedIntent
    allowed: bool
    message_to_client: Optional[str] = None
    workflow_to_trigger: Optional[str] = None
    workflow_params: Optional[Dict[str, Any]] = None
    clarification_options: Optional[List[Dict]] = None
    confirmation_details: Optional[Dict] = None
    suggestions: Optional[List[Dict]] = None

class CuxOrchestrator:
    """
    Central orchestration layer for CUX flow.
    """
    
    def __init__(
        self,
        intent_detector: HybridIntentDetector,
        allowance_client: AllowanceClient,
        state_manager: ConversationStateManager,
        config: Dict[str, Any] = None
    ):
        self.intent_detector = intent_detector
        self.allowance_client = allowance_client
        self.state_manager = state_manager
        self.config = config or {}

        # LangGraph workflow mappings
        from resident_agent.workflows.registry import WorkflowName
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

        # Chitchat responses
        self.chitchat_responses = {
            IntentType.GREETING: [
                "Xin chào! Tôi là Pulse AI. Tôi có thể giúp gì cho bạn hôm nay?",
                "Chào bạn! Bạn cần hỗ trợ gì về dịch vụ tòa nhà?",
            ],
            IntentType.FAREWELL: [
                "Tạm biệt! Chúc bạn một ngày tốt lành!",
                "Hẹn gặp lại! Đừng ngại liên hệ nếu cần hỗ trợ.",
            ],
            IntentType.THANKS: [
                "Không có gì! Rất vui được phục vụ bạn.",
                "Cảm ơn bạn đã sử dụng Pulse!",
            ],
        }
    
    async def process(
        self, 
        session_id: str,
        user_id: str,
        message: str
    ) -> CuxDecision:
        """
        Main entry point for CUX processing.
        """
        logger.info("cux_process_start", session_id=session_id, user_id=user_id)
        
        # 1. Load conversation state
        state = await self.state_manager.get_state(session_id)
        conversation_history = state.get("history", []) if state else []
        
        # 2. Detect intent
        intent = await self.intent_detector.detect(message, conversation_history)
        logger.info("intent_detected", 
            intent_type=intent.intent_type.value,
            category=intent.category.value,
            confidence=intent.confidence,
            method=intent.detection_method
        )
        
        # 3. Handle CHITCHAT - no allowance check needed
        if intent.category == IntentCategory.CHITCHAT:
            return await self._handle_chitchat(session_id, intent)
        
        # 4. Get user allowance
        allowance = await self.allowance_client.get_allowance(user_id)
        
        # 5. Check capability
        if intent.required_capability:
            if not self._check_allowance(intent.required_capability, allowance):
                return await self._handle_refusal(session_id, intent, allowance)
        
        # 6. Check if clarification needed
        if self._needs_clarification(intent, state):
            return await self._handle_clarification(session_id, intent, state)
        
        # 7. Check if confirmation needed (for high-risk actions)
        if self._needs_confirmation(intent):
            return await self._handle_confirmation(session_id, intent)
        
        # 8. Proceed with action
        return await self._handle_action(session_id, user_id, intent, allowance)
    
    async def _handle_chitchat(self, session_id: str, intent: DetectedIntent) -> CuxDecision:
        """Handle chitchat intents directly without workflow"""
        import random
        
        responses = self.chitchat_responses.get(intent.intent_type, [])
        response = random.choice(responses) if responses else "Tôi có thể giúp gì cho bạn?"
        
        # Update state
        await self.state_manager.update_state(session_id, {
            "last_intent": intent.intent_type.value,
            "last_category": intent.category.value,
        })
        
        return CuxDecision(
            decision_type="proceed",
            intent=intent,
            allowed=True,
            message_to_client=response,
            workflow_to_trigger=None,  # No workflow for chitchat
        )
    
    async def _handle_refusal(
        self, 
        session_id: str, 
        intent: DetectedIntent,
        allowance: Dict
    ) -> CuxDecision:
        """Handle capability refusal with helpful alternatives"""
        
        # Find what user CAN do
        allowed_caps = allowance.get("allowed_capabilities", [])
        alternatives = self._suggest_alternatives(intent.required_capability, allowed_caps)
        
        message = f"Xin lỗi, bạn không có quyền thực hiện {intent.required_capability}."
        if alternatives:
            message += f" Tuy nhiên, bạn có thể: {', '.join(alternatives)}"
        
        return CuxDecision(
            decision_type="refusal",
            intent=intent,
            allowed=False,
            message_to_client=message,
            suggestions=[{"label": alt, "capability": alt} for alt in alternatives]
        )
    
    async def _handle_clarification(
        self,
        session_id: str,
        intent: DetectedIntent,
        state: Dict
    ) -> CuxDecision:
        """Request clarification from user"""
        
        options = self._generate_clarification_options(intent)
        
        return CuxDecision(
            decision_type="clarification",
            intent=intent,
            allowed=True,
            message_to_client="Tôi cần thêm thông tin để hỗ trợ bạn tốt hơn:",
            clarification_options=options
        )
    
    async def _handle_confirmation(
        self,
        session_id: str,
        intent: DetectedIntent
    ) -> CuxDecision:
        """Request confirmation for high-risk actions"""
        
        return CuxDecision(
            decision_type="confirmation",
            intent=intent,
            allowed=True,
            message_to_client="Bạn có chắc chắn muốn thực hiện hành động này?",
            confirmation_details={
                "action": intent.intent_type.value,
                "risk_level": "HIGH",
                "consequences": self._describe_consequences(intent),
                "timeout_seconds": 30
            }
        )
    
    async def _handle_action(
        self,
        session_id: str,
        user_id: str,
        intent: DetectedIntent,
        allowance: Dict
    ) -> CuxDecision:
        """Proceed with the action - trigger LangGraph workflow"""

        from resident_agent.workflows.registry import WorkflowName
        workflow = self.intent_to_workflow.get(intent.intent_type)

        # Build workflow params (initial state for LangGraph)
        params = {
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent.intent_type.value,
            "messages": [],  # LangGraph message history
            **intent.slots
        }

        # Update conversation state
        await self.state_manager.update_state(session_id, {
            "last_intent": intent.intent_type.value,
            "last_action": workflow.value if isinstance(workflow, WorkflowName) else workflow,
            "history": (await self.state_manager.get_state(session_id)).get("history", []) + [intent.slots.get("raw_query", "")]
        })

        return CuxDecision(
            decision_type="proceed",
            intent=intent,
            allowed=True,
            message_to_client="Đang xử lý yêu cầu của bạn...",
            workflow_to_trigger=workflow.value if isinstance(workflow, WorkflowName) else workflow,
            workflow_params=params
        )
    
    def _check_allowance(self, capability: str, allowance: Dict) -> bool:
        """Check if user has required capability"""
        allowed = allowance.get("allowed_capabilities", [])
        return capability in allowed or "ADMIN" in allowance.get("roles", [])
    
    def _needs_clarification(self, intent: DetectedIntent, state: Dict) -> bool:
        """Determine if clarification is needed"""
        # Low confidence needs clarification
        if intent.confidence < 0.7:
            return True
        
        # Agentic flows without enough slots need clarification
        if intent.category == IntentCategory.AGENTIC_FLOW:
            required_slots = {"symbols", "timeframe"}
            if not required_slots.issubset(set(intent.slots.keys())):
                return True
        
        return False
    
    def _needs_confirmation(self, intent: DetectedIntent) -> bool:
        """Determine if confirmation is needed"""
        high_risk_intents = {
            IntentType.PLANNING,
            IntentType.GENERATE,
        }
        return intent.intent_type in high_risk_intents and intent.confidence < 0.9
    
    def _generate_clarification_options(self, intent: DetectedIntent) -> List[Dict]:
        """Generate clarification options based on intent"""
        if intent.category == IntentCategory.AGENTIC_FLOW:
            return [
                {"id": "1", "label": "Phân tích kỹ thuật", "description": "RSI, MACD, Moving Average"},
                {"id": "2", "label": "Phân tích cơ bản", "description": "P/E, Revenue, Earnings"},
                {"id": "3", "label": "Cả hai", "description": "Phân tích toàn diện"},
            ]
        return []
    
    def _suggest_alternatives(self, denied_cap: str, allowed_caps: List[str]) -> List[str]:
        """Suggest alternative capabilities user can use"""
        related = {
            "ANALYZE_TRENDS": ["NEWS_SEARCH", "PRICE_LOOKUP"],
            "INVESTMENT_PLANNING": ["GENERAL_QA", "SUMMARIZE_REPORT"],
            "GENERATE_REPORT": ["SUMMARIZE_REPORT"],
        }
        alternatives = related.get(denied_cap, [])
        return [cap for cap in alternatives if cap in allowed_caps]
    
    def _describe_consequences(self, intent: DetectedIntent) -> List[str]:
        """Describe consequences of action"""
        consequences = {
            IntentType.PLANNING: [
                "Sẽ tạo kế hoạch đầu tư cá nhân hóa",
                "Dữ liệu sẽ được lưu vào profile của bạn"
            ],
            IntentType.GENERATE: [
                "Báo cáo sẽ được tạo và gửi đến email",
                "Có thể mất 1-2 phút để hoàn thành"
            ],
        }
        return consequences.get(intent.intent_type, ["Hành động sẽ được thực thi"])
```

---

## 🎨 LLM-First Response Generation

### Triết lý thiết kế

Thay vì phức tạp hóa với nhiều layers (template, cache, rules), ta đơn giản hóa:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LLM-FIRST APPROACH                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User Query + User Capabilities ────► LLM ────► Structured Response    │
│                                                                         │
│  Output: { answer: "...", actions: [...] }                              │
│                                                                         │
│  Ưu điểm:                                                               │
│  ✅ Đơn giản, ít code                                                   │
│  ✅ LLM tự understand context                                           │
│  ✅ Suggestions luôn relevant                                           │
│  ✅ Actions filtered by capabilities                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Hai Flow chính

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FLOW 1: User hỏi câu hỏi cụ thể                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "Đèn hành lang tầng 5 bị hỏng"                                 │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ LLM Input:                                                   │       │
│  │ • User query                                                 │       │
│  │ • User capabilities: [report_incident, check_package, ...]  │       │
│  │ • Context: unit, building, role                              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ LLM Output:                                                  │       │
│  │ {                                                            │       │
│  │   "answer": "Đã ghi nhận báo cáo. Đơn vị sẽ kiểm tra...",  │       │
│  │   "actions": [                                               │       │
│  │     {"label": "📍 Xác nhận vị trí", "action": "confirm_loc", ...}│   │
│  │     {"label": "📋 Theo dõi phiếu", "action": "track_ticket", ...}│   │
│  │     {"label": "📞 Gọi hotline", "action": "call_support", ...}│   │
│  │   ]                                                          │       │
│  │ }                                                            │       │
│  └─────────────────────────────────────────────────────────────┘       │
│         │                                                               │
│         ▼                                                               │
│  Flutter: Render Text + Action Buttons                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FLOW 2: User không biết muốn gì / Greeting / Idle                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User: "Xin chào" hoặc "Tôi nên làm gì?"                               │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ LLM Input:                                                   │       │
│  │ • User query                                                 │       │
│  │ • User capabilities (as menu)                                │       │
│  │ • User context: unit, building, role                         │       │
│  └─────────────────────────────────────────────────────────────┘       │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ LLM Output:                                                  │       │
│  │ {                                                            │       │
│  │   "answer": "Xin chào! Tôi là Pulse AI. Tôi có thể giúp gì:",│       │
│  │   "actions": [                                               │       │
│  │     {"label": "🔧 Báo sự cố", "action": "report_incident"}  │       │
│  │     {"label": "📦 Kiểm tra bưu kiện", "action": "check_package"}│   │
│  │     {"label": "🏊 Đặt chỗ tiện ích", "action": "book_amenity"}│   │
│  │     {"label": "💳 Xem hóa đơn", "action": "view_bills"}     │       │
│  │   ]                                                          │       │
│  │ }                                                            │       │
│  └─────────────────────────────────────────────────────────────┘       │
│         │                                                               │
│         ▼                                                               │
│  Flutter: Render Greeting + Capability Menu                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### CUX Response Schema (Protobuf)

```protobuf
// proto/v1/cux_response.proto

message CuxResponse {
  string answer = 1;                    // Text response to display
  repeated ActionButton actions = 2;    // Suggested actions
  ResponseMeta meta = 3;                // Metadata
}

message ActionButton {
  string id = 1;                        // Unique ID
  string label = 2;                     // Button text (with emoji)
  string action = 3;                    // Action type: "report_incident", "check_package", etc.
  map<string, string> params = 4;       // Pre-filled params
  string icon = 5;                      // Optional icon name
  ActionStyle style = 6;                // primary, secondary, outline
}

enum ActionStyle {
  ACTION_PRIMARY = 0;                   // Highlighted
  ACTION_SECONDARY = 1;                 // Normal
  ACTION_OUTLINE = 2;                   // Less prominent
}

message ResponseMeta {
  string intent_detected = 1;
  float confidence = 2;
  bool required_tool_call = 3;
  string tool_name = 4;
}
```

---

### LLM System Prompt Template

```python
# src/be_inferflow_protocol/cux/prompts.py

CUX_SYSTEM_PROMPT = """You are Pulse AI - a Vietnamese intelligent resident services assistant.
Generate responses with suggested actions based on user's available capabilities.

## User's Available Capabilities
{capabilities_list}

## User Context
- Name: {user_name}
- Unit: {unit}
- Building: {building}
- Role: {role} (resident/staff/admin)

## Response Rules
1. ALWAYS respond in Vietnamese
2. Be polite, professional, and helpful (concierge-level service)
3. Suggest 2-4 relevant actions based on:
   - The user's query context
   - Their available capabilities ONLY (don't suggest actions they can't do)
   - Their role and unit/building for personalization
4. For greetings/unclear queries: show service menu
5. For specific queries: answer first, then suggest follow-ups
6. Escalate emergency requests (fire, medical, security) immediately

## Response Format (JSON only)
{
  "answer": "Your response in Vietnamese",
  "actions": [
    {
      "label": "🎯 Button text",
      "action": "capability_id",
      "params": {"key": "value"},
      "style": "primary|secondary|outline"
    }
  ],
  "intent": "detected_intent",
  "needs_tool": true/false,
  "tool": "tool_name if needs_tool"
}

## Example 1: Specific Query
User: "Báo sự cố đèn hỏng"
Capabilities: [report_incident, check_package, view_bills]
Response:
{
  "answer": "Đã ghi nhận báo cáo sự cố đèn hỏng. Bạn có muốn cung cấp thêm thông tin về vị trí không?",
  "actions": [
    {"label": "📍 Xác nhận vị trí", "action": "report_incident", "params": {"facility_type": "lighting"}, "style": "primary"},
    {"label": "📋 Xem phiếu đã báo", "action": "get_ticket_status", "params": {}, "style": "secondary"},
    {"label": "📞 Gọi hotline", "action": "call_support", "params": {}, "style": "outline"}
  ],
  "intent": "incident_report",
  "needs_tool": true,
  "tool": "create_incident_ticket"
}

## Example 2: Greeting / Don't know what to do
User: "Xin chào"
Capabilities: [report_incident, check_package, view_bills, book_amenity]
Unit: A-1201
Building: Pulse Tower
Response:
{
  "answer": "Xin chào! Tôi là Pulse AI, trợ lý 24/7 của bạn. Hôm nay tôi có thể giúp gì?",
  "actions": [
    {"label": "🔧 Báo sự cố", "action": "report_incident", "params": {}, "style": "primary"},
    {"label": "📦 Kiểm tra bưu kiện", "action": "check_package", "params": {}, "style": "secondary"},
    {"label": "🏊 Đặt chỗ tiện ích", "action": "book_amenity", "params": {}, "style": "secondary"},
    {"label": "💳 Xem hóa đơn", "action": "view_bills", "params": {}, "style": "outline"}
  ],
  "intent": "greeting",
  "needs_tool": false
}

## Example 3: User lacks capability
User: "Phê duyệt booking bể bơi"
Capabilities: [book_amenity, view_bills] (NO approve_booking - only admins can approve)
Role: resident
Response:
{
  "answer": "Chức năng phê duyệt chỉ dành cho quản lý viên. Bạn có thể đặt chỗ bể bơi, yêu cầu sẽ được xử lý:",
  "actions": [
    {"label": "🏊 Đặt bể bơi", "action": "book_amenity", "params": {"facility": "swimming_pool"}, "style": "primary"},
    {"label": "📋 Xem lịch đặt", "action": "view_my_bookings", "params": {}, "style": "secondary"},
    {"label": "📞 Liên hệ quản lý", "action": "contact_admin", "params": {}, "style": "outline"}
  ],
  "intent": "approve_booking",
  "needs_tool": false
}
"""


def build_cux_prompt(
    user_query: str,
    capabilities: List[Dict],
    user_context: Dict
) -> str:
    """Build the full prompt for CUX response generation"""

    # Format capabilities as a readable list
    caps_list = "\n".join([
        f"- {cap['id']}: {cap['description']}"
        for cap in capabilities
    ])

    # Format user context
    unit = user_context.get("unit", "N/A")
    building = user_context.get("building", "N/A")
    role = user_context.get("role", "resident")

    system = CUX_SYSTEM_PROMPT.format(
        capabilities_list=caps_list,
        user_name=user_context.get("name", "User"),
        unit=unit,
        building=building,
        role=role
    )

    return system, user_query
```

---

### Simplified CUX Orchestrator

```python
# src/be_inferflow_protocol/cux/orchestrator_v2.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
from openai import AsyncOpenAI

from .prompts import build_cux_prompt

@dataclass
class CuxResponse:
    """Unified response from CUX"""
    answer: str
    actions: List[Dict]
    intent: str
    needs_tool: bool
    tool: Optional[str] = None
    tool_params: Optional[Dict] = None

class CuxOrchestratorV2:
    """
    Simplified CUX Orchestrator - LLM-first approach.
    
    Flow:
    1. Get user capabilities
    2. Build context
    3. Call LLM with structured output
    4. Return answer + actions
    """
    
    def __init__(
        self,
        llm_client: AsyncOpenAI,
        capability_service,
        user_context_service,
        model: str = "gpt-4o-mini"
    ):
        self.llm = llm_client
        self.capability_service = capability_service
        self.user_context = user_context_service
        self.model = model
    
    async def process(
        self,
        user_id: str,
        session_id: str,
        message: str
    ) -> CuxResponse:
        """
        Main entry point - single LLM call for everything.
        """
        # 1. Get user's capabilities (what they're allowed to do)
        capabilities = await self.capability_service.get_user_capabilities(user_id)
        
        # 2. Get user context (unit, building, history, preferences)
        context = await self.user_context.get_context(user_id, session_id)
        
        # 3. Build prompt
        system_prompt, user_prompt = build_cux_prompt(
            user_query=message,
            capabilities=capabilities,
            user_context=context
        )
        
        # 4. Call LLM
        response = await self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # 5. Parse and return
        return CuxResponse(
            answer=result.get("answer", ""),
            actions=result.get("actions", []),
            intent=result.get("intent", "unknown"),
            needs_tool=result.get("needs_tool", False),
            tool=result.get("tool"),
            tool_params=self._extract_tool_params(result)
        )
    
    def _extract_tool_params(self, result: Dict) -> Optional[Dict]:
        """Extract tool parameters from first action if needs_tool"""
        if result.get("needs_tool") and result.get("actions"):
            first_action = result["actions"][0]
            return first_action.get("params", {})
        return None


# ═══════════════════════════════════════════════════════════════════════
# Integration with WebSocket Handler
# ═══════════════════════════════════════════════════════════════════════

class ChatHandlerV2:
    """Simplified chat handler using CUX V2"""
    
    def __init__(
        self,
        cux: CuxOrchestratorV2,
        tool_executor,
        message_router
    ):
        self.cux = cux
        self.tool_executor = tool_executor
        self.router = message_router
    
    async def handle_message(
        self,
        session_id: str,
        user_id: str,
        message: str
    ):
        """Handle user message with unified CUX response"""
        
        # 1. Get CUX response (answer + actions)
        cux_response = await self.cux.process(user_id, session_id, message)

        # 2. If tool needed, execute it first
        if cux_response.needs_tool:
            # Notify client we're processing
            await self.router.send(session_id, {
                "type": "THINKING",
                "message": cux_response.answer  # "Đang tạo phiếu báo cáo..."
            })
            
            # Execute tool
            tool_result = await self.tool_executor.execute(
                tool=cux_response.tool,
                params=cux_response.tool_params
            )
            
            # Re-run CUX with tool result to get final answer
            enriched_message = f"{message}\n\nTool result: {json.dumps(tool_result)}"
            cux_response = await self.cux.process(user_id, session_id, enriched_message)
        
        # 3. Send unified response to client
        await self.router.send(session_id, {
            "type": "CUX_RESPONSE",
            "answer": cux_response.answer,
            "actions": cux_response.actions
        })
```

---

### Flutter Client Rendering

```dart
// lib/widgets/cux_response_widget.dart

class CuxResponseWidget extends StatelessWidget {
  final CuxResponse response;
  final Function(ActionButton) onActionTap;

  const CuxResponseWidget({
    required this.response,
    required this.onActionTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Text Answer (with markdown support)
        MarkdownBody(
          data: response.answer,
          styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)),
        ),
        
        const SizedBox(height: 16),
        
        // Action Buttons Grid
        if (response.actions.isNotEmpty) ...[
          Text(
            'Bạn có thể:',
            style: Theme.of(context).textTheme.labelMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: response.actions.map((action) {
              return _buildActionButton(context, action);
            }).toList(),
          ),
        ],
      ],
    );
  }

  Widget _buildActionButton(BuildContext context, ActionButton action) {
    final style = _getButtonStyle(action.style);
    
    return ElevatedButton(
      style: style,
      onPressed: () => onActionTap(action),
      child: Text(action.label),
    );
  }

  ButtonStyle _getButtonStyle(ActionStyle style) {
    switch (style) {
      case ActionStyle.primary:
        return ElevatedButton.styleFrom(
          backgroundColor: Colors.blue,
          foregroundColor: Colors.white,
        );
      case ActionStyle.secondary:
        return ElevatedButton.styleFrom(
          backgroundColor: Colors.grey[200],
          foregroundColor: Colors.black87,
        );
      case ActionStyle.outline:
        return OutlinedButton.styleFrom(
          foregroundColor: Colors.blue,
        ).copyWith(
          side: MaterialStateProperty.all(BorderSide(color: Colors.blue)),
        );
    }
  }
}

// Usage in chat screen
class ChatScreen extends StatelessWidget {
  void _handleAction(ActionButton action) {
    // Send action back to server
    socket.send({
      'type': 'ACTION_SELECTED',
      'action': action.action,
      'params': action.params,
    });
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<CuxResponse>(
      stream: cuxResponseStream,
      builder: (context, snapshot) {
        if (snapshot.hasData) {
          return CuxResponseWidget(
            response: snapshot.data!,
            onActionTap: _handleAction,
          );
        }
        return LoadingIndicator();
      },
    );
  }
}
```

---

### Example Flows

#### Flow 1: "Báo sự cố đèn hỏng" (có tool call)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ User: "Đèn hành lang tầng 5 bị hỏng"                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Step 1: CUX Process                                                     │
│   Capabilities: [report_incident, check_package, view_bills]          │
│   Unit: A-1201                                                         │
│                                                                         │
│ Step 2: LLM Response                                                    │
│   {                                                                     │
│     "answer": "Đang tạo phiếu báo cáo sự cố...",                      │
│     "actions": [],                                                      │
│     "intent": "incident_report",                                       │
│     "needs_tool": true,                                                │
│     "tool": "create_incident_ticket"                                   │
│   }                                                                     │
│                                                                         │
│ Step 3: Execute Tool → { ticket_id: 12345, status: "pending" }         │
│                                                                         │
│ Step 4: Re-run CUX with tool result                                    │
│   {                                                                     │
│     "answer": "✅ Đã tạo phiếu #12345. Đơn vị sẽ kiểm tra trong 2h.",  │
│     "actions": [                                                        │
│       {"label": "📋 Theo dõi phiếu", "action": "get_ticket_status", ...},│
│       {"label": "📞 Gọi hotline", "action": "call_support", ...},      │
│       {"label": "🔧 Báo sự cố khác", "action": "report_incident", ...} │
│     ],                                                                  │
│     "intent": "incident_report",                                       │
│     "needs_tool": false                                                │
│   }                                                                     │
│                                                                         │
│ Step 5: Flutter renders                                                 │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ ✅ Đã tạo phiếu #12345. Đơn vị sẽ kiểm tra trong 2h.        │      │
│   │                                                              │      │
│   │ Bạn có thể:                                                  │      │
│   │ [📋 Theo dõi phiếu] [📞 Gọi hotline] [🔧 Báo sự cố khác]   │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Flow 2: "Xin chào" (không có tool, show menu)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ User: "Xin chào"                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Step 1: CUX Process                                                     │
│   Capabilities: [report_incident, check_package, view_bills,          │
│                   book_amenity]                                        │
│   Unit: A-1201                                                         │
│   Building: Pulse Tower                                                │
│                                                                         │
│ Step 2: LLM Response (no tool needed)                                  │
│   {                                                                     │
│     "answer": "Xin chào! Tôi là Pulse AI. Hôm nay tôi có thể giúp gì?",│
│     "actions": [                                                        │
│       {"label": "🔧 Báo sự cố", "action": "report_incident", ...},     │
│       {"label": "📦 Kiểm tra bưu kiện", "action": "check_package", ...},│
│       {"label": "🏊 Đặt chỗ tiện ích", "action": "book_amenity", ...},  │
│       {"label": "💳 Xem hóa đơn", "action": "view_bills", ...}         │
│     ],                                                                  │
│     "intent": "greeting",                                              │
│     "needs_tool": false                                                │
│   }                                                                     │
│                                                                         │
│ Step 3: Flutter renders                                                 │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Xin chào! Tôi là Pulse AI. Hôm nay tôi có thể giúp gì?       │      │
│   │                                                              │      │
│   │ Bạn có thể:                                                  │      │
│   │ [🔧 Báo sự cố] [📦 Kiểm tra bưu kiện]                       │      │
│   │ [🏊 Đặt chỗ tiện ích] [💳 Xem hóa đơn]                      │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Cost & Performance

| Metric | Value |
|--------|-------|
| **LLM calls per request** | 1-2 (1 if no tool, 2 if tool needed) |
| **Model** | gpt-4o-mini |
| **Cost per request** | ~$0.001-0.002 |
| **Latency (no tool)** | 200-400ms |
| **Latency (with tool)** | 400-800ms |

### So sánh với approach cũ

| Aspect | Old (Multi-layer) | New (LLM-first) |
|--------|-------------------|-----------------|
| **Complexity** | High (cache, template, rules) | Low (single LLM call) |
| **Maintenance** | Many configs to manage | Just prompt tuning |
| **Personalization** | Limited by templates | Full LLM understanding |
| **Cost** | Lower (more caching) | Slightly higher |
| **Flexibility** | Rigid | Highly flexible |
| **Time to market** | Longer | Faster |

---

### Optional: Caching for Common Patterns

Nếu cần optimize cost, có thể cache một số patterns phổ biến:

```python
class CuxOrchestratorV2WithCache:
    """Optional caching layer for common patterns"""
    
    async def process(self, user_id: str, session_id: str, message: str) -> CuxResponse:
        # Check cache for exact match (rare)
        cache_key = f"cux:{hash(message)}:{hash(str(caps))}"
        cached = await self.redis.get(cache_key)
        if cached:
            return CuxResponse(**json.loads(cached))
        
        # Call LLM
        response = await self._call_llm(...)
        
        # Cache if it's a common pattern (greeting, simple lookup)
        if response.intent in ["greeting", "farewell", "thanks"]:
            await self.redis.setex(cache_key, 3600, json.dumps(response))
        
        return response
```

Nhưng với cost của gpt-4o-mini (~$0.001/request), caching có thể không cần thiết trừ khi volume rất cao (>100k requests/day).

---

## 🔌 Integration with WS Middleware
    "updated_at": "2026-01-11T10:00:00Z"

# ═══════════════════════════════════════════════════════════════════════
# Collection: clarification_configs
# ═══════════════════════════════════════════════════════════════════════
{
    "_id": "clarify_report_type",
    "trigger_conditions": {
        "intent_category": "tool_call",
        "missing_entities": ["report_type"]
    },
    
    "prompt_template": "Bạn muốn xem loại dịch vụ nào cho {{facility_type}}?",
    
    # Dynamic options - fetched from capabilities DB
    "options_source": "capabilities",
    "options_filter": {
        "category": "service",
        "user_has_access": True  # Filter by user's allowance
    },

    # Static fallback options
    "static_options": [
        {"id": "incident", "label": "🔧 Báo sự cố", "capability": "cap_report_incident"},
        {"id": "package", "label": "📦 Kiểm tra bưu kiện", "capability": "cap_check_package"},
        {"id": "bill", "label": "💳 Xem hóa đơn", "capability": "cap_view_bills"}
    ],

    # LLM-generated options for novel situations
    "llm_generation": {
        "enabled": True,
        "prompt": "Based on user's query '{{user_query}}' and context, suggest 3-5 relevant service types they might want.",
        "cache_key_template": "clarify:{{intent}}:{{service_type}}"
    },

    "allow_free_text": True,
    "timeout_seconds": 60
}

# ═══════════════════════════════════════════════════════════════════════
# Collection: refusal_templates
# ═══════════════════════════════════════════════════════════════════════
{
    "_id": "refusal_capability_denied",
    "category": "refusal",

    "message_template": "Xin lỗi, tính năng **{{capability_name}}** yêu cầu quyền hạn {{required_role}}.",

    # Dynamic alternatives - query from capabilities
    "alternatives_config": {
        "source": "database",
        "query": {
            "collection": "capabilities",
            "filter": {
                "role": {"$in": ["{{user_role}}", "all"]},
                "category": "{{capability_category}}"
            },
            "limit": 3
        }
    },

    # Fallback mapping (if DB query fails)
    "alternatives_fallback": {
        "cap_amenity_book": ["cap_amenity_check", "cap_service_info"],
        "cap_payment_flow": ["cap_bill_view", "cap_service_info"]
    },

    "contact_message": {
        "enabled": True,
        "template": "Vui lòng liên hệ ban quản lý để biết thêm chi tiết."
    }
}

# ═══════════════════════════════════════════════════════════════════════
# Collection: suggestion_rules
# ═══════════════════════════════════════════════════════════════════════
{
    "_id": "suggest_after_incident_report",
    "trigger": {
        "after_intent": "incident_report",
        "entity_present": ["location"]
    },

    # Rule-based suggestions
    "rules": [
        {
            "condition": "{{urgency}} == 'high'",
            "suggestion": {"label": "📞 Gọi hotline khẩn cấp", "action": "call_emergency", "params": {"location": "{{location}}"}}
        },
        {
            "condition": "{{facility_type}} == 'electrical'",
            "suggestion": {"label": "💡 Các biện pháp an toàn điện", "action": "show_safety_tips", "params": {"type": "electrical"}}
        }
    ],

    # Default suggestions (always show)
    "default_suggestions": [
        {"label": "📋 Theo dõi phiếu", "action": "track_ticket", "params": {"ticket_id": "{{ticket_id}}"}},
        {"label": "🔧 Báo sự cố khác", "action": "report_incident", "params": {}}
    ],

    # LLM-powered personalized suggestions
    "llm_suggestions": {
        "enabled": True,
        "prompt": """Based on:
- User just reported incident at {{location}} (type: {{facility_type}}, urgency: {{urgency}})
- User's unit: {{unit}}
- User's recent tickets: {{recent_tickets}}

Suggest 2-3 relevant next actions. Return JSON array.""",
        "cache_ttl": 300  # Cache for 5 minutes
    }
}
```

---

### 2. Dynamic Response Engine Implementation

```python
# src/be_inferflow_protocol/cux/dynamic_response_engine.py

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re
import json
from datetime import datetime
import chevron  # Mustache template library
import structlog

logger = structlog.get_logger()

@dataclass
class ResponseContext:
    """Context for generating dynamic responses"""
    user_id: str
    user_name: Optional[str] = None
    user_tier: str = "free"
    intent_type: str = None
    intent_category: str = None
    entities: Dict[str, str] = None
    conversation_history: List[str] = None
    time_of_day: str = None
    is_returning_user: bool = False
    user_preferences: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name or "",
            "user_tier": self.user_tier,
            "intent_type": self.intent_type,
            "intent_category": self.intent_category,
            "time_of_day": self.time_of_day or self._get_time_of_day(),
            "is_returning_user": str(self.is_returning_user).lower(),
            **(self.entities or {}),
            **(self.user_preferences or {})
        }
    
    def _get_time_of_day(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        return "evening"


class DynamicResponseEngine:
    """
    Generate dynamic responses using:
    1. Redis cache (fastest)
    2. Template engine (fast)
    3. LLM generation (fallback)
    """
    
    def __init__(
        self,
        mongo_db,
        redis_client,
        llm_client,
        capability_resolver
    ):
        self.db = mongo_db
        self.redis = redis_client
        self.llm = llm_client
        self.capability_resolver = capability_resolver
        
        # In-memory cache for templates (refresh every 5 min)
        self._template_cache = {}
        self._cache_ttl = 300
    
    # ═══════════════════════════════════════════════════════════════════
    # CHITCHAT RESPONSES
    # ═══════════════════════════════════════════════════════════════════
    
    async def generate_chitchat_response(
        self,
        intent_type: str,
        context: ResponseContext
    ) -> str:
        """Generate dynamic chitchat response"""
        
        cache_key = f"chitchat:{intent_type}:{context.user_tier}:{context.time_of_day}"
        
        # 1. Try Redis cache
        cached = await self.redis.get(cache_key)
        if cached:
            return self._render_template(cached, context.to_dict())
        
        # 2. Get template from DB
        template_doc = await self._get_template(f"chitchat_{intent_type}")
        if not template_doc:
            return await self._llm_generate_chitchat(intent_type, context)
        
        # 3. Select appropriate variant
        response_template = self._select_variant(template_doc, context)
        
        # 4. Render with context
        response = self._render_template(response_template, context.to_dict())
        
        # 5. Cache for future
        await self.redis.setex(cache_key, 3600, response_template)
        
        return response
    
    def _select_variant(self, template_doc: Dict, context: ResponseContext) -> str:
        """Select the most appropriate template variant based on context"""
        
        ctx = context.to_dict()
        
        # Check context variants first
        variants = template_doc.get("context_variants", {})
        
        # Priority: user_tier > time_of_day > returning_user > default
        for variant_key in ["user_tier", "time_of_day", "returning_user"]:
            if variant_key in variants:
                variant_value = ctx.get(variant_key)
                if variant_value and variant_value in variants[variant_key]:
                    return variants[variant_key][variant_value]
        
        # Fallback to weighted random from templates
        templates = template_doc.get("templates", [])
        if templates:
            import random
            weights = [t.get("weight", 1.0) for t in templates]
            selected = random.choices(templates, weights=weights, k=1)[0]
            return selected["text"]
        
        return "Tôi có thể giúp gì cho bạn?"
    
    async def _llm_generate_chitchat(
        self,
        intent_type: str,
        context: ResponseContext
    ) -> str:
        """Fallback: Use LLM to generate chitchat response"""
        
        prompt = f"""Generate a {intent_type} response for a Vietnamese financial AI assistant.
Context:
- User name: {context.user_name or 'User'}
- Time: {context.time_of_day}
- User tier: {context.user_tier}

Requirements:
- Be friendly and professional
- Keep it short (1-2 sentences)
- Use Vietnamese

Response (just the text, no quotes):"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        
        result = response.choices[0].message.content.strip()
        
        # Cache for future (with context variations)
        cache_key = f"chitchat:{intent_type}:{context.user_tier}:{context.time_of_day}"
        await self.redis.setex(cache_key, 3600, result)
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════
    # CLARIFICATION OPTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    async def generate_clarification(
        self,
        intent: "DetectedIntent",
        context: ResponseContext,
        user_allowance: Dict
    ) -> Dict[str, Any]:
        """Generate dynamic clarification with personalized options"""
        
        # 1. Get clarification config
        config = await self._get_clarification_config(intent)
        if not config:
            return await self._llm_generate_clarification(intent, context)
        
        # 2. Generate prompt
        prompt = self._render_template(
            config.get("prompt_template", "Bạn cần gì thêm?"),
            {**context.to_dict(), **intent.slots}
        )
        
        # 3. Get options dynamically
        options = await self._get_clarification_options(config, context, user_allowance)
        
        return {
            "prompt": prompt,
            "options": options,
            "allow_free_text": config.get("allow_free_text", True),
            "timeout_seconds": config.get("timeout_seconds", 60)
        }
    
    async def _get_clarification_options(
        self,
        config: Dict,
        context: ResponseContext,
        user_allowance: Dict
    ) -> List[Dict]:
        """Get clarification options from various sources"""
        
        options = []
        
        # Source 1: Dynamic from capabilities DB
        if config.get("options_source") == "capabilities":
            filter_query = config.get("options_filter", {})
            caps = await self._query_user_capabilities(
                context.user_id,
                user_allowance,
                filter_query.get("category")
            )
            for cap in caps:
                options.append({
                    "id": cap["_id"],
                    "label": cap.get("display_name", cap["name"]),
                    "description": cap.get("description", ""),
                    "icon": cap.get("icon"),
                    "capability": cap["_id"]
                })
        
        # Source 2: Static options (filtered by allowance)
        if not options and config.get("static_options"):
            allowed_caps = set(user_allowance.get("allowed_capabilities", []))
            for opt in config["static_options"]:
                if opt.get("capability") in allowed_caps or not opt.get("capability"):
                    options.append(opt)
        
        # Source 3: LLM-generated (if enabled and needed)
        if not options and config.get("llm_generation", {}).get("enabled"):
            options = await self._llm_generate_options(config, context)
        
        return options[:5]  # Limit to 5 options
    
    async def _llm_generate_clarification(
        self,
        intent: "DetectedIntent",
        context: ResponseContext
    ) -> Dict[str, Any]:
        """Use LLM to generate clarification when no config exists"""
        
        prompt = f"""A user asked: "{intent.slots.get('raw_query', '')}"
Intent detected: {intent.intent_type.value}
Missing information: {list(intent.slots.keys())}

Generate a clarification request in Vietnamese with 3-4 options.
Return JSON:
{{
  "prompt": "question to ask user",
  "options": [
    {{"id": "1", "label": "option label", "description": "brief description"}}
  ]
}}"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=300
        )
        
        result = json.loads(response.choices[0].message.content)
        result["allow_free_text"] = True
        result["timeout_seconds"] = 60
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════
    # REFUSAL WITH ALTERNATIVES
    # ═══════════════════════════════════════════════════════════════════
    
    async def generate_refusal(
        self,
        denied_capability: str,
        context: ResponseContext,
        user_allowance: Dict
    ) -> Dict[str, Any]:
        """Generate refusal message with dynamic alternatives"""
        
        # 1. Get capability info
        cap_info = await self.db.capabilities.find_one({"_id": denied_capability})
        cap_name = cap_info.get("display_name", denied_capability) if cap_info else denied_capability
        required_tier = cap_info.get("tier", "pro") if cap_info else "pro"
        
        # 2. Get refusal template
        template = await self._get_template("refusal_capability_denied")
        
        # 3. Generate message
        message = self._render_template(
            template.get("message_template", "Xin lỗi, bạn không có quyền thực hiện chức năng này."),
            {
                "capability_name": cap_name,
                "required_tier": required_tier,
                **context.to_dict()
            }
        )
        
        # 4. Find alternatives dynamically
        alternatives = await self._find_alternatives(
            denied_capability,
            user_allowance,
            template.get("alternatives_config"),
            template.get("alternatives_fallback", {})
        )
        
        # 5. Add upsell if enabled
        upsell = None
        if template.get("upsell_message", {}).get("enabled"):
            upsell = self._render_template(
                template["upsell_message"]["template"],
                {"upgrade_tier": required_tier, "upgrade_url": "/upgrade"}
            )
        
        return {
            "message": message,
            "alternatives": alternatives,
            "upsell": upsell
        }
    
    async def _find_alternatives(
        self,
        denied_cap: str,
        user_allowance: Dict,
        db_config: Optional[Dict],
        fallback_mapping: Dict
    ) -> List[Dict]:
        """Find alternative capabilities user can use"""
        
        allowed_caps = set(user_allowance.get("allowed_capabilities", []))
        alternatives = []
        
        # 1. Try database query
        if db_config and db_config.get("source") == "database":
            try:
                # Get category of denied capability
                denied_cap_info = await self.db.capabilities.find_one({"_id": denied_cap})
                if denied_cap_info:
                    category = denied_cap_info.get("category")
                    user_tier = user_allowance.get("tier", "free")
                    
                    # Find similar capabilities user can access
                    cursor = self.db.capabilities.find({
                        "_id": {"$in": list(allowed_caps)},
                        "category": category,
                        "_id": {"$ne": denied_cap}
                    }).limit(3)
                    
                    async for cap in cursor:
                        alternatives.append({
                            "id": cap["_id"],
                            "label": cap.get("display_name", cap["name"]),
                            "description": cap.get("description", "")
                        })
            except Exception as e:
                logger.warning("alternatives_db_query_failed", error=str(e))
        
        # 2. Fallback to static mapping
        if not alternatives and denied_cap in fallback_mapping:
            for alt_cap in fallback_mapping[denied_cap]:
                if alt_cap in allowed_caps:
                    cap_info = await self.db.capabilities.find_one({"_id": alt_cap})
                    if cap_info:
                        alternatives.append({
                            "id": alt_cap,
                            "label": cap_info.get("display_name", alt_cap),
                            "description": cap_info.get("description", "")
                        })
        
        return alternatives
    
    # ═══════════════════════════════════════════════════════════════════
    # NEXT ACTION SUGGESTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    async def generate_suggestions(
        self,
        completed_intent: "DetectedIntent",
        action_result: Dict,
        context: ResponseContext,
        user_allowance: Dict
    ) -> List[Dict]:
        """Generate personalized next action suggestions"""
        
        # 1. Get suggestion rules for this intent
        rule_doc = await self.db.suggestion_rules.find_one({
            "trigger.after_intent": completed_intent.intent_type.value
        })
        
        suggestions = []
        
        if rule_doc:
            # 2. Evaluate rule-based suggestions
            rule_suggestions = await self._evaluate_suggestion_rules(
                rule_doc.get("rules", []),
                action_result,
                context
            )
            suggestions.extend(rule_suggestions)
            
            # 3. Add default suggestions
            for default in rule_doc.get("default_suggestions", []):
                rendered = self._render_suggestion(default, context, action_result)
                suggestions.append(rendered)
        
        # 4. LLM-powered personalized suggestions (if enabled)
        if len(suggestions) < 3:
            llm_suggestions = await self._llm_generate_suggestions(
                completed_intent,
                action_result,
                context,
                user_allowance
            )
            suggestions.extend(llm_suggestions)
        
        # 5. Filter by user's allowance
        allowed_caps = set(user_allowance.get("allowed_capabilities", []))
        filtered = []
        for sug in suggestions:
            cap = sug.get("required_capability")
            if not cap or cap in allowed_caps:
                filtered.append(sug)
        
        return filtered[:5]  # Limit to 5
    
    async def _evaluate_suggestion_rules(
        self,
        rules: List[Dict],
        action_result: Dict,
        context: ResponseContext
    ) -> List[Dict]:
        """Evaluate rule conditions and return matching suggestions"""
        
        suggestions = []
        ctx = {**context.to_dict(), **action_result}
        
        for rule in rules:
            condition = rule.get("condition", "")
            # Simple expression evaluation (could use more sophisticated parser)
            try:
                if self._evaluate_condition(condition, ctx):
                    suggestions.append(self._render_suggestion(rule["suggestion"], context, action_result))
            except Exception as e:
                logger.warning("rule_evaluation_failed", condition=condition, error=str(e))
        
        return suggestions
    
    def _evaluate_condition(self, condition: str, ctx: Dict) -> bool:
        """Evaluate simple conditions like '{{price_change_24h}} > 5'"""
        
        # Render variables
        rendered = self._render_template(condition, ctx)
        
        # Parse and evaluate (simple implementation)
        match = re.match(r"([\d.-]+)\s*([<>=!]+)\s*([\d.-]+)", rendered)
        if match:
            left, op, right = float(match.group(1)), match.group(2), float(match.group(3))
            ops = {
                ">": lambda a, b: a > b,
                "<": lambda a, b: a < b,
                ">=": lambda a, b: a >= b,
                "<=": lambda a, b: a <= b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
            }
            return ops.get(op, lambda a, b: False)(left, right)
        
        return False
    
    async def _llm_generate_suggestions(
        self,
        intent: "DetectedIntent",
        action_result: Dict,
        context: ResponseContext,
        user_allowance: Dict
    ) -> List[Dict]:
        """Use LLM to generate personalized suggestions"""
        
        # Check cache first
        cache_key = f"suggestions:{intent.intent_type.value}:{hash(json.dumps(intent.slots, sort_keys=True))}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Get user's available capabilities for context
        available_caps = user_allowance.get("allowed_capabilities", [])
        
        prompt = f"""User just completed: {intent.intent_type.value}
Result: {json.dumps(action_result, ensure_ascii=False)[:500]}
User's unit: {context.entities.get('unit', 'N/A')}
User's available actions: {available_caps[:10]}

Suggest 3 relevant next actions in Vietnamese.
Return JSON array:
[{{"label": "button text", "action": "action_type", "params": {{}}, "reason": "why relevant"}}]"""
        
        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            suggestions = result if isinstance(result, list) else result.get("suggestions", [])
            
            # Cache for 5 minutes
            await self.redis.setex(cache_key, 300, json.dumps(suggestions))
            
            return suggestions
        except Exception as e:
            logger.error("llm_suggestions_failed", error=str(e))
            return []
    
    # ═══════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def _render_template(self, template: str, data: Dict) -> str:
        """Render Mustache template with data"""
        try:
            return chevron.render(template, data)
        except Exception:
            # Fallback: simple string replacement
            result = template
            for key, value in data.items():
                result = result.replace("{{" + key + "}}", str(value) if value else "")
            return result
    
    def _render_suggestion(
        self,
        suggestion: Dict,
        context: ResponseContext,
        action_result: Dict
    ) -> Dict:
        """Render a suggestion with context data"""
        ctx = {**context.to_dict(), **action_result}
        
        return {
            "id": suggestion.get("id", str(hash(suggestion.get("label", "")))),
            "label": self._render_template(suggestion.get("label", ""), ctx),
            "action": suggestion.get("action"),
            "params": {
                k: self._render_template(str(v), ctx) 
                for k, v in suggestion.get("params", {}).items()
            },
            "required_capability": suggestion.get("required_capability")
        }
    
    async def _get_template(self, template_id: str) -> Optional[Dict]:
        """Get template from cache or DB"""
        if template_id in self._template_cache:
            return self._template_cache[template_id]
        
        doc = await self.db.response_templates.find_one({"_id": template_id})
        if doc:
            self._template_cache[template_id] = doc
        return doc
    
    async def _get_clarification_config(self, intent: "DetectedIntent") -> Optional[Dict]:
        """Find matching clarification config"""
        return await self.db.clarification_configs.find_one({
            "trigger_conditions.intent_category": intent.category.value,
            "$or": [
                {"trigger_conditions.missing_entities": {"$in": list(intent.slots.keys())}},
                {"trigger_conditions.intent_type": intent.intent_type.value}
            ]
        })
    
    async def _query_user_capabilities(
        self,
        user_id: str,
        user_allowance: Dict,
        category: Optional[str] = None
    ) -> List[Dict]:
        """Query capabilities user has access to"""
        allowed_caps = user_allowance.get("allowed_capabilities", [])
        
        query = {"_id": {"$in": allowed_caps}}
        if category:
            query["category"] = category
        
        return await self.db.capabilities.find(query).to_list(length=10)
```

---

### 3. Updated CUX Orchestrator (Using Dynamic Engine)

```python
# src/be_inferflow_protocol/cux/orchestrator.py (Updated)

class CuxOrchestrator:
    """Updated CUX Orchestrator with Dynamic Response Engine"""
    
    def __init__(
        self,
        intent_detector: HybridIntentDetector,
        allowance_client: AllowanceClient,
        state_manager: ConversationStateManager,
        response_engine: DynamicResponseEngine,  # NEW
        config: Dict[str, Any] = None
    ):
        self.intent_detector = intent_detector
        self.allowance_client = allowance_client
        self.state_manager = state_manager
        self.response_engine = response_engine  # NEW
        self.config = config or {}

        # LangGraph workflow mappings
        from resident_agent.workflows.registry import WorkflowName
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
    
    async def _build_context(self, session_id: str, user_id: str) -> ResponseContext:
        """Build response context from user data"""
        user_profile = await self.allowance_client.get_user_profile(user_id)
        state = await self.state_manager.get_state(session_id)
        
        return ResponseContext(
            user_id=user_id,
            user_name=user_profile.get("name"),
            user_tier=user_profile.get("tier", "free"),
            is_returning_user=state is not None,
            conversation_history=state.get("history", []) if state else [],
            user_preferences=user_profile.get("preferences", {})
        )
    
    async def _handle_chitchat(self, session_id: str, intent: DetectedIntent, context: ResponseContext) -> CuxDecision:
        """Handle chitchat with dynamic responses"""
        
        # Use dynamic response engine instead of hardcoded
        response = await self.response_engine.generate_chitchat_response(
            intent_type=intent.intent_type.value,
            context=context
        )
        
        return CuxDecision(
            decision_type="proceed",
            intent=intent,
            allowed=True,
            message_to_client=response,
            workflow_to_trigger=None
        )
    
    async def _handle_refusal(
        self, 
        session_id: str, 
        intent: DetectedIntent,
        allowance: Dict,
        context: ResponseContext
    ) -> CuxDecision:
        """Handle refusal with dynamic alternatives"""
        
        refusal = await self.response_engine.generate_refusal(
            denied_capability=intent.required_capability,
            context=context,
            user_allowance=allowance
        )
        
        return CuxDecision(
            decision_type="refusal",
            intent=intent,
            allowed=False,
            message_to_client=refusal["message"],
            suggestions=[
                {"label": alt["label"], "capability": alt["id"]}
                for alt in refusal.get("alternatives", [])
            ]
        )
    
    async def _handle_clarification(
        self,
        session_id: str,
        intent: DetectedIntent,
        state: Dict,
        context: ResponseContext,
        allowance: Dict
    ) -> CuxDecision:
        """Request clarification with dynamic options"""
        
        clarification = await self.response_engine.generate_clarification(
            intent=intent,
            context=context,
            user_allowance=allowance
        )
        
        return CuxDecision(
            decision_type="clarification",
            intent=intent,
            allowed=True,
            message_to_client=clarification["prompt"],
            clarification_options=clarification["options"]
        )
```

---

### 4. Background Job: Pre-generate & Cache Responses

```python
# src/be_inferflow_protocol/jobs/response_pregeneration.py

import asyncio
from typing import List

class ResponsePregenerator:
    """
    Background job to pre-generate LLM responses and cache them.
    Runs periodically to ensure fast response times.
    """
    
    def __init__(self, db, redis, llm_client):
        self.db = db
        self.redis = redis
        self.llm = llm_client
    
    async def run(self):
        """Run pre-generation for all template types"""
        await asyncio.gather(
            self._pregenerate_chitchat(),
            self._pregenerate_clarifications(),
            self._pregenerate_common_suggestions()
        )
    
    async def _pregenerate_chitchat(self):
        """Pre-generate chitchat responses for common contexts"""
        
        intent_types = ["greeting", "farewell", "thanks"]
        tiers = ["free", "pro", "enterprise"]
        times = ["morning", "afternoon", "evening"]
        
        for intent in intent_types:
            for tier in tiers:
                for time in times:
                    cache_key = f"chitchat:{intent}:{tier}:{time}"
                    
                    # Skip if already cached
                    if await self.redis.exists(cache_key):
                        continue
                    
                    # Generate using LLM
                    response = await self._generate_chitchat_llm(intent, tier, time)
                    
                    # Cache for 24 hours
                    await self.redis.setex(cache_key, 86400, response)
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.5)
    
    async def _generate_chitchat_llm(self, intent: str, tier: str, time: str) -> str:
        prompt = f"""Generate a {intent} response for a Vietnamese financial AI assistant.
Time: {time}
User tier: {tier}
Be friendly and professional. Keep it short (1-2 sentences).
Response in Vietnamese:"""
        
        response = await self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    async def _pregenerate_clarifications(self):
        """Pre-generate common clarification prompts"""
        # Similar pattern...
        pass
    
    async def _pregenerate_common_suggestions(self):
        """Pre-generate suggestions for common scenarios"""
        # Similar pattern...
        pass


# Schedule with APScheduler or Celery Beat
# Run every 6 hours
```

---

### 5. Summary: Không cần Hardcode!

| Component | Before (Hardcode) | After (Dynamic) |
|-----------|-------------------|-----------------|
| **Chitchat** | Dict trong code | MongoDB templates + LLM fallback |
| **Clarification** | Hardcoded options | DB config + User allowance filter |
| **Alternatives** | Dict mapping | DB query + Capability resolver |
| **Suggestions** | None | Rules engine + LLM personalization |

**Cost Impact**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│ Request Distribution                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Redis Cache (pre-generated):  70%  │ Cost: $0      │ Latency: < 5ms    │
│ Template Engine:              25%  │ Cost: $0      │ Latency: < 10ms   │
│ LLM Generation:                5%  │ Cost: ~$0.01  │ Latency: 200-500ms│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Integration with WS Middleware

```python
# src/be_inferflow_protocol/handlers/chat_handler.py

from ..cux.orchestrator import CuxOrchestrator, CuxDecision
from resident_agent.workflows.executor import LangGraphExecutor
from resident_agent.workflows.registry import WorkflowName

class ChatHandler:
    def __init__(self, cux_orchestrator: CuxOrchestrator, langgraph_executor: LangGraphExecutor, message_router):
        self.cux = cux_orchestrator
        self.langgraph = langgraph_executor  # Changed from windmill_client
        self.router = message_router
    
    async def handle_chat_input(self, session_id: str, user_id: str, message: str):
        """
        Handle incoming chat message through CUX layer.
        """
        # Process through CUX
        decision = await self.cux.process(session_id, user_id, message)
        
        # Route based on decision type
        if decision.decision_type == "refusal":
            await self._send_refusal(session_id, decision)
        
        elif decision.decision_type == "clarification":
            await self._send_clarification(session_id, decision)
        
        elif decision.decision_type == "confirmation":
            await self._send_confirmation_request(session_id, decision)
        
        elif decision.decision_type == "proceed":
            if decision.workflow_to_trigger:
                await self._trigger_workflow(session_id, decision)
            else:
                # Direct response (chitchat)
                await self._send_direct_response(session_id, decision)
    
    async def _send_refusal(self, session_id: str, decision: CuxDecision):
        """Send safe refusal message"""
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.SYSTEM_INFO,
            payload={
                "type": "SAFE_REFUSAL",
                "message": decision.message_to_client,
                "suggestions": decision.suggestions
            }
        )
    
    async def _send_clarification(self, session_id: str, decision: CuxDecision):
        """Send clarification request"""
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CLARIFICATION_REQUEST,
            payload={
                "prompt": decision.message_to_client,
                "choices": decision.clarification_options,
                "allow_free_text": True,
                "timeout_seconds": 60
            }
        )
    
    async def _trigger_workflow(self, session_id: str, decision: CuxDecision):
        """Execute LangGraph workflow (replaces Windmill)"""
        # Notify client
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CHAT_THINKING_START,
            payload={"message": decision.message_to_client}
        )

        # Build initial state for LangGraph
        initial_state = {
            "user_id": decision.workflow_params["user_id"],
            "session_id": session_id,
            **decision.intent.slots,
            "messages": []  # LangGraph message history
        }

        # Execute LangGraph workflow
        result = await self.langgraph.execute_intent_workflow(
            intent_type=decision.intent.intent_type.value,
            context=initial_state
        )

        # Send result to client
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CHAT_RESPONSE_CHUNK,
            payload={
                "content": result.get("message", "Workflow completed"),
                "is_final": True,
                "data": result.get("state", {})
            }
        )
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CHAT_RESPONSE_COMPLETE,
            payload={}
        )
    
    async def _send_direct_response(self, session_id: str, decision: CuxDecision):
        """Send direct response for chitchat"""
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CHAT_RESPONSE_CHUNK,
            payload={
                "content": decision.message_to_client,
                "is_final": True,
                "chunk_type": "TEXT"
            }
        )
        await self.router.send_to_client(
            session_id=session_id,
            message_type=MessageType.CHAT_RESPONSE_COMPLETE,
            payload={}
        )
```

---

## 📊 Performance Expectations

| Detection Method | Latency | Cost per 1000 requests | Accuracy |
|------------------|---------|------------------------|----------|
| Rule-based | < 1ms | $0 | 95%+ (for covered patterns) |
| ML Classifier | 10-50ms | ~$0.01 (compute) | 85-90% |
| LLM (gpt-4o-mini) | 200-500ms | ~$0.50 | 95%+ |
| Hybrid (avg) | 5-100ms | ~$0.05 | 92%+ |

### Distribution Expectation

```
┌─────────────────────────────────────────────────────────────────┐
│ Request Distribution by Detection Method                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Rule-Based: ████████████████████████████████████████  65%       │
│ ML Classifier: ██████████████████████  25%                      │
│ LLM Fallback: ██████  10%                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing Intent Detection

```python
# tests/test_intent_detection.py

import pytest
from be_inferflow_protocol.cux.hybrid_intent_detector import HybridIntentDetector

class TestIntentDetection:
    
    @pytest.fixture
    def detector(self):
        return HybridIntentDetector(
            rule_detector=RuleBasedDetector(),
            ml_classifier=None,  # Skip ML in unit tests
            llm_detector=None
        )
    
    @pytest.mark.parametrize("message,expected_type,expected_category", [
        ("xin chào", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("hello", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("Chào bạn", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("Hi", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("tạm biệt", IntentType.FAREWELL, IntentCategory.CHITCHAT),
        ("cảm ơn bạn", IntentType.THANKS, IntentCategory.CHITCHAT),
        ("Đèn bị hỏng", IntentType.INCIDENT_REPORT, IntentCategory.TOOL_CALL),
        ("Kiểm tra bưu kiện", IntentType.PACKAGE_CHECK, IntentCategory.TOOL_CALL),
        ("Đặt chỗ bể bơi", IntentType.BOOKING_FLOW, IntentCategory.AGENTIC_FLOW),
    ])
    def test_rule_based_detection(self, detector, message, expected_type, expected_category):
        result = detector.rule_detector.detect(message)
        assert result is not None
        assert result.intent_type == expected_type
        assert result.category == expected_category

    def test_slot_extraction(self, detector):
        result = detector.rule_detector.detect("Đèn hành lang tầng 5 bị hỏng")
        assert result.slots.get("facility") == "đèn"
        assert result.slots.get("location") == "hành lang tầng 5"

        result = detector.rule_detector.detect("Đặt bể bơi 3h chiều nay")
        assert result.slots.get("facility") == "swimming_pool"
```

---

## 📚 References

1. **Rasa NLU** - Intent classification architecture
2. **Dialogflow** - Entity extraction patterns
3. **Microsoft LUIS** - Hierarchical intent design
4. **spaCy** - Vietnamese NLP processing
5. **Sentence Transformers** - Multilingual embeddings

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-11  
**Author**: InferFlow Team
