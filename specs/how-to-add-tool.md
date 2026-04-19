# How to Add/Update/Delete LLM Tools When Pulse Backend Changes

This guide explains the step-by-step process for updating the chatbot's tools when the Pulse Backend API adds, modifies, or removes endpoints.

## Architecture Overview

When a resident chats with Pulse AI, the flow is:

```
User Message
  → LLM picks a tool (from TOOLS list in tools.py)
    → execute_tool() routes to PulseClient method (tools.py)
      → PulseClient makes HTTP request to Pulse Backend (pulse_client.py)
        → Backend returns JSON
  → LLM formats response to user
```

There are **5 files** you need to touch when adding a tool:

| # | File | Purpose |
|---|------|---------|
| 1 | `src/resident_agent/clients/pulse_client.py` | HTTP client - calls backend API |
| 2 | `src/resident_agent/cux/tools.py` | Tool definitions + router |
| 3 | `configs/permissions.yaml` | Permission → tool mapping |
| 4 | `src/resident_agent/cux/action_generator.py` | Fallback action mappings |
| 5 | `configs/prompts.yaml` | LLM prompt tool lists |

---

## Adding a New Tool

### Step 1: Add PulseClient method

File: `src/resident_agent/clients/pulse_client.py`

Find the appropriate section (marked with `# ==================== Section ====================`) and add a new async method:

```python
async def get_new_resource(self, param1: str, param2: Optional[str] = None) -> Dict[str, Any]:
    """Short description.

    Args:
        param1: Description
        param2: Optional description

    Returns:
        Result from API
    """
    params = {}
    if param2:
        params["param2"] = param2
    return await self._request("GET", "/api/NewResource", params=params)
```

**Rules:**
- Use `_request()` helper - never use `httpx` directly
- GET requests: pass query params via `params=`
- POST/PUT requests: pass body via `json_data=`
- Collection endpoints (return lists): use `-> List[Dict]` return type
- Single item endpoints: use `-> Dict[str, Any]` return type
- Match the backend endpoint path exactly (e.g., `/api/Parcels`, `/api/v1/resident/bookings`)
- Check backend controller for the correct route: `[Route("api/[controller]")]` resolves to `/api/ControllerName`

### Step 2: Add tool definition

File: `src/resident_agent/cux/tools.py`

Add to the `TOOLS` list in the appropriate section:

```python
{
    "type": "function",
    "function": {
        "name": "get_new_resource",
        "description": "Mô tả bằng tiếng Việt, ngắn gọn, rõ ràng - LLM dùng description này để quyết định gọi tool nào",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Mô tả param bằng tiếng Việt"},
                "param2": {"type": "string", "description": "Optional - mô tả (optional)"},
            },
            "required": ["param1"],
        },
    },
},
```

**Rules:**
- `name`: snake_case, matches the PulseClient method name
- `description`: **Vietnamese**, concise but descriptive - this is what the LLM reads to decide which tool to call
- `parameters`: follow OpenAI function calling format
- Mark optional params by NOT including them in `required`
- For enum values: use `"enum": ["Value1", "Value2"]`

### Step 3: Wire in execute_tool()

Same file `src/resident_agent/cux/tools.py`, add an `elif` branch in the `execute_tool()` function:

```python
elif tool_name == "get_new_resource":
    result = _wrap_result(await pulse_client.get_new_resource(**params))
```

**Pattern guide:**
- Collection endpoints (return list): wrap with `_wrap_result()`
- Single item with ID param: `result = await pulse_client.get_something(params["something_id"])`
- POST/PUT with specific params: extract and pass named args
  ```python
  elif tool_name == "create_something":
      result = await pulse_client.create_something(
          field1=params["field1"],
          field2=params.get("field2"),  # optional
      )
  ```

### Step 4: Update permissions

File: `configs/permissions.yaml`

**3 places to update:**

1. `permission_to_tools` - map backend permission to tool:
```yaml
"NewResource.Read": ["get_new_resource"]
```

2. `tool_to_permission` - map tool to required permission:
```yaml
get_new_resource: "NewResource.Read"
```

3. If the tool is public (no permission needed), set to `null`:
```yaml
get_new_resource: null
```

And add to `default_tools`:
```yaml
default_tools:
  - "get_new_resource"
```

### Step 5: Update action_generator.py

File: `src/resident_agent/cux/action_generator.py`

1. Add to `_find_tool_for_action()` mapping (~line 136):
```python
"view_new_resource": "get_new_resource",
```

2. Add to `_DEFAULT_ACTION_SUGGESTER_PROMPT` tool list:
```
- get_new_resource: Short description
```

### Step 6: Update prompts.yaml

File: `configs/prompts.yaml`

Add the new tool to the tool lists in these prompts:
- `agentic` - main tool-calling prompt
- `action_router` - action routing prompt
- `action_suggester` - action suggestion prompt

Format: `- tool_name: Short English description`

---

## Deleting a Tool

Reverse the process - remove from all 5 files:

1. **pulse_client.py**: Remove the method (or keep if still used elsewhere)
2. **tools.py**: Remove from `TOOLS` list AND the `elif` branch in `execute_tool()`
3. **permissions.yaml**: Remove from `permission_to_tools`, `tool_to_permission`, and `default_tools`
4. **action_generator.py**: Remove from `action_to_tool` mapping and prompt
5. **prompts.yaml**: Remove from all prompt tool lists

---

## Modifying an Existing Tool

1. Update the backend endpoint in `pulse_client.py` if the route changed
2. Update `parameters` in the `TOOLS` definition if params changed
3. Update `execute_tool()` if the PulseClient method signature changed
4. Update permissions if the required permission changed
5. Update prompts if the tool description changed

---

## Quick Checklist

When adding a tool, verify each step:

- [ ] PulseClient method added with correct endpoint path
- [ ] Tool definition in TOOLS list with Vietnamese description
- [ ] `elif` branch in `execute_tool()` with correct PulseClient call
- [ ] `_wrap_result()` used for collection endpoints (return lists)
- [ ] `permission_to_tools` updated
- [ ] `tool_to_permission` updated (or `null` for public)
- [ ] `default_tools` updated if tool is public
- [ ] `action_to_tool` mapping in action_generator.py
- [ ] Tool list in `_DEFAULT_ACTION_SUGGESTER_PROMPT`
- [ ] Tool list in `agentic`, `action_router`, `action_suggester` prompts
- [ ] `python -c "from resident_agent.cux.tools import TOOLS; print(len(TOOLS))"` - no import errors
- [ ] Backend endpoint path matches controller route exactly

## Common Patterns Reference

### GET collection (list)
```python
# PulseClient
async def get_items(self, status: Optional[str] = None) -> List[Dict]:
    params = {}
    if status:
        params["status"] = status
    return await self._request("GET", "/api/Items", params=params)

# tools.py TOOLS
{"name": "get_items", "description": "Xem danh sách...", "parameters": {...}}

# tools.py execute_tool
elif tool_name == "get_items":
    result = _wrap_result(await pulse_client.get_items(**params))
```

### GET single item by ID
```python
# PulseClient
async def get_item(self, item_id: str) -> Dict[str, Any]:
    return await self._request("GET", f"/api/Items/{item_id}")

# tools.py TOOLS
{"name": "get_item_detail", "description": "Xem chi tiết...", "parameters": {
    "properties": {"item_id": {"type": "string", "description": "ID của item"}},
    "required": ["item_id"]
}}

# tools.py execute_tool
elif tool_name == "get_item_detail":
    result = await pulse_client.get_item(params["item_id"])
```

### POST create
```python
# PulseClient
async def create_item(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
    payload = {"name": name}
    if description:
        payload["description"] = description
    return await self._request("POST", "/api/Items", json_data=payload)

# tools.py TOOLS
{"name": "create_item", "description": "Tạo mới...", "parameters": {
    "properties": {
        "name": {"type": "string", "description": "Tên"},
        "description": {"type": "string", "description": "Mô tả (optional)"}
    },
    "required": ["name"]
}}

# tools.py execute_tool
elif tool_name == "create_item":
    result = await pulse_client.create_item(**params)
```

### PUT update
```python
# PulseClient
async def update_item(self, item_id: str, **kwargs) -> Dict[str, Any]:
    return await self._request("PUT", f"/api/Items/{item_id}", json_data=kwargs)

# tools.py execute_tool
elif tool_name == "update_item":
    result = await pulse_client.update_item(item_id=params["item_id"], **params)
```
