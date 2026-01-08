# Fix: Agent Assignment Should Be Conditional

## The Problem

When a user reports damage and provides order ID + image:

```
User: "my order id is 1234521 and my image is [ img.png ]"

LLM Analysis → Tools Selected: ['image_analysis', 'verification', 'assign_agent']
                                    ↓                                    ↓
                              (runs parallel)                     (runs parallel)
                                    ↓                                    ↓
                              FAILS (no image)               SUCCEEDS (agent assigned!)
                                    ↓
                              Bot asks: "please re-upload image"

                              BUT AGENT IS ALREADY ASSIGNED! ❌
```

**This is wrong because:**

- Agent is assigned before we even know if there's real damage
- If user re-uploads and image shows NO damage, agent was assigned for nothing
- Wastes human agent time on unverified claims
- Breaks natural support flow

---

## How Real Support Bots Work

Real support bots follow a **verify-first, act-later** approach:

```
1. Customer reports damage
2. Bot requests photo + order ID
3. Customer provides both
4. Bot analyzes image
   ├─ If analysis SUCCEEDS and damage detected:
   │    → "I can see the damage. Would you like me to connect you with an agent?"
   │    → Wait for user confirmation
   │    → THEN assign agent
   │
   ├─ If analysis SUCCEEDS but NO damage detected:
   │    → "I don't see visible damage in this photo. Could you try a clearer angle?"
   │    → OR "If you still believe it's damaged, I can connect you with an agent"
   │
   └─ If analysis FAILS (error, blurry, etc.):
        → "I couldn't analyze the image. Could you upload a clearer photo?"
        → Do NOT assign agent yet
```

**Key insight:** Agent assignment is a **commitment action** - it should only happen after the issue is verified OR the user explicitly requests it.

---

## The Fix: Teach LLM About Action Types

The solution is to update the **analysis prompt** to help the LLM understand that some tools are:

1. **Information-gathering tools** - Can run anytime, in parallel

   - `live_information`
   - `knowledge_base`
   - `verification`
   - `image_analysis`

2. **Commitment/Action tools** - Should only run after verification OR user confirmation
   - `assign_agent` (assigns human = commitment)
   - `order_action` (processes refund/cancel = commitment)
   - `raise_ticket` (creates ticket = commitment)

---

## Prompt Changes

### Update Tool Descriptions Section

**Current (problematic):**

```
6. assign_agent
   - Use for: Escalating to human agent immediately
   - When: Very frustrated customer, urgent issue, high fraud risk,
           complex problem, or customer requests human
```

**New (with conditional guidance):**

```
6. assign_agent
   - Use for: Connecting customer with a human agent
   - When to use IMMEDIATELY:
     • Customer explicitly asks for human ("let me talk to someone", "I want a person")
     • Critical/safety issue that needs immediate human attention
   - When to use AFTER CONFIRMATION:
     • Damage claims → First run image_analysis, confirm damage, THEN offer agent
     • Complex issues → First try to help, if stuck, THEN offer agent
   - DO NOT use alongside image_analysis in same turn for damage claims
     (wait for image analysis result first)
```

### Add "Action Planning" Guidance to Prompt

Add this section to the analysis prompt:

```
TOOL SELECTION RULES:

1. Information tools (live_information, knowledge_base, verification, image_analysis)
   → Can be selected together, run in parallel

2. Commitment tools (assign_agent, order_action, raise_ticket)
   → Only select these when you have enough information to act
   → For damage claims: Do NOT select assign_agent until image_analysis confirms damage
   → For refunds: Do NOT select order_action until verification passes

3. If unsure whether to commit → Don't. Gather info first, let next turn decide.

DAMAGE CLAIM FLOW:
- Turn 1: User reports damage → Ask for photo + order ID (no tools)
- Turn 2: User provides photo + order ID → Use [image_analysis, verification] only
- Turn 3 (based on results):
  • If damage confirmed → Offer agent connection, wait for user response
  • If no damage → Tell user, offer to escalate if they insist
  • If image error → Ask for clearer photo
- Turn 4: If user confirms they want agent → Use [assign_agent]
```

---

## Expected Behavior After Fix

### Scenario: Damage Claim with Image

**Turn 1:**

```
User: "my cake arrived damaged"
Bot: "I'm sorry to hear that. Could you share your order ID and a photo of the damage?"
Tools: [] (need info first)
```

**Turn 2:**

```
User: "order 1234521 [img.png]"
Bot analyzes → Tools: [image_analysis, verification]
               NOT assign_agent (wait for results)
```

**Turn 2a - If image_analysis succeeds + damage found:**

```
Tool results: damage_detected: true, severity: moderate
Bot: "I can see the damage to your cake. I'm sorry this happened.
      Would you like me to connect you with an agent who can arrange
      a replacement or refund?"
Tools: [] (waiting for user confirmation)
```

**Turn 3a - User confirms:**

```
User: "yes please"
Bot analyzes → Tools: [assign_agent]
Bot: "I've connected you with Agent Sarah. She'll be with you shortly."
```

**Turn 2b - If image_analysis fails:**

```
Tool results: error - couldn't analyze image
Bot: "I wasn't able to analyze the image you sent. Could you try
      uploading a clearer photo of the damage?"
Tools: [] (no agent assigned!)
```

**Turn 2c - If image shows no damage:**

```
Tool results: damage_detected: false
Bot: "I've looked at the photo but I don't see visible damage.
      Could you try a different angle? If you believe there's
      damage I'm missing, I can connect you with an agent."
Tools: [] (offer but don't auto-assign)
```

---

## Implementation Steps

### Step 1: Update `_analyze_query()` Prompt

In the tool descriptions, add conditional usage guidance for commitment tools.

**Changes to make:**

1. Add "TOOL SELECTION RULES" section (as shown above)
2. Update `assign_agent` description to include when NOT to use it
3. Add "DAMAGE CLAIM FLOW" example to guide multi-turn thinking

### Step 2: Update `_generate_response()` Prompt (Minor)

Add guidance for when tools partially fail:

```
IF image_analysis failed but other tools succeeded:
- Focus on the image issue
- Ask user to re-upload
- Do NOT mention agent assignment if one wasn't made
- Do NOT offer agent yet - wait for successful image analysis
```

---

## What NOT To Do

❌ **Don't add code logic to block assign_agent**

- This defeats the purpose of LLM-driven decisions
- The prompt should teach the LLM when to use it

❌ **Don't make tools dependent in code**

- No "run image_analysis first, then decide on assign_agent"
- Let LLM learn the pattern through prompt guidance

❌ **Don't over-engineer**

- Simple prompt additions, not complex new logic
- The LLM is smart enough to understand "don't assign agent until damage is confirmed"

---

## Summary of Changes

| File                        | Section                       | Change                                          |
| --------------------------- | ----------------------------- | ----------------------------------------------- |
| `customer_support_agent.py` | `_analyze_query()` prompt     | Add tool selection rules + damage flow guidance |
| `customer_support_agent.py` | `_analyze_query()` prompt     | Update `assign_agent` tool description          |
| `customer_support_agent.py` | `_generate_response()` prompt | Add guidance for partial tool failures          |

**Estimated effort:** ~30 lines of prompt text changes

---

## Testing After Implementation

Test these scenarios:

- [ ] Damage claim + image provided → Should NOT assign agent in same turn
- [ ] Damage confirmed + user says "yes connect me" → Should assign agent
- [ ] Image analysis fails → Should ask for re-upload, NO agent assigned
- [ ] User explicitly says "I want to talk to someone" → Should assign immediately
- [ ] Urgent safety issue → Should assign immediately (no image needed)
- [ ] Image shows no damage → Should inform user, offer escalation option

---

## Why This Works

1. **Follows natural conversation flow** - Just like a human agent would verify before escalating
2. **Uses LLM intelligence** - No hardcoded tool blocking, just better guidance
3. **Matches real support behavior** - Verify first, commit later
4. **Saves human agent time** - Only escalates verified issues
5. **Better user experience** - Clear communication at each step
