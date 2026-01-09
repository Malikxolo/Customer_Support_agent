# Scope Detection & Mandatory Info Handling - Implementation Plan

## Overview

This document outlines the plan to fix two issues in the customer support agent:

1. **Out-of-Scope Query Handling** - Bot should NOT try to help or escalate queries outside its scope
2. **Missing Mandatory Info Handling** - Bot should clearly communicate when it cannot proceed without required information

---

## Issue 1: Out-of-Scope Query Detection

### Problem Statement

Currently, when a user asks about something completely unrelated to the support scope (e.g., "I am experiencing electricity outage in my area"), the bot:

- Tries to help by asking follow-up questions
- May eventually offer escalation

**This is wrong.** The bot should:

- Clearly identify out-of-scope queries
- Politely inform user that this is outside support scope
- NOT escalate (escalation is only for in-scope issues the bot can't resolve)
- Keep repeating this if user persists

### What's In-Scope (Our Support Domain)

Based on existing tools and functionality:

- Order status, tracking, delivery inquiries
- Refund requests
- Cancellation requests
- Replacement requests
- Damaged/defective product issues
- Wrong item received
- Return policy questions
- Shipping information
- Product questions (from knowledge base)
- Account-related issues
- Billing questions

### What's Out-of-Scope (Examples)

- Electricity outages
- Weather inquiries
- General knowledge questions
- Technical support for unrelated products
- Government services
- Other companies' products/services
- Medical/legal advice
- Random chitchat unrelated to orders/products

### Implementation Plan

#### Step 1: Add Scope Detection to Analysis Prompt

**File:** `core/customer_support_agent.py`  
**Location:** `_analyze_query()` method - in the analysis prompt

**Changes:**

1. Add a new section in the analysis prompt under "WORKFLOW GUIDANCE" for scope detection
2. Add new fields to the JSON output:
   - `is_in_scope`: boolean
   - `out_of_scope_reason`: string (if out of scope)

**Prompt Addition (conceptual):**

```
SCOPE CHECK (DO THIS FIRST):
Before analyzing intent, check if this query relates to our support domain:
- Our scope: Orders, tracking, refunds, cancellations, replacements, damaged items, returns, shipping, products, billing
- OUT of scope: Utilities (electricity/water/gas), weather, general knowledge, other companies, medical/legal advice

If OUT OF SCOPE:
- Set is_in_scope = false
- Set out_of_scope_reason = brief explanation
- Set tools_to_use = [] (empty - no tools for out-of-scope)
- Do NOT set needs_more_info = true (we don't need info for out-of-scope queries)
```

#### Step 2: Add Scope Fields to Analysis JSON Output

Add to the JSON schema in the analysis prompt:

```json
{
  "is_in_scope": true/false,
  "out_of_scope_reason": "explanation if out of scope, else null",
  ...existing fields...
}
```

#### Step 3: Update Response Generation for Out-of-Scope

**File:** `core/customer_support_agent.py`  
**Location:** `_generate_response()` method

**Changes:**

1. Pass `is_in_scope` and `out_of_scope_reason` to the response prompt
2. Add response guideline for out-of-scope handling

**Response Guideline Addition:**

```
OUT-OF-SCOPE HANDLING (if is_in_scope = false):
- Politely inform user this is outside your support scope
- Be clear but kind: "I'm sorry, but [electricity outages / this topic] is outside what I can help with. I'm here to assist with orders, refunds, product issues, and similar queries."
- Do NOT offer escalation (escalation is for in-scope issues only)
- Do NOT ask follow-up questions about the out-of-scope topic
- If user persists, keep politely declining
- Optionally: suggest where they might get help (e.g., "You may want to contact your local electricity provider")
```

#### Step 4: Handle Persistent Out-of-Scope Requests

**Logic:** If user keeps asking about same out-of-scope topic:

- Conversation state should track `out_of_scope_topic_repeated`
- Response should remain polite but firm
- Never escalate out-of-scope issues

---

## Issue 2: Missing Mandatory Information Handling

### Problem Statement

When a user:

- Refuses to provide required information (e.g., "I don't have my order ID")
- Says they can't give the information (e.g., "I don't want to share my phone number")

The bot currently might:

- Keep asking repeatedly
- Not clearly communicate that it cannot proceed

**Should Instead:**

- Clearly state: "I'm sorry, but I cannot proceed without [required info]. This information is necessary to [reason]."
- Stop asking after user explicitly refuses
- Provide a graceful closure

### Mandatory Information by Action Type

| Action        | Required Info                    | Why Needed                            |
| ------------- | -------------------------------- | ------------------------------------- |
| Refund        | Order ID                         | To locate the order                   |
| Cancellation  | Order ID                         | To identify which order to cancel     |
| Replacement   | Order ID                         | To process replacement                |
| Damaged Item  | Order ID + Image                 | To verify damage claim                |
| Create Ticket | Order ID + Customer Name + Phone | To contact customer & reference order |

### Implementation Plan

#### Step 1: Add Refusal Detection to Analysis

**File:** `core/customer_support_agent.py`  
**Location:** `_analyze_query()` method

**Changes:**

1. Detect when user explicitly refuses to provide info
2. Add new fields to JSON output:
   - `user_refused_info`: boolean
   - `refused_info_type`: what info they refused (e.g., "order_id", "phone_number")

**Detection Patterns (for prompt):**

```
REFUSAL DETECTION:
Check if user is refusing/unable to provide required information:
- "I don't have..." / "don't have my order ID"
- "I can't provide..." / "can't give you my phone"
- "I don't remember..." / "forgot my order number"
- "I don't want to share..."
- "not willing to give"

If refusal detected:
- Set user_refused_info = true
- Set refused_info_type = what they refused
- Set needs_more_info = false (we know they can't/won't provide it)
```

#### Step 2: Add Refusal Fields to Analysis JSON

```json
{
  "user_refused_info": true/false,
  "refused_info_type": "order_id" / "phone_number" / "image" / etc,
  "cannot_proceed_reason": "explanation of why we need this info",
  ...existing fields...
}
```

#### Step 3: Update Conversation State Extraction

**File:** `core/customer_support_agent.py`  
**Location:** `_extract_conversation_state()` method

**Changes:**
Add tracking for:

- `info_refused`: dictionary of what info user has refused
- `times_asked_for_info`: counter for each info type (to detect repeated asks)

#### Step 4: Update Response Generation for Cannot-Proceed Scenarios

**File:** `core/customer_support_agent.py`  
**Location:** `_generate_response()` method

**Response Guideline Addition:**

```
CANNOT PROCEED HANDLING (if user_refused_info = true):
- Acknowledge their concern/situation empathetically
- Clearly state you cannot proceed without the required info
- Explain WHY the info is needed (briefly)
- Offer alternatives if any exist:
  - "If you can find your order confirmation email, the order ID will be there"
  - "You can also check your account order history"
- If no alternatives and user firm in refusal:
  - "I understand. Unfortunately, without [info], I'm unable to assist with this request. Is there anything else I can help you with?"
- Do NOT keep asking for the same info after explicit refusal
- Do NOT escalate just because user won't provide info (unless it's an in-scope issue they need help with)
```

#### Step 5: Create Reusable "Cannot Proceed" Logic

This same pattern can be used for:

- Out-of-scope queries → "Cannot help with this topic"
- Missing mandatory info → "Cannot proceed without this info"
- Future scenarios → Same graceful decline pattern

**Common Response Pattern:**

```
1. Acknowledge ("I understand...")
2. State limitation clearly ("Unfortunately, I cannot...")
3. Explain briefly why (if helpful)
4. Offer alternative or graceful closure
5. Move on without repetition
```

---

## Summary of Changes

### Files to Modify

1. **`core/customer_support_agent.py`**
   - `_analyze_query()`: Add scope detection + refusal detection to prompt
   - `_extract_conversation_state()`: Track refusals and repeated asks
   - `_generate_response()`: Add guidelines for out-of-scope and cannot-proceed scenarios

### New Analysis Fields

```json
{
  "is_in_scope": boolean,
  "out_of_scope_reason": string | null,
  "user_refused_info": boolean,
  "refused_info_type": string | null,
  "cannot_proceed_reason": string | null
}
```

### New State Tracking Fields

```python
state = {
    ...existing fields...,
    "out_of_scope_detected": False,
    "out_of_scope_topic": None,
    "info_refused": {},  # {"order_id": True, "phone": False}
    "times_asked": {}    # {"order_id": 2, "phone": 1}
}
```

---

## Expected Behavior After Implementation

### Scenario 1: Out-of-Scope Query

```
User: "I am experiencing electricity outage in my area"
Bot: "I'm sorry, but electricity outages are outside what I can help with. I'm here to assist with orders, refunds, returns, and product-related queries. You may want to contact your local electricity provider for assistance. Is there anything order-related I can help you with?"

User: "Can you please help me with the electricity issue?"
Bot: "I understand this is frustrating, but I'm only able to assist with order and product-related queries. For electricity issues, please contact your local utility provider."
```

### Scenario 2: User Refuses to Provide Info

```
User: "I want a refund"
Bot: "I'd be happy to help with your refund. Could you please provide your order ID?"

User: "I don't have my order ID"
Bot: "I understand. The order ID is needed to locate your order and process the refund. You can find it in your order confirmation email or in your account order history. Without the order ID, I won't be able to proceed with the refund request. Would you like help with anything else?"
```

### Scenario 3: Persistent Refusal

```
User: "Just process the refund without the order ID"
Bot: "I'm sorry, but the order ID is required to identify and process your refund - there's no way around this requirement. If you're able to locate it later, I'll be happy to help. Is there anything else I can assist you with today?"
```

---

## Notes

- **No escalation for out-of-scope**: Escalation should only be offered for in-scope issues
- **No repeated asking**: Once user refuses, don't ask again in the same conversation
- **Graceful closure**: Always offer to help with something else
- **Consistent tone**: Polite, understanding, but firm about limitations
