# Customer Support Agent - Redesign Plan

## Overview

This document outlines a comprehensive plan to redesign `customer_support_agent.py` to properly follow the customer support workflow while leveraging LLM intelligence instead of hardcoded logic.

---

## Current Problems

### 1. Hardcoded Workflow Logic

- Current `_validate_workflow_tools()` uses rigid stage-to-tool mapping
- Workflow stages are explicitly defined in code, not intelligently determined
- The `_analyze_query()` prompt tries to force specific workflow stages

### 2. Poor Prompt Design

- Analysis prompt is overly prescriptive with hardcoded branching logic
- Tells LLM exactly what to output instead of letting it reason
- Missing: tool descriptions passed to LLM so it can choose intelligently
- Missing: language mirroring instruction

### 3. Wrong Tool Result Formatting

- `_format_tool_results()` references non-existent tools (web_search, calculator)
- Doesn't handle outputs from actual tools:
  - `image_analysis` → returns analysis object with damage assessment
  - `verification` → returns fraud_check with risk_level
  - `assign_agent` → returns assignment_id and agent_info
  - `raise_ticket` → returns ticket_id and status
  - `order_action` → returns action result and status
  - `live_information` → returns data object
  - `knowledge_base` → returns articles list

### 4. Unnecessary Complexity

- `_validate_workflow_tools()` overrides LLM decisions
- Sequential vs parallel tool execution is overly complex
- Workflow path tracking adds no value

---

## Target Workflow (JSON Simplified)

```
Customer Query
      ↓
┌─────────────────────────────────┐
│        AIIntakeLayer            │  ← Analyze: intent, sentiment, urgency
│  (Categorization & Sentiment)   │
└─────────────────────────────────┘
      ↓
  [If Angry/Frustrated]
      ↓
┌─────────────────────────────────┐
│        DeEscalation             │  ← Empathy message first
└─────────────────────────────────┘
      ↓
  [Decision: Sensitive Task?]
      ↓
┌─────────────┐     ┌─────────────────────────────┐
│ Refund/     │ YES │  ComplianceVerification     │ → verification tool
│ Cancel/     │ ──► │  (Fraud Check)              │ → image_analysis (if photo)
│ Personal    │     │  Then: SecureHandlingTeam   │ → assign_agent
│ Data?       │     └─────────────────────────────┘
└─────────────┘
      │ NO
      ↓
  [Decision: Can AI Resolve?]
      ↓
┌─────────────┐     ┌─────────────────────────────┐
│ Order       │ YES │     AIAutoResponse          │ → live_information
│ Status,     │ ──► │     (Direct Answer)         │ → knowledge_base
│ FAQs,       │     └─────────────────────────────┘
│ Policies?   │
└─────────────┘
      │ NO
      ↓
  [Decision: Urgent?]
      ↓
┌─────────────┐     ┌─────────────────────────────┐
│ Critical/   │ YES │    AIAssistedRouting        │ → assign_agent
│ Urgent?     │ ──► │    (Escalate to Human)      │
└─────────────┘     └─────────────────────────────┘
      │ NO
      ↓
┌─────────────────────────────────┐
│       TicketCreation            │ → raise_ticket
│   (Non-urgent, needs research)  │
└─────────────────────────────────┘
```

---

## Redesign Plan

### Phase 1: Simplify Architecture

#### 1.1 Remove Unnecessary Functions

- **DELETE**: `_validate_workflow_tools()` - LLM should decide tools, not code
- **DELETE**: `_get_fallback_analysis()` - Replace with simpler fallback
- **SIMPLIFY**: `_execute_tools()` - Remove complex sequential logic

#### 1.2 Simplified Flow

```
process_query()
    ↓
_analyze_query()     → Single smart prompt that understands workflow
    ↓
_execute_tools()     → Simple parallel execution (let LLM handle dependencies)
    ↓
_generate_response() → Natural response using tool results
```

---

### Phase 2: Redesign Analysis Prompt

#### 2.1 New Analysis Prompt Structure

The prompt should:

1. **Provide context** - Current date, chat history, available tools
2. **Describe workflow naturally** - Not as code branches, but as decision guidance
3. **Include tool descriptions** - So LLM can choose intelligently
4. **Request language mirroring** - Detect and match customer's language
5. **Let LLM reason** - Not prescribe exact outputs

#### 2.2 Tool Descriptions to Include

```
AVAILABLE TOOLS:
1. live_information
   - Use for: Order status, tracking, delivery info, customer profile
   - When: Customer asks "where is my order", "order status", "tracking"

2. knowledge_base
   - Use for: Policies, FAQs, product info, how-to guides, shipping info
   - When: Customer asks about returns policy, product questions, general help

3. verification
   - Use for: Fraud check before processing refunds/cancellations
   - When: Customer requests refund, cancellation, or sensitive changes
   - Returns: risk_level (low/medium/high)

4. image_analysis
   - Use for: Analyzing product photos for damage/defects
   - When: Customer reports broken/defective item AND provides image
   - Returns: damage assessment, severity, recommendation

5. order_action
   - Use for: Processing refund, cancel, replace, return label
   - When: After verification confirms low/medium risk
   - IMPORTANT: Use verification FIRST before this tool

6. assign_agent
   - Use for: Escalating to human agent immediately
   - When: Very frustrated customer, urgent issue, high fraud risk,
           complex problem, or customer requests human

7. raise_ticket
   - Use for: Creating ticket for non-urgent investigation
   - When: Issue needs research (warehouse/courier checks) but can wait
```

#### 2.3 Analysis Prompt Template (Conceptual)

```
You are analyzing a customer support query. Your job is to understand what the
customer needs and decide how to help them.

TODAY'S DATE: {current_date}

CUSTOMER QUERY: {query}

RECENT CONVERSATION:
{chat_history}

AVAILABLE TOOLS:
{tool_descriptions}

WORKFLOW GUIDANCE:
1. First, understand the customer's emotion and urgency
   - If very angry/frustrated → acknowledge their feelings first (de-escalation)

2. Determine if this is a sensitive request (refund, cancel, personal data change)
   - If YES → use verification tool first to check risk
   - If image provided → also use image_analysis
   - Then assign_agent for human handling

3. Check if you can help directly (order status, FAQs, policies)
   - If YES → use live_information or knowledge_base

4. If you can't resolve and it's urgent → assign_agent

5. If not urgent → raise_ticket for investigation

THINK ABOUT:
- What is the customer's primary intent?
- How are they feeling? (angry, confused, calm, urgent)
- Do you need information from them first? (order ID, photo, reason)
- Which tool(s) would help? (can be none if just answering)
- What language is the customer using? (respond in same language)

Return your analysis as JSON:
{
  "language": "detected language code (en, es, ar, etc.)",
  "intent": "brief description of what customer wants",
  "sentiment": {
    "emotion": "angry/frustrated/confused/neutral/satisfied",
    "intensity": "low/medium/high",
    "urgency": "low/medium/high/critical"
  },
  "needs_de_escalation": true/false,
  "de_escalation_approach": "how to acknowledge their feelings (if needed)",
  "needs_more_info": true/false,
  "missing_info": "what info is needed from customer (if any)",
  "tools_to_use": ["tool1", "tool2"],
  "tool_queries": {
    "tool_name": "specific query for this tool"
  },
  "reasoning": "brief explanation of your decision"
}
```

---

### Phase 3: Redesign Response Generation Prompt

#### 3.1 New Response Prompt Structure

```
You are a friendly customer support agent. Generate a helpful response.

CUSTOMER QUERY: {query}
LANGUAGE TO USE: {detected_language}

CUSTOMER STATE:
- Emotion: {sentiment.emotion}
- Urgency: {sentiment.urgency}
- Needs de-escalation: {needs_de_escalation}

WHAT YOU LEARNED:
{formatted_tool_results}

INFORMATION STILL NEEDED: {missing_info or "None"}

GUIDELINES:
1. Respond in the SAME LANGUAGE as the customer
2. If de-escalation needed → Start with empathy, acknowledge their frustration
3. If missing info → Ask politely for what you need
4. If tools provided info → Use it to answer directly
5. If escalated to agent → Confirm they'll get help soon
6. If ticket created → Give them the reference number and timeline
7. Keep response concise (2-4 sentences unless complex explanation needed)
8. Be warm but professional

Generate your response:
```

---

### Phase 4: Fix Tool Result Formatting

#### 4.1 New `_format_tool_results()` Function

Handle ONLY the actual tools that exist:

```python
def _format_tool_results(self, tool_results: dict) -> str:
    """Format tool results for response generation"""
    if not tool_results:
        return "No additional information retrieved."

    formatted = []

    for tool_key, result in tool_results.items():
        # Skip failed results
        if isinstance(result, dict) and result.get('error'):
            continue
        if not isinstance(result, dict) or not result.get('success', True):
            continue

        tool_name = tool_key.split('_')[0]  # Remove _0, _1 suffix

        # Format based on tool type
        if tool_name == "live_information":
            data = result.get('data', {})
            if data:
                formatted.append(f"ORDER/CUSTOMER INFO:\n{json.dumps(data, indent=2)}")

        elif tool_name == "knowledge_base":
            articles = result.get('articles', [])
            if articles:
                formatted.append("KNOWLEDGE BASE RESULTS:")
                for article in articles[:3]:
                    formatted.append(f"- {article.get('title', 'Untitled')}")
                    formatted.append(f"  {article.get('content', '')[:200]}")

        elif tool_name == "verification":
            fraud = result.get('fraud_check', {})
            risk = fraud.get('risk_level', result.get('risk_level', 'unknown'))
            formatted.append(f"VERIFICATION RESULT:\n- Risk Level: {risk}")
            if fraud.get('recommendation'):
                formatted.append(f"- Recommendation: {fraud.get('recommendation')}")

        elif tool_name == "image_analysis":
            analysis = result.get('analysis', {})
            if analysis:
                formatted.append("IMAGE ANALYSIS:")
                formatted.append(f"- Damage Detected: {analysis.get('damage_detected', 'unknown')}")
                formatted.append(f"- Severity: {analysis.get('severity', 'unknown')}")
                formatted.append(f"- Description: {analysis.get('description', 'N/A')}")
                formatted.append(f"- Recommendation: {analysis.get('recommendation', 'N/A')}")
            ai_detection = result.get('ai_detection', {})
            if ai_detection.get('is_ai_generated'):
                formatted.append(f"- ⚠️ Warning: Image may be AI-generated")

        elif tool_name == "assign_agent":
            agent = result.get('agent_info', {})
            formatted.append("AGENT ASSIGNED:")
            formatted.append(f"- Agent: {agent.get('agent_name', 'Support Specialist')}")
            formatted.append(f"- ETA: {result.get('eta', '5-10 minutes')}")
            formatted.append(f"- Channel: {result.get('channel', 'chat')}")

        elif tool_name == "raise_ticket":
            formatted.append("TICKET CREATED:")
            formatted.append(f"- Ticket ID: {result.get('ticket_id', 'N/A')}")
            formatted.append(f"- Status: {result.get('status', 'open')}")
            formatted.append(f"- Priority: {result.get('priority', 'medium')}")

        elif tool_name == "order_action":
            action = result.get('action', 'unknown')
            formatted.append(f"ORDER ACTION ({action.upper()}):")
            formatted.append(f"- Status: {result.get('status', 'pending')}")
            if result.get('refund_amount'):
                formatted.append(f"- Refund Amount: ${result.get('refund_amount')}")
            if result.get('tracking_number'):
                formatted.append(f"- Tracking: {result.get('tracking_number')}")

    return "\n".join(formatted) if formatted else "No actionable information retrieved."
```

---

### Phase 5: Simplify Tool Execution

#### 5.1 Remove Sequential Logic

Current code has complex verification-first logic. Instead:

1. Let the LLM specify tools in the order it wants them
2. Execute all tools in parallel (simpler, faster)
3. If verification returns high risk, handle it in response generation

#### 5.2 Simplified `_execute_tools()`

```python
async def _execute_tools(self, tools: List[str], query: str,
                         analysis: Dict, user_id: str = None) -> Dict[str, Any]:
    """Execute tools in parallel"""
    if not tools:
        return {}

    results = {}
    tasks = []
    tool_queries = analysis.get('tool_queries', {})

    for i, tool in enumerate(tools):
        if tool not in self.available_tools:
            continue

        tool_key = f"{tool}_{i}"
        tool_query = tool_queries.get(tool, query)

        logger.info(f"🔧 Queueing {tool_key}")
        task = self.tool_manager.execute_tool(tool, query=tool_query, user_id=user_id)
        tasks.append((tool_key, task))

    # Execute all in parallel
    for tool_key, task in tasks:
        try:
            results[tool_key] = await task
            logger.info(f"✅ {tool_key} complete")
        except Exception as e:
            logger.error(f"❌ {tool_key} failed: {e}")
            results[tool_key] = {"error": str(e), "success": False}

    return results
```

---

### Phase 6: Streamline `process_query()`

#### 6.1 Simplified Main Flow

```python
async def process_query(self, query: str, chat_history: List[Dict] = None,
                        user_id: str = None) -> Dict[str, Any]:
    """Process customer query"""
    start_time = datetime.now()

    try:
        # Step 1: Analyze query (1 LLM call)
        analysis = await self._analyze_query(query, chat_history)

        # Step 2: Execute tools if needed
        tools_to_use = analysis.get('tools_to_use', [])

        if analysis.get('needs_more_info'):
            tool_results = {}  # Skip tools if we need info first
        else:
            tool_results = await self._execute_tools(tools_to_use, query, analysis, user_id)

        # Step 3: Generate response (1 LLM call)
        response = await self._generate_response(query, analysis, tool_results, chat_history)

        return {
            "success": True,
            "response": response,
            "analysis": analysis,
            "tool_results": tool_results,
            "processing_time": (datetime.now() - start_time).total_seconds()
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        return {
            "success": False,
            "response": "I apologize, I encountered an issue. Please try again.",
            "error": str(e)
        }
```

---

## Files to Modify

### customer_support_agent.py

| Function                   | Action   | Notes                                         |
| -------------------------- | -------- | --------------------------------------------- |
| `__init__`                 | KEEP     | No changes needed                             |
| `process_query`            | SIMPLIFY | Remove workflow tracking, simplify return     |
| `_analyze_query`           | REWRITE  | New intelligent prompt with tool descriptions |
| `_get_fallback_analysis`   | SIMPLIFY | Basic fallback, fewer fields                  |
| `_execute_tools`           | SIMPLIFY | Remove sequential logic                       |
| `_execute_parallel`        | DELETE   | Merge into `_execute_tools`                   |
| `_validate_workflow_tools` | DELETE   | LLM decides tools, not code                   |
| `_generate_response`       | REWRITE  | New prompt with language mirroring            |
| `_format_tool_results`     | REWRITE  | Handle actual tools only                      |
| `_extract_json`            | KEEP     | Utility function                              |
| `_clean_response`          | KEEP     | Utility function                              |
| `background_task_worker`   | KEEP     | No changes                                    |
| `_start_worker_if_needed`  | KEEP     | No changes                                    |

---

## Key Principles

### 1. Let LLM Reason, Don't Prescribe

- ❌ "If X then Y, if Z then W" in prompts
- ✅ "Consider X, Y, Z when deciding"

### 2. Trust LLM Tool Selection

- ❌ Code that overrides LLM's tool choices
- ✅ LLM sees tool descriptions and decides

### 3. Language Mirroring

- Detect customer's language in analysis
- Pass to response generation
- LLM responds in same language

### 4. Handle Real Tool Outputs

- Format results based on what tools actually return
- Don't reference non-existent tools

### 5. Natural Workflow

- Workflow emerges from LLM understanding, not hardcoded branches
- De-escalation happens because LLM recognizes frustration
- Tool selection happens because LLM understands the need

---

## Example Scenarios

### Scenario 1: Angry Customer Wanting Refund

```
Customer: "This is ridiculous! My order arrived broken and nobody is helping me! I want my money back NOW!"

Analysis:
- emotion: angry, intensity: high, urgency: high
- needs_de_escalation: true
- intent: refund for damaged item
- missing_info: order_id, photo
- tools: [] (need info first)

Response:
"I'm so sorry you received a broken item - that's really frustrating, and I completely understand.
To help process your refund right away, could you please share your order number and a photo
of the damage? I'll make this a priority."
```

### Scenario 2: Order Status Check

```
Customer: "Where is my order #12345?"

Analysis:
- emotion: neutral, urgency: medium
- needs_de_escalation: false
- intent: order status
- tools: [live_information]

Response:
"Let me check on order #12345 for you. [Uses live_information tool results]
Your order shipped on [date] and is currently [status]. Expected delivery is [date]."
```

### Scenario 3: Policy Question

```
Customer: "What is your return policy?"

Analysis:
- emotion: neutral, urgency: low
- intent: return policy info
- tools: [knowledge_base]

Response:
"[Uses knowledge_base results] We offer 30-day returns for most items.
Items must be unused and in original packaging. Would you like to start a return?"
```

---

## Implementation Order

1. **First**: Rewrite `_format_tool_results()` - Critical fix
2. **Second**: Rewrite `_analyze_query()` with new prompt
3. **Third**: Rewrite `_generate_response()` with new prompt
4. **Fourth**: Simplify `_execute_tools()`
5. **Fifth**: Simplify `process_query()`
6. **Sixth**: Delete unused functions

---

## Testing Checklist

After implementation, test these scenarios:

- [ ] Angry customer → De-escalation message first
- [ ] Order status query → Uses live_information
- [ ] Policy question → Uses knowledge_base
- [ ] Refund request without order ID → Asks for order ID
- [ ] Refund request with photo → Uses verification + image_analysis + assign_agent
- [ ] Urgent technical issue → Uses assign_agent
- [ ] Non-urgent complaint → Uses raise_ticket
- [ ] Spanish customer → Response in Spanish
- [ ] Arabic customer → Response in Arabic

---

## Summary

The redesign focuses on:

1. **Smart prompts** that guide LLM reasoning instead of prescribing exact outputs
2. **Tool intelligence** by providing descriptions so LLM chooses appropriately
3. **Language awareness** for responding in customer's language
4. **Correct tool handling** for the 7 actual tools that exist
5. **Simplified code** by removing unnecessary validation and routing logic

The workflow happens naturally through LLM understanding, not through hardcoded stage transitions.
