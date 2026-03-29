# Pulse - Concept Document

## 1. Project Overview

| Field | Value |
|-------|-------|
| **English** | Pulse – Intelligent Resident Services & Management System |
| **Vietnamese** | Pulse – Hệ thống quản lý và dịch vụ cư dân thông minh |
| **Abbreviation** | SP26SE129 |

### Context

Building Management interaction remains low-tech while residents expect "Concierge-level" service—instant, personalized, and effortless. Current solutions lack a centralized "brain" to process natural language requests.

### Solution

Pulse replaces traditional forms with a **Conversational Interface**:

- **Core AI Agent**: Smart chatbot with Intent Recognition, automatically triggers workflows and routes tickets
- **5 Core Services**: AI Incident Management, Payment Gateway, Amenities Booking, Resident Services, Package Logistics
- **Modular Monolithic Architecture**: Simple deployment, structured for future updates

---

## 2. System Architecture

| Service | Technology | Purpose |
|---------|------------|---------|
| **Resident Agent** | Python (FastAPI) | AI Chat, Intent Detection, Workflow Automation |
| **Pulse Backend** | .NET 9 | Business API, CRUD Operations, Payment Gateway |

### Architecture Highlights

- Separate tokens: Each service issues its own JWT
- Token passthrough: Mobile app passes Pulse token via `X-Pulse-Token` header
- Permission check: Resident Agent uses Pulse token to fetch user capabilities
- Fallback mode: Works with mock data if Pulse Backend unavailable

---

## 3. Key Components

### Resident Agent Components

| Component | Description |
|-----------|-------------|
| **Auth Layer** | JWT token validation, Token passthrough (X-Pulse-Token) |
| **API Layer** | REST endpoints for chat and authentication |
| **SSE Handler** | Real-time streaming via Server-Sent Events |
| **CUX Orchestrator** | LLM-first with Function Calling + Multimodal Input |

### CUX Orchestrator Intents

| Intent | Description |
|--------|-------------|
| `chitchat` | Tâm sự, không cần tool |
| `agentic_flow` | LLM tự detect + gọi tools |
| `tool_call` | User click action button |

---

## 4. Authentication

### Two-Token System

| Token | Issued By | Purpose |
|-------|-----------|---------|
| **Resident Agent JWT** | Resident Agent (Python) | Access Chat APIs |
| **Pulse Backend JWT** | Pulse Backend (.NET) | Access Business APIs |

### Key Points

- Login field: `phoneNumber` (not email)
- Token passthrough via `X-Pulse-Token` header for permission checks and data access

---

## 5. API Summary

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Login, get Resident Agent JWT |
| `/chat` | POST | Send message, get response |
| `/chat/stream` | SSE | Stream chat responses in real-time |
| `/action` | POST | Execute suggested action |

### Action Types

| action_type | Description |
|-------------|-------------|
| `navigate` | Navigate to screen in `params.screen` |
| `check_package` | View packages list |
| `view_bills` | View bills list |
| `book_amenity` | Open amenity booking |
| `report_incident` | Open incident form |
| `service_request` | Open service request form |
| `make_payment` | Open payment flow |
| `deeplink` | Open deep link |

### SSE Event Types

| Type | Description |
|------|-------------|
| `thinking` | AI is processing |
| `content` | Text content chunk |
| `action` | Suggested action buttons |
| `complete` | Stream finished |
| `error` | Error occurred |

---

## 6. Functional Requirements

### Resident (Mobile App - Flutter)

- **AI ChatBot**: 24/7 assistant, intelligent action handler, auto-execution
- **Report a Problem**: Incident reporting, AI intent classification
- **Bills & Payment**: Bill viewing, online payment gateway
- **Amenities & Services**: Smart booking, service registration
- **Logistics & Notifications**: Package alerts, notification center

### Administrator (Web Dashboard - Next.js)

- **Ticket & Incident Management**: AI-filtered tickets, task assignment
- **Amenity & Service Management**: Booking approval, facility scheduling
- **Core Data Management**: Resident management, package operations
- **Payment Monitoring**: Billing status monitoring

### Technical Staff (Mobile App - Flutter)

- **Task Management**: View assigned maintenance tasks
- **Status Update**: Update ticket status (triggers notifications)

---

## 7. Non-functional Requirements

- **Performance**: AI response under 3 seconds
- **Real-time**: Admin Dashboard updates via WebSocket (SignalR)
- **Accuracy**: High confidence in intent classification
- **Architecture**: Modular Monolithic
- **Security**: Role-based access control (RBAC)

---

## 8. Tech Stack

| Layer | Technology |
|-------|------------|
| **Server** | .NET (ASP.NET Core Web API) |
| **AI Services** | Python, LangChain, FastAPI, OpenAI |
| **Database** | PostgreSQL, Cloudinary |
| **Web Client** | Next.js (React Framework) |
| **Mobile Client** | Flutter |

### Products

- RESTful APIs + WebSocket APIs
- Mobile Application (Residents, Staff)
- Web Administration Portal
- AI Integration Module
- PostgreSQL Database + ER diagram

---

## References

| Document | Description |
|----------|-------------|
| [business_analysis.md](bussiness_analysis.md) | Detailed requirements and tech stack |
| [architecture.md](architecture.md) | System architecture, chat flow, auth flow |
| [api-reference.md](api-reference.md) | Endpoints, JSON schemas, Flutter handling |
| [authentication.md](authentication.md) | JWT details, token passthrough |
| [components.md](components.md) | Key components overview |
| [CUX.md](../CUX.md) | CUX architecture, multimodal, tool definitions |
