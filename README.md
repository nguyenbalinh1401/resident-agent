# Pulse - Intelligent Resident Services & Management System

## Overview

Pulse (SP26SE129) is an intelligent resident services platform that replaces traditional forms with a conversational AI interface. The system provides "Concierge-level" service—instant, personalized, and effortless interaction for luxury residential living.

## Core Features

### AI Chatbot Service (LangGraph + CUX Orchestrator)
- **Virtual Receptionist**: 24/7 assistant for building policies and services
- **Intelligent Action Handler**: Intent recognition triggers automated workflows
- **Auto-Execution**: Extracts key details (Location, Severity) without manual forms

### Core Services
- 🛠️ **Incident Management**: AI-powered ticket creation and routing
- 💳 **Payment Gateway**: Bill viewing and online payment
- 🏊 **Amenities Booking**: Real-time slot checking and booking
- 📦 **Package Logistics**: Automated package alerts and notifications
- 🎫 **Resident Services**: Digital requests for cards and registrations

---

## Architecture

### Tech Stack

| Component | Technology |
|-----------|------------|
| **Workflow Engine** | LangGraph (Stateful agentic workflows) |
| **Intent Detection** | CUX Orchestrator (Rule-based + ML + LLM hybrid) |
| **LLM Integration** | OpenAI Library (gpt-4o-mini) |
| **Streaming Protocol** | Server-Sent Events (SSE) |
| **Data Serialization** | Google Protobuf |
| **Authentication** | JWT (JSON Web Tokens) |
| **Backend** | Python (FastAPI) |
| **Testing** | Pytest, Locust (load testing) |
| **Mobile** | Flutter |
| **Admin Dashboard** | Next.js |

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Pulse Chat Services                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Flutter    │    │   Next.js    │    │  Staff App   │      │
│  │  (Residents) │    │   (Admin)    │    │  (Mobile)    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │              │
│         └───────────────────┼───────────────────┘              │
│                             │                                  │
│                    ┌────────▼────────┐                         │
│                    │   SSE Protocol   │                         │
│                    │  (Real-time)     │                         │
│                    └────────┬────────┘                         │
│                             │                                  │
│                    ┌────────▼────────┐                         │
│                    │  JWT Auth Layer  │                         │
│                    │  (Bearer Token)  │                         │
│                    └────────┬────────┘                         │
│                             │                                  │
│                    ┌────────▼────────┐                         │
│                    │  CUX Orchestrator│                        │
│                    │  - Intent Detect │                         │
│                    │  - Allowance Check│                        │
│                    │  - State Mgmt    │                         │
│                    └────────┬────────┘                         │
│                             │                                  │
│                    ┌────────▼────────┐                         │
│                    │  LangGraph Engine│                         │
│                    │  - StateGraph    │                         │
│                    │  - Workflows     │                         │
│                    │  - Checkpointing │                         │
│                    └────────┬────────┘                         │
│                             │                                  │
│         ┌───────────────────┼───────────────────┐              │
│         │                   │                   │              │
│    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐          │
│    │ OpenAI  │        │PostgreSQL│       │Protobuf │          │
│    │   API   │        │ Database │       │Schema   │          │
│    └─────────┘        └──────────┘        └─────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Service Separation

**Pulse Chat Services (This Repository)**
- Chat and conversational AI
- Intent recognition and workflow execution
- Real-time SSE streaming
- Protobuf message handling
- JWT Authentication

**Backend Services (Separate Repository)**
- RESTful API endpoints
- CRUD operations
- Admin dashboard APIs
- Integration with external payment gateways

---

## Key Components

### CUX Orchestrator

The CUX (Conversation Understanding & eXecution) Orchestrator is the central brain:

- **Intent Detection**: Hybrid approach (Rule-based → ML → LLM)
- **Allowance Checking**: Validates user permissions before actions
- **Conversation State**: Maintains context across multi-turn conversations
- **Flow Routing**: Routes to appropriate LangGraph workflows

**Supported Intents:**
- **Chitchat**: greeting, farewell, thanks
- **General Ask**: policy questions, service info, contact info
- **Tool Call**: incident_report, package_check, bill_view, amenity_book
- **Agentic Flow**: incident_management, booking_flow, payment_flow

For detailed documentation, see [CUX.md](CUX.md).

### LangGraph Workflows

Stateful workflows for resident services:

| Workflow | Description | State Graph Nodes |
|----------|-------------|-------------------|
| `incident_report` | Create maintenance tickets | extract_info → create_ticket → notify_maintenance |
| `package_check` | Query packages for user | query_packages → format_details |
| `bill_view` | View unpaid bills | query_bills → format_details |
| `amenity_book` | Book facilities | check_availability → request_confirmation → confirm_booking |
| `payment_flow` | Process payments | get_bill_details → select_method → process_payment → update_status |

---

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- OpenAI API Key
- Git
- Redis (for caching, optional)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/resident-agent.git
cd resident-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python scripts/init_db.py

# Run migrations
alembic upgrade head
```

### Configuration

Create a `.env` file in the project root:

```bash
# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/pulse

# Redis (optional)
REDIS_URL=redis://localhost:6379

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Running the Server

```bash
# Development server with auto-reload
uvicorn src.resident_agent.main:app --reload --port 8000

# Production server
gunicorn src.resident_agent.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Usage Examples

### Chat with the AI Agent

```python
from resident_agent.workflows.executor import LangGraphExecutor
from resident_agent.cux.orchestrator import CuxOrchestrator

# Initialize
cux = CuxOrchestrator(intent_detector, allowance_client, state_manager)
executor = LangGraphExecutor()

# Process user message
decision = await cux.process(
    session_id="sess_123",
    user_id="user_456",
    message="Đèn hành lang tầng 5 bị hỏng"
)

# Execute workflow if needed
if decision.workflow_to_trigger:
    result = await executor.execute_intent_workflow(
        intent_type=decision.intent.intent_type.value,
        context={
            "user_id": "user_456",
            "session_id": "sess_123",
            **decision.intent.slots
        }
    )
    print(result["message"])
    # Output: "Đã tiếp nhận báo cáo: đèn tại hành lang tầng 5. Mã ticket: #T-12345"
```

### SSE Streaming

```python
import asyncio
import httpx

async def chat_stream():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/chat/stream",
            json={"message": "Kiểm tra bưu kiện"},
            headers={"Authorization": "Bearer YOUR_TOKEN"},
            timeout=None
        ) as response:
            async for chunk in response.aiter_lines():
                if chunk.startswith("data: "):
                    data = json.loads(chunk[6:])
                    if data.get("type") == "message":
                        print(data["content"])

asyncio.run(chat_stream())
```

---

## API Reference

### WebSocket/SSE Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/chat/stream` | SSE | Bearer JWT | Stream chat responses in real-time |
| `/chat` | POST | Bearer JWT | Send single message |
| `/action` | POST | Bearer JWT | Execute suggested action |
| `/auth/login` | POST | None | Login and get JWT token |
| `/auth/refresh` | POST | Refresh token | Refresh access token |

### Protobuf Schema

```protobuf
// proto/chat.proto

syntax = "proto3";
package pulse;

// Chat message from client
message ChatMessage {
    string session_id = 1;
    string user_id = 2;
    string content = 3;
    int64 timestamp = 4;
}

// Chat response to client
message ChatResponse {
    enum MessageType {
        THINKING = 0;
        CONTENT = 1;
        ACTION = 2;
        COMPLETE = 3;
        ERROR = 4;
    }
    MessageType type = 1;
    string content = 2;
    repeated Action actions = 3;
    string error = 4;
}

// Suggested action button
message Action {
    string id = 1;
    string label = 2;
    string action_type = 3;
    map<string, string> params = 4;
    string style = 5;  // primary, secondary, outline
}

// Authentication messages
message LoginRequest {
    string email = 1;
    string password = 2;
}

message LoginResponse {
    string access_token = 1;
    string refresh_token = 2;
    string token_type = 3;
    int64 expires_in = 4;
}
```

---

## Authentication (JWT)

### Overview

Pulse Chat Services uses JWT (JSON Web Tokens) for authentication. All protected endpoints require a valid Bearer token in the Authorization header.

### Getting a Token

```bash
# Login to get access token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Using the Token

```bash
# Include token in Authorization header
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"message": "Kiểm tra bưu kiện"}'
```

### Token Refresh

```bash
# Refresh access token before expiry
curl -X POST http://localhost:8000/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

### Python Client Example

```python
import requests
from typing import Optional

class PulseChatClient:
    """Python client for Pulse Chat Services with JWT authentication"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

    def login(self, email: str, password: str):
        """Login and store tokens"""
        response = requests.post(f"{self.base_url}/auth/login", json={
            "email": email,
            "password": password
        })
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        return data

    def _get_headers(self):
        """Get headers with auth token"""
        if not self.access_token:
            raise ValueError("Not logged in")
        return {"Authorization": f"Bearer {self.access_token}"}

    def send_message(self, message: str, session_id: str = None):
        """Send chat message"""
        response = requests.post(
            f"{self.base_url}/chat",
            headers={**self._get_headers(), "Content-Type": "application/json"},
            json={"message": message, "session_id": session_id}
        )

        if response.status_code == 401:
            # Token expired, refresh
            self._refresh_and_retry(message, session_id)
            return self.send_message(message, session_id)

        response.raise_for_status()
        return response.json()

    def _refresh_and_retry(self, message: str, session_id: str):
        """Refresh token and retry request"""
        self.refresh_tokens()
        response = requests.post(
            f"{self.base_url}/chat",
            headers={**self._get_headers(), "Content-Type": "application/json"},
            json={"message": message, "session_id": session_id}
        )
        response.raise_for_status()
        return response.json()

    def refresh_tokens(self):
        """Refresh access token"""
        response = requests.post(
            f"{self.base_url}/auth/refresh",
            headers={"Authorization": f"Bearer {self.refresh_token}"}
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        return data

# Usage
client = PulseChatClient()
client.login("user@example.com", "password")
response = client.send_message("Kiểm tra bưu kiện")
print(response["message"])
```

---

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/

# Run with coverage
pytest --cov=src/resident_agent tests/unit/

# Run specific test file
pytest tests/unit/test_cux_orchestrator.py -v
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/ -v

# Test with test database
TEST_DATABASE_URL="postgresql://test:test@localhost/pulse_test" \
  pytest tests/integration/
```

### Test Examples

```python
# tests/unit/test_cux_orchestrator.py

import pytest
from resident_agent.cux.orchestrator import CuxOrchestrator, CuxDecision
from resident_agent.cux.intent_detector import IntentType, IntentCategory

class TestCuxOrchestrator:
    @pytest.fixture
    async def orchestrator(self, mock_intent_detector, mock_allowance_client, mock_state_manager):
        return CuxOrchestrator(
            intent_detector=mock_intent_detector,
            allowance_client=mock_allowance_client,
            state_manager=mock_state_manager
        )

    @pytest.mark.asyncio
    async def test_greeting_intent(self, orchestrator):
        decision = await orchestrator.process(
            session_id="test_123",
            user_id="user_456",
            message="xin chào"
        )
        assert decision.decision_type == "proceed"
        assert decision.allowed == True
        assert decision.workflow_to_trigger is None

    @pytest.mark.asyncio
    async def test_incident_report_workflow(self, orchestrator):
        decision = await orchestrator.process(
            session_id="test_123",
            user_id="user_456",
            message="Đèn hành lang bị hỏng"
        )
        assert decision.decision_type == "proceed"
        assert decision.workflow_to_trigger == "incident_report"
        assert "facility" in decision.workflow_params

# tests/integration/test_workflows.py

import pytest
from resident_agent.workflows.executor import LangGraphExecutor
from resident_agent.workflows.states import IncidentState

class TestWorkflows:
    @pytest.fixture
    def executor(self):
        return LangGraphExecutor()

    @pytest.mark.asyncio
    async def test_incident_workflow(self, executor):
        result = await executor.execute_workflow(
            workflow_name="incident_report",
            initial_state={
                "user_id": "test_user",
                "session_id": "test_session",
                "facility": "đèn",
                "location": "hành lang tầng 5",
                "severity": "medium",
                "messages": []
            }
        )
        assert result["success"] == True
        assert "ticket_id" in result["state"]
        assert result["state"]["message"] is not None

# tests/integration/test_auth.py

import pytest
from fastapi.testclient import TestClient
from resident_agent.main import app

class TestAuthentication:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_login_success(self, client):
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, client):
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrong_password"
        })
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        response = client.post("/chat", json={"message": "test"})
        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, client):
        # First login
        login_response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        token = login_response.json()["access_token"]

        # Use token
        response = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "test"}
        )
        assert response.status_code == 200
```

### Load Testing

```bash
# Using locust for load testing
locust -f tests/load/chat_load_test.py --host=http://localhost:8000

# Expected performance targets:
# - Chat response: < 3 seconds (including LLM)
# - Token refresh: < 100ms
# - Concurrent users: 100+ without degradation
```

---

## UI Demo

### Simple HTML/JS Demo Client

Save this as `demo.html` and open in your browser:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pulse AI - Chat Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 5px 0 0; opacity: 0.9; font-size: 14px; }
        #chat-box {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        .message {
            margin: 10px 0;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 80%;
            word-wrap: break-word;
        }
        .user {
            background: #667eea;
            color: white;
            margin-left: auto;
        }
        .bot {
            background: white;
            color: #333;
            border: 1px solid #e0e0e0;
        }
        .typing {
            font-style: italic;
            color: #999;
            font-size: 12px;
        }
        .actions {
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .action-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .action-btn.primary {
            background: #667eea;
            color: white;
        }
        .action-btn.secondary {
            background: #e0e0e0;
            color: #333;
        }
        .action-btn.outline {
            background: white;
            border: 1px solid #667eea;
            color: #667eea;
        }
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        #input-area {
            display: flex;
            gap: 10px;
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
        }
        #message-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #ddd;
            border-radius: 24px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        #message-input:focus {
            border-color: #667eea;
        }
        #send-btn {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 24px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.2s;
        }
        #send-btn:hover {
            background: #5568d3;
        }
        .status {
            padding: 8px 16px;
            text-align: center;
            font-size: 12px;
            color: #999;
            background: #f8f9fa;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Pulse AI - Chat Demo</h1>
            <p>Trợ lý ảo cư dân 24/7</p>
        </div>
        <div class="status" id="status">Connecting...</div>
        <div id="chat-box"></div>
        <div id="input-area">
            <input type="text" id="message-input" placeholder="Nhập tin nhắn..." />
            <button id="send-btn" onclick="sendMessage()">Gửi</button>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:8000';
        let accessToken = localStorage.getItem('access_token');
        let refreshToken = localStorage.getItem('refresh_token');
        let sessionId = 'demo_' + Date.now();

        // Update status
        function setStatus(text, isConnected = null) {
            const statusEl = document.getElementById('status');
            statusEl.textContent = text;
            if (isConnected !== null) {
                statusEl.style.color = isConnected ? '#28a745' : '#dc3545';
            }
        }

        // Login function
        async function login() {
            try {
                const response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: 'demo@example.com',
                        password: 'demo123'
                    })
                });
                if (response.ok) {
                    const data = await response.json();
                    accessToken = data.access_token;
                    refreshToken = data.refresh_token;
                    localStorage.setItem('access_token', accessToken);
                    localStorage.setItem('refresh_token', refreshToken);
                    setStatus('Đã kết nối', true);
                    return true;
                }
            } catch (e) {
                console.error('Login failed:', e);
            }
            setStatus('Không thể kết nối', false);
            return false;
        }

        // Refresh token
        async function refreshAccessToken() {
            try {
                const response = await fetch(`${API_BASE}/auth/refresh`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${refreshToken}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    accessToken = data.access_token;
                    localStorage.setItem('access_token', accessToken);
                    return true;
                }
            } catch (e) {
                console.error('Token refresh failed:', e);
            }
            return false;
        }

        function addMessage(text, type, isTyping = false) {
            const box = document.getElementById('chat-box');
            const div = document.createElement('div');
            div.className = `message ${type} ${isTyping ? 'typing' : ''}`;
            div.textContent = text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
            return div;
        }

        function showActions(actions) {
            const box = document.getElementById('chat-box');
            const div = document.createElement('div');
            div.className = 'actions';
            actions.forEach(action => {
                const btn = document.createElement('button');
                btn.className = `action-btn ${action.style || 'secondary'}`;
                btn.textContent = action.label;
                btn.onclick = () => executeAction(action);
                div.appendChild(btn);
            });
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        async function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            if (!message) return;

            input.value = '';
            addMessage(message, 'user');

            if (!accessToken) {
                const loggedIn = await login();
                if (!loggedIn) {
                    addMessage('Vui lòng đăng nhập để sử dụng dịch vụ.', 'bot');
                    return;
                }
            }

            try {
                const response = await fetch(`${API_BASE}/chat`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${accessToken}`
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    })
                });

                if (response.status === 401) {
                    // Token expired, refresh
                    const refreshed = await refreshAccessToken();
                    if (refreshed) {
                        return sendMessage();
                    }
                    throw new Error('Session expired');
                }

                if (response.ok) {
                    const data = await response.json();
                    addMessage(data.message || 'Đang xử lý...', 'bot');
                    if (data.actions && data.actions.length > 0) {
                        showActions(data.actions);
                    }
                } else {
                    throw new Error('Request failed');
                }
            } catch (e) {
                console.error('Error:', e);
                addMessage('Có lỗi xảy ra. Vui lòng thử lại.', 'bot');
            }
        }

        async function executeAction(action) {
            addMessage(`Đang thực hiện: ${action.label}...`, 'user');

            if (!accessToken) return;

            try {
                const response = await fetch(`${API_BASE}/action`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${accessToken}`
                    },
                    body: JSON.stringify(action)
                });

                if (response.status === 401) {
                    await refreshAccessToken();
                    return executeAction(action);
                }

                if (response.ok) {
                    const data = await response.json();
                    addMessage(data.message || 'Hoàn thành!', 'bot');
                    if (data.actions && data.actions.length > 0) {
                        showActions(data.actions);
                    }
                }
            } catch (e) {
                console.error('Action error:', e);
                addMessage('Không thể thực hiện hành động.', 'bot');
            }
        }

        // Enter key to send
        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        // Auto login on load
        window.onload = () => {
            if (accessToken) {
                setStatus('Đã kết nối', true);
            } else {
                login();
            }
        };
    </script>
</body>
</html>
```

### Example Conversations

**Conversation 1: Incident Report**
```
User: Đèn hành lang tầng 5 bị hỏng
Bot: Đã tiếp nhận báo cáo: đèn tại hành lang tầng 5. Mức độ: medium.
     Mã ticket: #T-12345. Đội bảo trì sẽ xử lý trong 24h.

Actions: [📋 Theo dõi phiếu] [📞 Gọi hotline] [🔧 Báo sự cố khác]
```

**Conversation 2: Package Check**
```
User: Tôi có bưu kiện nào không?
Bot: Bạn có 2 bưu kiện chờ nhận tại quầy lễ tân.

     Chi tiết bưu kiện:
     • P-1001 - Shopee - Ng nhận: 2026-03-01
     • P-1002 - Lazada - Ng nhận: 2026-03-02

Actions: [📍 Xem trên bản đồ] [📞 Gọi lễ tân]
```

**Conversation 3: Amenity Booking**
```
User: Đặt bể bơi 3h chiều nay
Bot: Bể bơi còn trống vào 3h chiều nay. Bạn có muốn đặt không?

User: [Confirm]
Bot: Đã đặt bể bơi thành công vào 3h chiều nay. Mã đặt chỗ: #BK-67890

Actions: [📋 Xem lịch đặt] [🗑️ Hủy đặt]
```

---

## Development Roadmap

### Phase 1: Core Chat (Current)
- [x] CUX Orchestrator documentation
- [x] LangGraph workflow definitions
- [ ] SSE streaming endpoint
- [ ] Protobuf schema implementation
- [ ] OpenAI integration
- [ ] JWT Authentication
- [ ] Unit & integration tests

### Phase 2: Backend Integration
- [ ] RESTful API endpoints
- [ ] PostgreSQL integration with SQLAlchemy
- [ ] Redis caching layer
- [ ] Admin dashboard APIs

### Phase 3: Mobile & Web
- [ ] Flutter mobile app (Residents & Staff)
- [ ] Next.js admin dashboard
- [ ] Push notifications

### Phase 4: Advanced Features
- [ ] Multi-language support (Vietnamese, English)
- [ ] Voice integration
- [ ] Analytics dashboard
- [ ] File upload for incident photos

---

## Project Structure

```
resident-agent/
├── src/resident-agent/
│   ├── schema/              # Pydantic models (49 database entities)
│   │   ├── Users.py
│   │   ├── Tickets.py
│   │   ├── Packages.py
│   │   └── ...
│   ├── workflows/           # LangGraph workflow definitions
│   │   ├── states.py        # TypedDict state definitions
│   │   ├── registry.py      # Workflow registry
│   │   ├── executor.py      # LangGraph executor
│   │   ├── incident_workflow.py
│   │   ├── package_workflow.py
│   │   ├── bill_workflow.py
│   │   ├── booking_workflow.py
│   │   └── payment_workflow.py
│   ├── auth/                # JWT Authentication (to be implemented)
│   │   ├── __init__.py
│   │   ├── jwt_handler.py
│   │   ├── models.py
│   │   └── dependencies.py
│   ├── api/                 # FastAPI endpoints (to be implemented)
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── auth.py
│   │   └── sse.py
│   └── main.py              # FastAPI app entry point
├── tests/
│   ├── unit/                # Unit tests (pytest)
│   ├── integration/         # Integration tests
│   └── load/                # Load tests (locust)
├── CUX.md                   # CUX Orchestrator documentation
├── PROJECT_DESCRIPTION.md   # Project requirements
├── schema.xml               # Database ER diagram (Draw.io)
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to the main repository.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Project Code**: SP26SE129
**Version**: 1.0.0
**Last Updated**: March 2026
**Tech Stack**: LangGraph, OpenAI, SSE, Protobuf, JWT, FastAPI
