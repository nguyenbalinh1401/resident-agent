# Authentication (JWT)

> **Note:** This documents **Resident Agent** authentication.
> Pulse Backend has its own auth system using `phoneNumber` login.

## Overview

Resident Agent uses JWT (JSON Web Tokens) for authentication. All protected endpoints require a valid Bearer token in the Authorization header.

## Two-Token System

| Token | Issued By | Login Field | Purpose |
|-------|-----------|-------------|---------|
| **Resident Agent JWT** | Resident Agent | `phoneNumber` | Access Chat APIs |
| **Pulse Backend JWT** | Pulse Backend | `phoneNumber` | Access Business APIs |

## Getting a Token

### Resident Agent Login

```bash
# Login to get Resident Agent token (not email!)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phoneNumber": "0901234567", "password": "demo123"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Pulse Backend Login (Mobile App)

```bash
# Mobile app login uses phoneNumber (not email!)
curl -X POST http://localhost:5000/api/Users/login \
  -H "Content-Type: application/json" \
  -d '{"phoneNumber": "0901234567", "password": "password"}'

# Response
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {...}
}
```

## Using the Token

### Basic Chat Request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <resident_agent_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Kiểm tra bưu kiện"}'
```

### With Pulse Token Passthrough

```bash
# Pass Pulse token for permission checks and data access
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <resident_agent_jwt>" \
  -H "X-Pulse-Token: <pulse_backend_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Kiểm tra bưu kiện"}'
```

