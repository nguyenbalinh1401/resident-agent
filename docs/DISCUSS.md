# Pulse Chat Services - Discussion Log

## Overview

This document captures the architectural discussions and decisions made during the development of Pulse Chat Services integration with Pulse Backend (.NET).

---

## Discussion 1: Chat Session Handling for Multiple User Roles

### Question
> Chatbot này hỗ trợ cả cư dân, ban quản lý của chung cư. Vậy handle chat session thế nào?

### Current State

| Component | Implementation |
|-----------|----------------|
| **Session ID** | Auto-generate: `session_{user_id}` or user-provided |
| **State Storage** | In-memory dictionary (no persistence) |
| **Role from JWT** | Token contains `sub`, `role`, `exp` |
| **Capability Check** | `AllowanceClient` checks permissions based on role |

### Role-Based Capabilities

```python
DEFAULT_CAPABILITIES = {
    "resident": ["REPORT_INCIDENT", "CHECK_PACKAGE", "VIEW_BILLS", "BOOK_AMENITY"],
    "staff": [...resident + "APPROVE_BOOKING", "VIEW_ALL_TICKETS", "MANAGE_AMENITIES"],
    "admin": ["*"]  # All permissions
}
```

### Flow

1. JWT token → extract `user_id` + `role`
2. CUX Orchestrator → check allowance (capability)
3. Only suggest actions user has permission for
4. Store history in in-memory state manager

### Limitations

- Session lost on app restart
- No cross-instance session sharing
- Need Redis/DB for production

---

## Discussion 2: Backend API Integration & Dynamic Allowance

### Question 1
> Chatbot đã gọi được data từ bên backend app thông qua MCP chưa?

### Answer
**No MCP integration.** Current communication uses HTTP REST API via `httpx.AsyncClient`.

**PulseClient** (`src/resident_agent/clients/pulse_client.py`) wraps all API calls:
- Authentication: `/api/Users/login`, `/api/Users/register`
- Bills, Packages, Bookings, Tickets, etc.

### Question 2
> Services cung cấp thì có, nhưng allowance thì liệu có list, update, chỉnh sửa dynamic theo services được không?

### Answer
**Yes!** Pulse Backend already has RBAC (Role-Based Access Control):

| Entity | Description |
|--------|-------------|
| `Permissions` | Resource + Action (e.g., "Bills.View") |
| `Roles` | Role definitions |
| `RolePermission` | Mapping Role ↔ Permission |
| `UserRoleMapping` | Mapping User ↔ Role |

**Existing APIs (Admin only):**
- `GET/POST /api/Permissions` - List/Create permissions
- `GET/POST /api/Roles` - List/Create roles
- `POST/DELETE /api/Roles/{roleId}/permissions/{permId}` - Add/Remove permission
- `GET /api/UserRoles/{user_id}` - Get user's roles

**Gap:** Chat API currently uses mock allowance data, needs integration with Pulse Backend.

### Permission Structure

```
Permission = Resource + Action
Example: "Bills.View", "Packages.View", "Amenities.Book"
```

---

## Discussion 3: CUX Action Generation Logic

### Question
> Bạn hãy đề xuất 3 giải pháp cho CUX tạo action theo logic.

### Three Proposed Solutions

#### Solution 1: Dynamic Action Registry (Backend-Driven)
- Actions defined in database
- Load from Pulse Backend API
- Admin can add/edit/delete actions via UI
- A/B test action labels

#### Solution 2: Intent-Triggered Workflow Actions
- Actions auto-generated from LangGraph workflow definitions
- Single source of truth (workflows)
- Auto-sync when adding new workflows
- Less flexible for ad-hoc actions

#### Solution 3: Hybrid LLM + Rule Engine (Recommended)
- Combine LLM flexibility with Rule Engine reliability
- Fast path for known intents (no LLM needed)
- Flexible for edge cases
- Context-aware from workflow state
- Capability filtering built-in

### Action Categories

**By Intent Type:**

| Intent | Primary Action | Secondary Actions |
|--------|----------------|-------------------|
| `INCIDENT_REPORT` | 🔧 Báo sự cố | 📋 Xem ticket, 📞 Hotline |
| `PACKAGE_CHECK` | 📦 Kiểm tra bưu kiện | 📍 Xem bản đồ, 📞 Lễ tân |
| `BILL_VIEW` | 💳 Xem hóa đơn | 💰 Thanh toán, 📊 Lịch sử |
| `AMENITY_BOOK` | 🏊 Đặt tiện ích | 📅 Lịch đặt, ❌ Hủy đặt |
| `SERVICE_REQUEST` | 📝 Yêu cầu dịch vụ | 📋 Theo dõi, 📞 Hỗ trợ |

**By User Role:**

| Role | Capabilities |
|------|-------------|
| **Resident** | All basic actions |
| **Staff** | + Approve bookings, View all tickets |
| **Admin** | + System management, Dashboard |

---

## Decisions Made

| Topic | Decision |
|-------|----------|
| **Auth Flow** | Token Passthrough - App sends Pulse JWT to Chat API |
| **Allowance API** | Use `/api/UserRoles/{user_id}` to get user permissions |
| **Action Generation** | Hybrid - Fetch actions from Backend, LLM selects relevant ones |

---

## Related Files

- `src/resident_agent/cux/orchestrator.py` - CUX Orchestrator
- `src/resident_agent/cux/allowance_client.py` - Permission checking
- `src/resident_agent/clients/pulse_client.py` - Pulse Backend client
- `src/resident_agent/workflows/` - LangGraph workflows

---

## Next Steps

1. [ ] Implement Token Passthrough in Chat API
2. [ ] Update AllowanceClient to call `/api/UserRoles/{user_id}`
3. [ ] Create Action Registry API in Pulse Backend
4. [ ] Update CUX to fetch and select actions dynamically

---

**Last Updated:** 2026-03-26
**Participants:** Development Team
