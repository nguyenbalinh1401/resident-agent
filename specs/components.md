# Key Components

## System Overview

| Service | Tech | Purpose |
|---------|------|---------|
| **Resident Agent** | Python/FastAPI | AI Chat, Intent Detection, Tool Orchestration |
| **Pulse Backend** | .NET 9 | Business API, CRUD, Payment |

---

## Resident Agent Components

### 1. Auth Layer

- JWT token validation
- Token passthrough (X-Pulse-Token)

### 2. API Layer

| Endpoint | Description |
|----------|-------------|
| `/auth/login` | Login, get Resident Agent JWT |
| `/chat` | Send message, get response |
| `/chat/stream` | SSE streaming chat |

### 3. SSE Handler

- Real-time streaming via Server-Sent Events
- Event types: `thinking`, `content`, `action`, `complete`, `error`

### 4. CUX Orchestrator

**LLM-first với Function Calling + Multimodal Input**

| Intent | Description |
|--------|-------------|
| `chitchat` | Tâm sự, không cần tool |
| `agentic_flow` | LLM tự detect + gọi tools |
| `tool_call` | User click action button |

Chi tiết: [CUX.md](./cux.md)

---

## Related Docs

| Document | Description |
|----------|-------------|
| [CUX.md](../CUX.md) | CUX architecture, multimodal, tool definitions |
| [architecture.md](architecture.md) | System architecture, auth flow |
| [api-reference.md](api-reference.md) | Endpoints, JSON schema |
| [authentication.md](authentication.md) | JWT, token passthrough |
