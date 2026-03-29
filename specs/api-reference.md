# API Reference

> **Note:** This documents the **Resident Agent** API endpoints.
> For Pulse Backend (.NET) API, see `app/Pulse-dotnetBE/README.md`.

## Base URL

| Service | URL |
|---------|-----|
| **Resident Agent** | `http://localhost:8000` |
| **Pulse Backend** | `http://localhost:5000` |

## Chat via SSE Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/chat/stream` | SSE | Bearer JWT | Stream chat responses in real-time |
| `/chat` | POST | Bearer JWT | Send single message |
| `/action` | POST | Bearer JWT | Execute suggested action |
| `/auth/login` | POST | None | Login and get JWT token |

## JSON Schema

### Chat Request

```json
{
  "message": "Kiểm tra bưu kiện",
  "session_id": "session_123"
}
```

### Chat Response with Actions

```json
{
  "message": "Bạn có 2 bưu kiện chờ nhận...",
  "actions": [
    {
      "id": "check_package",
      "label": "Xem chi tiết",
      "action_type": "navigate",
      "params": {"screen": "packages"},
      "style": "primary"
    }
  ],
  "session_id": "session_123"
}
```

### Action Button Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique action identifier |
| `label` | string | Button display text |
| `action_type` | string | Action type for Flutter to handle |
| `params` | object | Additional parameters |
| `style` | string | Visual style: `primary`, `secondary`, `outline` |

## Flutter Action Handling

When user taps an action button, Flutter app uses `action_type` to determine behavior:

### Action Types & Navigation

| action_type | Flutter Screen | Description |
|-------------|----------------|-------------|
| `navigate` | Dynamic | Navigate to screen in `params.screen` |
| `report_incident` | `IncidentReportPage` | Open incident form |
| `check_package` | `PackagesPage` | View packages list |
| `view_bills` | `BillsPage` | View bills list |
| `book_amenity` | `BookingPage` | Open amenity booking |
| `service_request` | `ServiceRequestPage` | Open service request form |
| `make_payment` | `PaymentPage` | Open payment flow |
| `deeplink` | Dynamic | Open deep link in `params.url` |

### Flutter Example

```dart
void handleActionButton(ActionButton action) {
  switch (action.actionType) {
    case 'navigate':
      final screen = action.params['screen'];
      Navigator.pushNamed(context, '/$screen');
      break;
    case 'check_package':
      Navigator.pushNamed(context, '/packages');
      break;
    case 'report_incident':
      Navigator.pushNamed(context, '/incident/report');
      break;
    // ... handle other action types
  }
}
```

### Navigation via `params.screen`

For generic navigation, use `action_type: "navigate"` with `params.screen`:

```json
{
  "id": "view_packages",
  "label": "Xem chi tiết",
  "action_type": "navigate",
  "params": {"screen": "packages"},
  "style": "primary"
}
```

Flutter routes mapping:

```dart
final routes = {
  '/packages': (context) => PackagesPage(),
  '/bills': (context) => BillsPage(),
  '/bookings': (context) => BookingsPage(),
  '/tickets': (context) => TicketsPage(),
  // ...
};
```

## SSE Event Types

| Type | Description |
|------|-------------|
| `thinking` | AI is processing |
| `content` | Text content chunk |
| `action` | Suggested action buttons |
| `complete` | Stream finished |
| `error` | Error occurred |
