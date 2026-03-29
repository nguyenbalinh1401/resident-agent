# CUX Orchestrator - Architecture Overview

## Overview

Tài liệu này mô tả kiến trúc của **CUX Orchestrator** - thành phần sử dụng LLM với Function Calling để tự động detect intent và gọi tools (Pulse Backend APIs).

**Key Features:**
- Multimodal input (text + image/file)
- LLM-first với tool calling
- 3 intent types đơn giản

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CUX ORCHESTRATOR (LLM-First)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User Message ──────► LLM + Tool Definitions ──────► Response          │
│                              │                                          │
│                              ▼                                          │
│                    ┌─────────────────┐                                  │
│                    │  Function Call? │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│              ┌──────────────┼──────────────┐                            │
│              │ YES          │              │ NO                          │
│              ▼              │              ▼                            │
│    ┌─────────────────┐     │      ┌─────────────────┐                   │
│    │ Execute Tool    │     │      │ Return Answer   │                   │
│    │ (Pulse API)     │     │      │ + Actions       │                   │
│    └────────┬────────┘     │      └─────────────────┘                   │
│             │              │                                          │
│             ▼              │                                          │
│    ┌─────────────────┐     │                                          │
│    │ Tool Result     │     │                                          │
│    └────────┬────────┘     │                                          │
│             │              │                                          │
│             ▼              │                                          │
│    ┌─────────────────┐     │                                          │
│    │ LLM generates   │     │                                          │
│    │ final response  │     │                                          │
│    └─────────────────┘     │                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Intent Types (Simplified)

Chỉ **3 intent types** - LLM tự quyết định tool nào để gọi:

| Intent | Description | Handling |
|--------|-------------|----------|
| `chitchat` | Tâm sự, greeting, small talk | LLM trả lời trực tiếp |
| `agentic_flow` | User request cần thực hiện action | LLM detect + gọi tool tự động |
| `tool_call` | User click action button từ UI | Execute tool trực tiếp |

### Key Insight

**Không cần fine-grained intents** (view_bills, make_payment, etc.) - những đó là **Tool Definitions**. LLM sẽ tự chọn tool dựa trên user message.

---

## Multimodal Input

CUX hỗ trợ **text + image/file** (multimodal) tương tự Gemini API.

### Input Methods

| Method | Best For | Max Size | Persistence |
|--------|----------|----------|-------------|
| **Inline (base64)** | Real-time, small files | 20MB | None |
| **URL** | Public URLs, cloud storage | 100MB | None |

### Supported File Types

| Type | MIME Types | Use Case |
|------|------------|----------|
| **Image** | `image/jpeg`, `image/png`, `image/webp` | Báo sự cố kèm ảnh, OCR |
| **PDF** | `application/pdf` | Xem tài liệu, hóa đơn |
| **Text** | `text/plain`, `text/csv` | Log files, data export |

### Chat Request with Attachment

```json
{
  "message": "Báo sự cố vòi hình ảnh",
  "session_id": "session_123",
  "attachments": [
    {
      "type": "image",
      "data": "base64_encoded_data...",
      "mime_type": "image/jpeg"
    }
  ]
}
```

### URL Attachment

```json
{
  "message": "Tóm tắt tài liệu này",
  "attachments": [
    {
      "type": "url",
      "url": "https://example.com/document.pdf",
      "mime_type": "application/pdf"
    }
  ]
}
```

---

## Tool Definitions

Tools chính là **capabilities** của user. Trước khi gửi đến LLM, filter tools theo user allowance.

### Profile Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `get_profile` | PROFILE_VIEW | Xem thông tin căn hộ | - |
| `update_contact` | PROFILE_UPDATE | Cập nhật liên hệ | `phone`, `email` |
| `register_vehicle` | VEHICLE_REGISTER | Đăng ký xe | `plate_number`, `vehicle_type` |

### Payment Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `get_bills` | BILLS_VIEW | Xem hóa đơn | `period?`, `status?` |
| `make_payment` | BILLS_PAY | Thanh toán | `bill_id`, `method` |
| `get_payment_history` | BILLS_VIEW | Lịch sử thanh toán | `from_date?`, `to_date?` |

### Booking Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `get_amenities` | AMENITY_VIEW | Xem tiện ích có sẵn | - |
| `book_amenity` | AMENITY_BOOK | Đặt chỗ | `amenity_id`, `date`, `time_slot` |
| `cancel_booking` | AMENITY_BOOK | Hủy đặt chỗ | `booking_id` |
| `get_my_bookings` | AMENITY_VIEW | Xem lịch đặt | `status?` |

### Support Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `create_incident` | INCIDENT_REPORT | Báo sự cố | `type`, `location`, `description`, `urgency?` |
| `get_incident_status` | INCIDENT_VIEW | Kiểm tra phiếu | `ticket_id?` |
| `get_my_incidents` | INCIDENT_VIEW | Xem phiếu đã báo | `status?` |

### Visitor Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `register_visitor` | VISITOR_REGISTER | Đăng ký khách | `name`, `phone`, `visit_date`, `purpose` |
| `get_visitors` | VISITOR_VIEW | Xem khách đã đăng ký | `date?` |

### Package Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `get_packages` | PACKAGE_VIEW | Kiểm tra bưu kiện | `status?` |

### Notification Tools

| Tool | Capability | Description | Parameters |
|------|------------|-------------|------------|
| `get_announcements` | NOTIFICATION_VIEW | Xem thông báo | `limit?` |

---

## Flow Examples

### Flow 1: "Xem hóa đơn" (Agentic Flow với Tool)

```
User: "Xem hóa đơn tháng này"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM với available tools (filtered by user capabilities)     │
│                                                             │
│ Tools: [get_bills, get_payment_history, make_payment, ...]  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              LLM chọn: get_bills(period: "current")
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Execute: GET /api/bills?period=current                      │
│ Response: { bills: [{id: 1, amount: 150, status: "unpaid"}, │
│                       {id: 2, amount: 45, status: "unpaid"}] }│
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM generates response:                                     │
│                                                             │
│ "Bạn có 2 hóa đơn chưa thanh toán:                          │
│  • Phí quản lý: 150,000đ                                    │
│  • Tiền điện: 45,000đ                                       │
│  Tổng: 195,000đ"                                            │
│                                                             │
│ Actions: [Thanh toán ngay, Xem chi tiết]                    │
└─────────────────────────────────────────────────────────────┘
```

### Flow 2: Thiếu Params → Hỏi User

```
User: "Đặt chỗ tennis"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM analyzes: book_amenity needs: amenity_id, date, time    │
│                                                             │
│ Missing: date, time_slot                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM response (asks for missing params):                     │
│                                                             │
│ "Bạn muốn đặt sân tennis vào ngày nào? Và khung giờ nào?    │
│  Sân tennis hoạt động: 6:00 - 22:00"                        │
│                                                             │
│ Actions: [Hôm nay 17:00, Ngày mai 8:00, Xem lịch trống]     │
└─────────────────────────────────────────────────────────────┘
```

### Flow 3: Báo sự cố kèm Ảnh (Multimodal)

```
User: "Báo sự cố vòi nước rò rỉ" + [Ảnh]
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM với multimodal input (text + image)                        │
│                                                             │
│ Message: "Báo sự cố vòi nước rò rỉ"                         │
│ Attachments: [{type: "image", data: "base64..."}]            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              LLM phân tích: image + text → create_incident
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Tool call: create_incident(                                     │
│   type: "plumbing",                                            │
│   location: "khu vực bếp",                                     │
│   description: "Vòi nước rò rỉ",                               │
│   image_url: "https://storage/incident_123.jpg"               │
│ )                                                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM response:                                                   │
│                                                                 │
│ "✅ Đã tạo phiếu báo sự cố #12345                              │
│  Loại: Cấp nước                                                │
│  Vị trí: Khu vực bếp                                           │
│  Đơn vị sẽ kiểm tra trong 2h."                                  │
│                                                                 │
│ Actions: [📋 Theo dõi phiếu, 📷 Thêm ảnh, 🏠 Về trang chủ]     │
└─────────────────────────────────────────────────────────────┘
```

### Flow 4: Không có Data → Suggest Alternatives

```
User: "Kiểm tra bưu kiện"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Execute: GET /api/packages                                   │
│ Response: { packages: [] }                                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM response:                                               │
│                                                             │
│ "Hiện tại không có bưu kiện nào cho căn hộ của bạn.        │
│  Tôi sẽ thông báo khi có bưu kiện mới đến."                 │
│                                                             │
│ Actions: [Đặt lịch nhận hàng, Xem thông báo, Về trang chủ]  │
└─────────────────────────────────────────────────────────────┘
```

### Flow 5: Chitchat (Không cần Tool)

```
User: "Xin chào"
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM response directly (no tool needed):                     │
│                                                             │
│ "Xin chào! Tôi là Pulse AI, trợ lý 24/7 của bạn.           │
│  Hôm nay tôi có thể giúp gì?"                               │
│                                                             │
│ Actions: [Báo sự cố, Xem hóa đơn, Đặt tiện ích, Kiểm tra bưu kiện]│
└─────────────────────────────────────────────────────────────┘
```

### Flow 5: User Click Action Button (Tool Call)

```
User clicks: [🔧 Báo sự cố]
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ Intent: tool_call (from UI button)                          │
│ Action: report_incident                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ System triggers: create_incident flow                       │
│ Or: Navigate to incident form                               │
└─────────────────────────────────────────────────────────────┘
```

---

## JSON Response Schema

### CUX Response

```json
{
  "answer": "string - Text response to display",
  "actions": [
    {
      "id": "string",
      "label": "string - Button text with emoji",
      "action": "string - Action type",
      "params": { },
      "style": "primary | secondary | outline"
    }
  ],
  "tool_calls": [
    {
      "tool": "string - Tool name",
      "params": { },
      "result": { }
    }
  ]
}
```

### Tool Call Request (LLM → System)

```json
{
  "tool": "get_bills",
  "params": {
    "period": "current"
  }
}
```

### Tool Response (System → LLM)

```json
{
  "status": "success | error",
  "data": { },
  "error": "string | null"
}
```

---

## Action Types (UI Buttons)

Dùng cho action buttons trong UI. Khi user click → `tool_call` intent:

| Action | Description |
|--------|-------------|
| `view_profile` | Xem thông tin căn hộ |
| `update_contact` | Cập nhật liên hệ |
| `register_vehicle` | Đăng ký xe |
| `view_bills` | Xem hóa đơn |
| `make_payment` | Thanh toán |
| `payment_history` | Lịch sử thanh toán |
| `view_amenities` | Xem tiện ích |
| `book_amenity` | Đặt chỗ |
| `cancel_booking` | Hủy đặt chỗ |
| `report_incident` | Báo sự cố |
| `track_request` | Kiểm tra phiếu |
| `register_visitor` | Đăng ký khách |
| `check_package` | Kiểm tra bưu kiện |
| `view_announcements` | Xem thông báo |

---

## Performance Expectations

| Metric | Value |
|--------|-------|
| **LLM calls per request** | 1-2 (1 if no tool, 2 if tool needed) |
| **Model** | gpt-4o-mini |
| **Cost per request** | ~$0.001-0.002 |
| **Latency (no tool)** | 200-400ms |
| **Latency (with tool)** | 400-800ms |

---

## Key Benefits

| Aspect | Description |
|--------|-------------|
| **Simple** | Chỉ 3 intent types, không cần maintain patterns |
| **Flexible** | LLM handles natural language variations |
| **Scalable** | New tool = new definition, không cần code mới |
| **Smart** | LLM tự hỏi missing params, suggest alternatives |
| **Aligned** | Follows Claude/ChatGPT patterns |

---

**Document Version**: 3.0
**Last Updated**: 2026-03-29
