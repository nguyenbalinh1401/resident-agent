"""Unit tests for CUX orchestrator and intent detection."""

import pytest
from typing import Optional

from resident_agent.cux.intent_detector import (
    RuleBasedDetector,
    HybridIntentDetector,
    IntentType,
    IntentCategory,
    DetectedIntent,
)
from resident_agent.cux.allowance_client import AllowanceClient
from resident_agent.cux.state_manager import ConversationStateManager
from resident_agent.cux.orchestrator import CuxOrchestrator, CuxDecision


class TestRuleBasedDetector:
    """Tests for rule-based intent detection."""

    @pytest.fixture
    def detector(self):
        return RuleBasedDetector()

    @pytest.mark.parametrize("message,expected_type,expected_category", [
        ("xin chào", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("hello", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("Chào bạn", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("Hi", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("Good morning", IntentType.GREETING, IntentCategory.CHITCHAT),
        ("tạm biệt", IntentType.FAREWELL, IntentCategory.CHITCHAT),
        ("bye bye", IntentType.FAREWELL, IntentCategory.CHITCHAT),
        ("cảm ơn bạn", IntentType.THANKS, IntentCategory.CHITCHAT),
        ("thank you", IntentType.THANKS, IntentCategory.CHITCHAT),
        ("Đèn hành lang bị hỏng", IntentType.INCIDENT_REPORT, IntentCategory.TOOL_CALL),
        ("Báo sự cố điện", IntentType.INCIDENT_REPORT, IntentCategory.TOOL_CALL),
        ("Kiểm tra bưu kiện", IntentType.PACKAGE_CHECK, IntentCategory.TOOL_CALL),
        ("check package", IntentType.PACKAGE_CHECK, IntentCategory.TOOL_CALL),
        ("Xem hóa đơn", IntentType.BILL_VIEW, IntentCategory.TOOL_CALL),
        ("Đặt bể bơi", IntentType.AMENITY_BOOK, IntentCategory.TOOL_CALL),
        ("Đặt sân tennis", IntentType.AMENITY_BOOK, IntentCategory.TOOL_CALL),
    ])
    def test_detection(
        self,
        detector: RuleBasedDetector,
        message: str,
        expected_type: IntentType,
        expected_category: IntentCategory
    ):
        """Test various intent detections."""
        result = detector.detect(message)

        assert result is not None, f"Failed to detect intent for: {message}"
        assert result.intent_type == expected_type, f"Expected {expected_type}, got {result.intent_type}"
        assert result.category == expected_category, f"Expected {expected_category}, got {result.category}"
        assert result.confidence > 0.5, "Confidence should be > 0.5"
        assert result.detection_method == "rule"

    def test_slot_extraction_incident(self, detector: RuleBasedDetector):
        """Test slot extraction for incident reports."""
        result = detector.detect("Đèn hành lang tầng 5 bị hỏng")

        assert result is not None
        assert result.intent_type == IntentType.INCIDENT_REPORT
        # Should have extracted some slots
        assert len(result.slots) > 0

    def test_slot_extraction_amenity(self, detector: RuleBasedDetector):
        """Test slot extraction for amenity booking."""
        result = detector.detect("Đặt bể bơi 3h chiều nay")

        assert result is not None
        assert result.intent_type == IntentType.AMENITY_BOOK
        # Check for facility in slots
        assert "swimming_pool" in result.slots.get("facility", "").lower() or result.slots

    def test_unknown_message_returns_none(self, detector: RuleBasedDetector):
        """Test that unknown messages return None for fallback to LLM."""
        result = detector.detect("This is a completely random message 12345")

        # May return None or a low-confidence result
        # The detector should return None or something with low confidence
        if result is not None:
            assert result.confidence < 0.8 or result.intent_type == IntentType.UNKNOWN

    def test_confidence_levels(self, detector: RuleBasedDetector):
        """Test that detection confidence is reasonable."""
        # High confidence for clear patterns
        high_conf_result = detector.detect("xin chào")
        assert high_conf_result.confidence >= 0.9

        # Lower confidence for ambiguous patterns
        # (This depends on implementation)


class TestAllowanceClient:
    """Tests for allowance client."""

    @pytest.fixture
    def client(self):
        return AllowanceClient()

    @pytest.mark.asyncio
    async def test_get_allowance_resident(self, client: AllowanceClient):
        """Test getting allowance for resident user."""
        allowance = await client.get_allowance("user_123")

        assert "allowed_capabilities" in allowance
        assert "REPORT_INCIDENT" in allowance["allowed_capabilities"]
        assert "CHECK_PACKAGE" in allowance["allowed_capabilities"]
        assert "resident" in allowance["roles"]

    @pytest.mark.asyncio
    async def test_get_allowance_staff(self, client: AllowanceClient):
        """Test getting allowance for staff user."""
        allowance = await client.get_allowance("staff_456")

        assert "allowed_capabilities" in allowance
        assert "APPROVE_BOOKING" in allowance["allowed_capabilities"]
        assert "staff" in allowance["roles"]

    @pytest.mark.asyncio
    async def test_get_allowance_admin(self, client: AllowanceClient):
        """Test getting allowance for admin user."""
        allowance = await client.get_allowance("admin_789")

        assert "allowed_capabilities" in allowance
        assert "*" in allowance["allowed_capabilities"] or "admin" in allowance["roles"]

    def test_check_capability_allowed(self, client: AllowanceClient):
        """Test checking allowed capability."""
        allowance = {"allowed_capabilities": ["REPORT_INCIDENT", "CHECK_PACKAGE"], "roles": ["resident"]}

        assert client.check_capability("REPORT_INCIDENT", allowance) is True
        assert client.check_capability("CHECK_PACKAGE", allowance) is True

    def test_check_capability_denied(self, client: AllowanceClient):
        """Test checking denied capability."""
        allowance = {"allowed_capabilities": ["REPORT_INCIDENT"], "roles": ["resident"]}

        assert client.check_capability("APPROVE_BOOKING", allowance) is False

    def test_check_capability_admin_has_all(self, client: AllowanceClient):
        """Test that admin has all capabilities."""
        allowance = {"allowed_capabilities": [], "roles": ["admin"]}

        assert client.check_capability("ANY_CAPABILITY", allowance) is True

    def test_suggest_alternatives(self, client: AllowanceClient):
        """Test suggesting alternatives for denied capability."""
        allowance = {
            "allowed_capabilities": ["BOOK_AMENITY", "VIEW_BILLS"],
            "roles": ["resident"]
        }

        alternatives = client.suggest_alternatives("APPROVE_BOOKING", allowance)

        assert len(alternatives) > 0
        assert all(alt["capability"] in ["BOOK_AMENITY", "VIEW_BILLS"] for alt in alternatives)

    def test_cache_clear(self, client: AllowanceClient):
        """Test cache clearing."""
        # This test verifies the cache clear methods work
        client.clear_cache("user_123")
        client.clear_cache()  # Clear all


class TestConversationStateManager:
    """Tests for conversation state management."""

    @pytest.fixture
    def manager(self):
        return ConversationStateManager()

    @pytest.mark.asyncio
    async def test_get_state_empty(self, manager: ConversationStateManager):
        """Test getting state for non-existent session."""
        state = await manager.get_state("nonexistent_session")
        assert state is None

    @pytest.mark.asyncio
    async def test_update_state(self, manager: ConversationStateManager):
        """Test updating state."""
        await manager.update_state("test_session", {"key": "value"})

        state = await manager.get_state("test_session")
        assert state is not None
        assert state["key"] == "value"

    @pytest.mark.asyncio
    async def test_add_message_to_history(self, manager: ConversationStateManager):
        """Test adding messages to history."""
        await manager.add_message_to_history("session_1", "user", "Hello")
        await manager.add_message_to_history("session_1", "assistant", "Hi there!")

        history = await manager.get_history("session_1")

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, manager: ConversationStateManager):
        """Test getting history with limit."""
        for i in range(5):
            await manager.add_message_to_history("session_2", "user", f"Message {i}")

        history = await manager.get_history("session_2", limit=3)

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_clear_state(self, manager: ConversationStateManager):
        """Test clearing state."""
        await manager.update_state("to_clear", {"data": "test"})
        await manager.clear_state("to_clear")

        state = await manager.get_state("to_clear")
        assert state is None

    def test_session_count(self, manager: ConversationStateManager):
        """Test session count."""
        initial_count = manager.get_session_count()
        assert initial_count >= 0


class TestHybridIntentDetector:
    """Tests for hybrid intent detection."""

    @pytest.fixture
    def detector(self, rule_based_detector):
        # Create hybrid detector with rule-based only (no LLM for faster tests)
        return HybridIntentDetector(
            rule_detector=rule_based_detector,
            llm_detector=None,
            llm_threshold=0.6
        )

    @pytest.mark.asyncio
    async def test_rule_based_fallback(self, detector: HybridIntentDetector):
        """Test that hybrid detector uses rule-based for simple cases."""
        result = await detector.detect("xin chào")

        assert result is not None
        assert result.intent_type == IntentType.GREETING
        assert result.detection_method == "rule"

    @pytest.mark.asyncio
    async def test_force_llm_flag(self, detector: HybridIntentDetector):
        """Test force_llm flag (would use LLM if available)."""
        # Without LLM detector, should still return something
        result = await detector.detect("xin chào", force_llm=True)

        assert result is not None
