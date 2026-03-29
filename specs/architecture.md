# Architecture

> **Note:** This document describes the **Resident Agent** (AI Chat Service).
> For Pulse Backend (.NET) architecture, see `app/Pulse-dotnetBE/README.md`.

## System Overview

Pulse consists of two main services:

| Service | Technology | Purpose |
|---------|------------|---------|
| **Resident Agent** | Python (FastAPI) | AI Chat, Intent Detection, Workflow Automation |
| **Pulse Backend** | .NET 9 | Business API, CRUD Operations, Payment Gateway |

## Chat Flow

```mermaid
sequenceDiagram
    participant App as Mobile App
    participant RA as Resident Agent
    participant CUX as CUX Orchestrator
    participant PB as Pulse Backend
    participant LLM as OpenAI LLM

    Note over App,PB: 1. User logs in on Mobile App
    App->>PB: POST /api/Users/login
    PB-->>App: Pulse JWT Token

    Note over App,RA: 2. User opens Chat
    App->>RA: POST /auth/login (guest/demo)
    RA-->>App: Resident Agent JWT

    Note over App,LLM: 3. User sends message
    App->>RA: POST /chat
    Note right of App: Authorization: Bearer RA_JWT<br/>X-Pulse-Token: Pulse_JWT
    RA->>CUX: process(message, pulse_token)

    CUX->>CUX: Detect Intent
    CUX->>PB: GET /api/UserRoles/{user_id}
    PB-->>CUX: User capabilities

    alt Has Permission
        CUX->>PB: GET /api/Actions, /api/Bills, etc.
        PB-->>CUX: Business data
        CUX->>LLM: Generate response with context
        LLM-->>CUX: AI response
    else No Permission
        CUX->>CUX: Return permission denied
    end

    CUX-->>RA: Response + Actions
    RA-->>App: Chat response
```

## Authorization Flow

The system uses **two separate JWT tokens** with passthrough mechanism:

| Token | Issued By | Purpose |
|-------|-----------|---------|
| **Pulse Backend JWT** | Pulse Backend (.NET) | Access Pulse APIs (mobile app login) |
| **Resident Agent JWT** | Resident Agent (Python) | Access Chat APIs |

### Key Points

- **Separate tokens**: Each service issues its own JWT
- **Token passthrough**: Mobile app passes Pulse token via `X-Pulse-Token` header
- **Permission check**: Resident Agent uses Pulse token to fetch user capabilities
- **Fallback mode**: Works with mock data if Pulse Backend unavailable
