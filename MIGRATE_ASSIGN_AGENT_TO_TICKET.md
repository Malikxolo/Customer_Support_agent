# Migration Plan: Replace `assign_agent` with `raise_ticket` Tool

## 📋 Executive Summary

**Current State:** The bot uses `assign_agent` tool to directly assign a human agent to customers.

**Problem:** LLMs are unpredictable. Allowing the bot to directly assign agents is risky - it could assign agents unnecessarily, overwhelm the support team, or assign incorrectly.

**Solution:** Replace `assign_agent` with `raise_ticket`. When escalation is needed, a ticket is created instead. Human agents can then be assigned in the backend based on ticket priority/category - a standard industry practice.

**Flow Change:**

- **Before:** Bot → assigns agent directly → agent handles
- **After:** Bot → creates ticket → backend assigns agent → agent handles

---

## 🔍 Analysis: What Needs to Change in `customer_support_agent.py`

### File: `customer_support_agent.py`

There are **5 key areas** that reference `assign_agent` and need modification:

---

### 1. Tool Descriptions (`_get_tool_descriptions` method) - Lines 42-85

**Current `assign_agent` entry:**

```python
"assign_agent": {
    "purpose": "Connect customer with a human agent who can process refunds, replacements, etc.",
    "use_when": "After gathering all info (order ID, reason, photos if applicable) for: refund requests, cancellations, replacements, complex issues",
    "important": "NEVER use just because user says 'talk to agent' - first ask what their issue is. Gather all info before escalating."
}
```

**Current `raise_ticket` entry:**

```python
"raise_ticket": {
    "purpose": "Create support ticket for investigation",
    "use_when": "Issue needs research (warehouse/courier checks) but is not urgent"
}
```

**Required Change:**

- ❌ Remove `assign_agent` from tool descriptions entirely
- ✅ Expand `raise_ticket` description to cover escalation scenarios

**New `raise_ticket` entry:**

```python
"raise_ticket": {
    "purpose": "Create support ticket for escalation and investigation",
    "use_when": "After gathering all info (order ID, reason, photos if applicable) for: refund requests, cancellations, replacements, complex issues, or issues needing research",
    "important": "NEVER create ticket just because user says 'talk to agent' - first ask what their issue is. Gather all info before creating ticket. An agent will be assigned in backend.",
    "returns": "ticket_id, status, priority, category"
}
```

---

### 2. Analysis Prompt - Tool Selection Rules (Lines ~270-290)

**Current text references `assign_agent` in multiple places:**

**Section: "4. SELECT TOOLS"**

```
- Refund/cancel/replace requests → verification ONLY (then offer agent in response, don't auto-assign)
```

**Section: "5. SPECIAL CASES"**

```
- Customer asks for human BUT has already explained issue and we couldn't help → assign_agent
- Customer asks for human WITHOUT explaining issue → Ask what's wrong first (needs_more_info=true)
- High-risk verification result → assign_agent
```

**Section: "ABSOLUTE RULE FOR ASSIGN_AGENT"**

```
assign_agent is NOT a problem-solving step.
assign_agent is a permission-based action.
...
```

**Required Changes:**

- Replace all mentions of `assign_agent` with `raise_ticket`
- Update the "ABSOLUTE RULE" section to be about `raise_ticket`
- Keep the same logic (permission-based, gather info first)

---

### 3. Analysis Prompt - Commitment Tools Section (Lines ~285-295)

**Current:**

```
Commitment tools (require user confirmation FIRST):
   - assign_agent → ONLY use when user explicitly confirms they want an agent
   - order_action → ONLY after verification passes
   - raise_ticket → creates a permanent record
```

**Required Change:**

- Remove `assign_agent` line
- Keep `raise_ticket` but update its description to reflect escalation use case

**New:**

```
Commitment tools (require user confirmation FIRST):
   - raise_ticket → ONLY use when user explicitly confirms they want escalation/agent help. Creates ticket and agent is assigned in backend.
   - order_action → ONLY after verification passes
```

---

### 4. Response Generation Prompt (Lines ~395-465)

**Section: "6. OFFERING ESCALATION"**

**Current:**

```python
6. OFFERING ESCALATION:
   Check if agent was already assigned (look for "AGENT ASSIGNED" in tool results):

   - If AGENT ASSIGNED appears in tool results:
     → Agent is already connected. Confirm help is on the way with ETA.

   - If NO agent assigned yet AND verification was done:
     → ASK user: "Would you like me to connect you with an agent who can help with your [refund/replacement/etc]?"
     → Wait for their confirmation before actually assigning.
```

**Required Changes:**

- Change "AGENT ASSIGNED" check to "TICKET CREATED" check
- Update the ask message from "connect you with an agent" to "escalate this to our support team"
- Update confirmation message to reference ticket instead of agent assignment

**New:**

```python
6. OFFERING ESCALATION:
   Check if ticket was already created (look for "TICKET CREATED" in tool results):

   - If TICKET CREATED appears in tool results:
     → Ticket is created. Confirm an agent will reach out soon with ticket reference.

   - If NO ticket created yet AND verification was done:
     → ASK user: "Would you like me to escalate this to our support team? An agent will reach out to help with your [refund/replacement/etc]."
     → Wait for their confirmation before creating ticket.
```

---

### 5. Format Tool Results Method (`_format_tool_results`) - Lines ~475-545

**Current `assign_agent` formatting:**

```python
elif tool_name == "assign_agent":
    agent_info = result.get('agent_info', {})
    formatted.append("👤 AGENT ASSIGNED:")
    formatted.append(f"  • Agent: {agent_info.get('agent_name', 'Support Specialist')}")
    formatted.append(f"  • ETA: {result.get('eta', '5-10 minutes')}")
    formatted.append(f"  • Channel: {result.get('channel', 'chat')}")
    if result.get('assignment_id'):
        formatted.append(f"  • Reference: {result.get('assignment_id')}")
```

**Required Changes:**

- ❌ Remove entire `assign_agent` formatting block
- ✅ Update `raise_ticket` formatting to handle escalation tickets

**Current `raise_ticket` formatting:**

```python
elif tool_name == "raise_ticket":
    formatted.append("🎫 TICKET CREATED:")
    formatted.append(f"  • Ticket ID: {result.get('ticket_id', 'N/A')}")
    formatted.append(f"  • Status: {result.get('status', 'open')}")
    formatted.append(f"  • Priority: {result.get('priority', 'medium')}")
    if result.get('category'):
        formatted.append(f"  • Category: {result.get('category')}")
```

**Enhanced `raise_ticket` formatting (to handle escalation context):**

```python
elif tool_name == "raise_ticket":
    formatted.append("🎫 TICKET CREATED:")
    formatted.append(f"  • Ticket ID: {result.get('ticket_id', 'N/A')}")
    formatted.append(f"  • Status: {result.get('status', 'open')}")
    formatted.append(f"  • Priority: {result.get('priority', 'medium')}")
    if result.get('category'):
        formatted.append(f"  • Category: {result.get('category')}")
    # For escalation tickets, add ETA info
    formatted.append(f"  • Agent will be assigned and will reach out shortly")
```

---

## 📊 `raise_ticket` Tool Parameters Analysis

### Current Parameters (from `cs_tools.py`):

```python
async def execute(self, user_id: str, subject: str, description: str,
                 priority: str = "medium", category: str = "general",
                 customerName: str = None, channel: str = "whatsapp",
                 metadata: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
```

| Parameter      | Required    | Type | Description                                                       |
| -------------- | ----------- | ---- | ----------------------------------------------------------------- |
| `user_id`      | ✅ Yes      | str  | User identifier - comes from session                              |
| `subject`      | ✅ Yes      | str  | Ticket subject/title                                              |
| `description`  | ✅ Yes      | str  | Detailed description of the issue                                 |
| `priority`     | ❌ Optional | str  | "low", "medium", "high", "urgent" (default: "medium")             |
| `category`     | ❌ Optional | str  | "technical", "billing", "general", "product" (default: "general") |
| `customerName` | ❌ Optional | str  | Customer name                                                     |
| `channel`      | ❌ Optional | str  | "whatsapp" or "website" (default: "whatsapp")                     |
| `metadata`     | ❌ Optional | Dict | Additional data (order_id, product_id, etc.)                      |

### Comparison with `assign_agent` Parameters:

| `assign_agent` Param | Maps to `raise_ticket` | Notes                                    |
| -------------------- | ---------------------- | ---------------------------------------- |
| `user_id`            | `user_id`              | Same - 1:1 mapping                       |
| `issue_type`         | `category`             | Same concept, different name             |
| `context`            | `description`          | Conversation context becomes description |
| `priority`           | `priority`             | Same - 1:1 mapping                       |
| `preferred_channel`  | `channel`              | Same concept                             |
| `query`              | Part of `description`  | Include in description                   |

### Handling Missing Required Fields

The `raise_ticket` tool requires: `user_id`, `subject`, `description`

**How to handle in response generation:**

If ticket creation fails due to missing field, the error will indicate which field is missing. The response generation prompt already has logic for:

- "If any tool shows 'Error' or failed → acknowledge the issue"

**Add specific guidance for ticket errors:**

```
- If raise_ticket failed due to missing info → ask customer for the specific missing information
- Common missing: order ID, issue description, customer name
```

---

## 🔄 Summary of All Changes

### Changes in `customer_support_agent.py`:

| Location                             | Change Type     | Description                                               |
| ------------------------------------ | --------------- | --------------------------------------------------------- |
| `_get_tool_descriptions()`           | Remove + Update | Remove `assign_agent`, expand `raise_ticket`              |
| Analysis prompt - Tool selection     | Update text     | Replace `assign_agent` → `raise_ticket`                   |
| Analysis prompt - Special cases      | Update text     | Replace `assign_agent` → `raise_ticket`                   |
| Analysis prompt - Absolute rule      | Update text     | Change rule from `assign_agent` to `raise_ticket`         |
| Analysis prompt - Commitment tools   | Remove + Update | Remove `assign_agent` line, update `raise_ticket`         |
| Response prompt - Escalation section | Update text     | Change from "AGENT ASSIGNED" to "TICKET CREATED"          |
| Response prompt - Bot limitations    | Update text     | Update messaging about escalation                         |
| `_format_tool_results()`             | Remove + Update | Remove `assign_agent` block, enhance `raise_ticket` block |

### NO Changes Needed in:

- ❌ `cs_tools.py` - `raise_ticket` tool already has all needed parameters
- ❌ `tools.py` - Tool manager doesn't need changes
- ❌ API layer - No changes needed

---

## 📝 Language/Messaging Changes

### Old Messaging (assign_agent):

- "Would you like me to connect you with an agent?"
- "I'm connecting you with a support specialist"
- "Agent is on the way, ETA 5-10 minutes"
- "A human agent will help you shortly"

### New Messaging (raise_ticket):

- "Would you like me to escalate this to our support team?"
- "I'm creating a support ticket for you"
- "I've escalated your issue. An agent will reach out shortly"
- "Your ticket has been created. Our team will get back to you soon"

---

## ✅ Implementation Checklist

1. [ ] Update `_get_tool_descriptions()` - Remove `assign_agent`, expand `raise_ticket`
2. [ ] Update analysis prompt - Replace all `assign_agent` references with `raise_ticket`
3. [ ] Update analysis prompt - Modify "ABSOLUTE RULE" section for `raise_ticket`
4. [ ] Update response prompt - Change "AGENT ASSIGNED" to "TICKET CREATED"
5. [ ] Update response prompt - Change escalation messaging
6. [ ] Update `_format_tool_results()` - Remove `assign_agent` block
7. [ ] Update `_format_tool_results()` - Enhance `raise_ticket` block with agent assignment note
8. [ ] Test the flow end-to-end

---

## 🎯 Expected Behavior After Migration

1. **User asks for refund:** Bot gathers info → verifies → asks "Would you like me to escalate this?" → creates ticket
2. **User asks for agent directly:** Bot asks what their issue is first → gathers info → then offers to escalate
3. **High-risk verification:** Bot offers to escalate to support team via ticket
4. **Complex issue:** Bot creates ticket after gathering all required information
5. **Ticket created:** Response confirms ticket ID and that an agent will reach out

---

## 🚀 Benefits of This Migration

1. **Predictability:** Backend controls agent assignment, not LLM
2. **Audit Trail:** Every escalation creates a ticket record
3. **Queue Management:** Support team can prioritize tickets properly
4. **Reduced Risk:** LLM can't accidentally spam agent assignments
5. **Standard Practice:** Aligns with industry-standard support workflows
