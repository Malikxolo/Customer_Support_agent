# Fix: Agent Should Use Conversation Context Intelligently

## The Problems Found in Logs

### Problem 1: Not Using Chat History for Already-Provided Information

**What happened:**

```
Turn 1:
User: "maine order kiya tha cake usme top layer damage hai"
Bot: "order ID aur photo share karein"

Turn 2:
User: "order id is this 123422 and image is [ img.png ]"
Bot: [runs image_analysis + verification]
Analysis: missing_info = None ✅ (correctly detected order ID was provided)

Turn 3-5:
User explains can't get image (friend has no internet)

Turn 6:
User: "vo nhi kr paa raha hai send mujhe re order ya refund krke do"
Bot Analysis: missing_info = "order_id" ❌
Bot Response: "kripya mujhe apka order_id bataein"

Turn 7:
User: "order id 12343212" (provides DIFFERENT ID - confused!)
```

**Why this is wrong:**

- User already said order ID was `123422` in Turn 2
- Bot successfully used it in Turn 2 (ran verification with that order ID)
- But in Turn 6, bot "forgot" and asked again
- This frustrates users - they feel unheard

**Root cause:**

- Analysis prompt doesn't instruct LLM to check chat history for already-mentioned info
- LLM only looks at current query, not full conversation context

---

### Problem 2: Hardcoded "Agent or Feedback" Pattern

**What happened:**

```
Turn 7:
User: "order id 12343212"
User intent: Clear request for refund/reorder (stated in previous turn)

Bot Response:
"main aapki refund ki request ko agent ke paas forward karunga,
 kya aapko agent se connect hona hai ya sirf feedback dena hai?"
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        ALWAYS asks this!
```

**Why this is wrong:**

- User explicitly said what they want: refund or reorder
- User didn't ask "should I talk to agent?"
- Bot is forcing a choice that wasn't requested
- This feels robotic and unnatural

**Real support behavior:**

- If user clearly states intent (refund/cancel/replace) → Act on it or escalate directly
- Don't ask "do you want agent or just feedback?" unless user is vague
- Feedback offer should be AFTER resolution, not during escalation

**Current (bad) pattern:**

```
User: "I want refund"
Bot: "Would you like to connect with agent or just give feedback?" ❌
```

**Natural pattern:**

```
User: "I want refund"
Bot: "I'm connecting you with an agent who can process your refund" ✅
```

---

## How Real Support Bots Work

### Context Awareness

Real support bots maintain conversation memory:

```
User: "My order 12345 is damaged"
Bot: "Sorry to hear that. Can you send a photo?"
User: "I can't get a photo right now. Just send me a refund"
Bot: [Should know order ID is 12345 from earlier in conversation]
     "I'll escalate order 12345 for refund processing"
     NOT: "What's your order ID?" ❌
```

### Smart Escalation

Real bots don't always ask "agent or feedback":

```
SCENARIO A - Clear Request:
User: "I want to cancel my order"
Bot: "I'll connect you with an agent who can cancel it" (direct escalation)
     NOT: "Do you want agent or feedback?" ❌

SCENARIO B - Vague Issue:
User: "Something seems wrong with my order"
Bot: "I can connect you with an agent, or is there something specific I can help with?"
     (offering choice makes sense here because intent is unclear)

SCENARIO C - After Resolution:
Bot: "Your refund is processed. Is there anything else?"
User: "No"
Bot: "Would you like to share feedback about your experience?" ✅
     (feedback offer AFTER issue is resolved, not during)
```

---

## The Fix: Update Prompts for Context Awareness

### Fix 1: Analysis Prompt - Add Chat History Checking

**Location:** In `_analyze_query()` method, add to the "3. DO YOU NEED MORE INFORMATION?" section:

**Add this guidance:**

```
CRITICAL - CHECK CONVERSATION HISTORY FIRST:
Before marking anything as missing_info, review the CONVERSATION HISTORY above:
   - If user mentioned order ID in previous turns → Use it, don't ask again
   - If user already explained their issue → Don't ask them to repeat it
   - If user already stated what they want (refund/cancel/etc.) → Acknowledge it

ONLY mark as missing_info if information was NEVER mentioned in the conversation.

If customer is repeating information they already gave → They're frustrated.
Set needs_more_info=false and proceed with available info from history.
```

**Update the missing_info return field description:**

From:

```
"missing_info": "what specific info is needed (order_id, photo, reason, details) or null if none"
```

To:

```
"missing_info": "what specific info is needed that was NEVER mentioned in conversation history (order_id, photo, reason, details) or null if none. CHECK HISTORY FIRST - don't ask for info already provided in previous turns"
```

---

### Fix 2: Response Prompt - Remove "Agent or Feedback" Pattern

**Location:** In `_generate_response()` method, update the response guidance section.

**Current issue:** Response prompt likely has pattern that always asks "agent or feedback?"

**Add this guidance to response prompt:**

```
ESCALATION BEHAVIOR:
When user needs agent connection (for refund/cancel/replace/complex issues):

1. If you've gathered all needed info (order ID, issue details, photos if needed):
   → Directly connect them: "I'm connecting you with an agent who can help with [specific action]"
   → Do NOT ask "do you want agent or feedback?" - they already requested help

2. If user's intent is clear and direct (they asked for refund/cancel/etc.):
   → Act on it immediately, don't create extra decision points
   → Match their directness with direct action

3. NEVER offer "feedback" option during active issue resolution
   → Feedback is for AFTER issue is resolved or conversation is ending
   → Don't mix feedback with escalation decisions

CONTEXT ACKNOWLEDGMENT:
When using information from earlier in conversation:
   → Acknowledge it naturally: "Based on order [X] you mentioned earlier..."
   → Shows you're listening and builds trust
   → Prevents user from feeling like they have to repeat themselves
```

---

## Example Scenarios with Fixes

### Scenario 1: From Logs - Asking for Order ID Again

**Current behavior (bad):**

```
Turn 2: User gives order 123422
Turn 6: User requests refund
        Bot: "What's your order ID?" ❌ (already given in Turn 2!)
```

**Fixed behavior:**

```
Turn 2: User gives order 123422
Turn 6: User requests refund
        Bot Analysis: Checks history → order_id = 123422 (from Turn 2)
        Bot: "I'm connecting you with an agent who can help with a refund
              for order 123422" ✅
```

---

### Scenario 2: From Logs - "Agent or Feedback" Pattern

**Current behavior (robotic):**

```
User: "vo nhi kr paa raha hai send mujhe re order ya refund krke do"
     (Translation: He can't send it, give me reorder or refund)

Bot: "kya aapko agent se connect hona hai ya sirf feedback dena hai?" ❌
     (Do you want to connect with agent or just give feedback?)
```

**Fixed behavior:**

```
User: Clear request for refund/reorder
Bot Analysis:
  - intent: refund or reorder (clear and direct)
  - user already stated what they want
  - no need to ask "agent or feedback?"

Bot: "Main aapko agent se connect kar raha hoon jo aapki refund process
      kar sakta hai" ✅
     (I'm connecting you with an agent who can process your refund)
```

---

### Scenario 3: Commitment Tool Flow (Keep Current Behavior)

**Current behavior (CORRECT - don't change):**

```
Turn 1: User reports damage + provides photo
Bot: [Runs image_analysis + verification]
     Does NOT auto-assign agent ✅

Turn 2: If damage confirmed:
        Bot: "I can see the damage. Would you like me to connect you
              with an agent who can arrange replacement/refund?"
        Waits for user confirmation ✅

Turn 3: User confirms "yes"
        Bot: [Now assigns agent] ✅
```

**This workflow is correct because:**

- Bot gathers info first (image analysis, verification)
- Bot OFFERS agent connection, doesn't force it
- Bot waits for user confirmation before assigning agent
- This prevents wasting human agent time on unverified issues

---

## What NOT To Do

❌ **Don't add code logic or hardcoded examples to prompts**

- Current prompts use guidance-based approach (good!)
- Just add context-checking guidance, not example dialogues
- Let LLM intelligence handle the actual reasoning

❌ **Don't change the commitment tool workflow**

- Current behavior: Bot gathers info → Offers agent → Waits for confirmation ✅
- This is CORRECT - don't make bot auto-assign agent
- Bot should never process refunds/cancels directly (always needs human agent)

❌ **Don't add parsing logic**

- Chat history is already passed to LLM
- Just tell LLM to check it, don't build extraction code

❌ **Don't remove the ability to ask questions**

- Sometimes asking is needed (vague intent, missing critical info)
- Just make it context-aware: "Don't ask for info already provided"

---

| ##File                    | Method                 | Section                                 | Change                                                                         |
| ------------------------- | ---------------------- | --------------------------------------- | ------------------------------------------------------------------------------ |
| customer_support_agent.py | `_analyze_query()`     | Step 3: "DO YOU NEED MORE INFORMATION?" | Add guidance to check conversation history before marking info as missing      |
| customer_support_agent.py | `_analyze_query()`     | JSON return description                 | Update `missing_info` field description to emphasize checking history          |
| customer_support_agent.py | `_generate_response()` | Response guidance                       | Add "ESCALATION BEHAVIOR" section - no "agent or feedback?" for clear requests |
| customer_support_agent.py | `_generate_response()` | Response guidance                       | Add "CONTEXT ACKNOWLEDGMENT" - acknowledge when using info from history        |

**Estimated effort:** ~15 lines of guidance text additions (no examples, no code logic)

**Style:** Match existing prompt style (guidance-based, not example-driven)uring" | Better UX, less robotic |

**Estimated effort:** ~40 lines of prompt text additions/modifications

---

## Testing After Implementation

Bot uses order ID from history, doesn't ask again

- [ ] User clearly states "I want refund" → Bot directly connects to agent, no "agent or feedback?" question
- [ ] User reports damage + provides photo → Bot runs image_analysis, then OFFERS agent (doesn't auto-assign)
- [ ] User confirms they want agent AFTER offer → Bot assigns agent (commitment tool workflow)
- [ ] Bot tries to process refund directly → Should NOT happen (always escalate to agent for refunds/cancels)
- [ ] User repeats info already given → Bot acknowledges: "based on order X you mentioned
- [ ] After resolution → Feedback offer is natural
- [ ] During active issue → No feedback offer
- [ ] User repeats information already given → Bot acknowledges "as you mentioned earlier..."

---

## Why This Works

1. **Respects conversation flow** - Bot uses what user already said
2. **Reduces friction** - No repetitive questions
3. **Feels natural** - No robotic "agent or feedback?" pattern
4. **Uses LLM intelligence** - Chat history is already there, just tell LLM to use it
5. **Better UX** - Users feel heard, not interrogated
6. **Matches real support** - Human agents don't ask for info they already have

---s

1. **Chat history is already passed to LLM** - We just need to tell it to use it

   - Add guidance: "Check conversation history before marking info as missing"
   - No code needed, no examples needed - just clear instruction

2. **Current commitment tool workflow is CORRECT** - Don't change it

   - Bot gathers info → Offers agent → Waits for confirmation ✅
   - Bot never processes refunds/cancels directly ✅
   - Keep this behavior

3. **Problem is in response generation** - Hardcoded "agent or feedback?" pattern
   - Remove this pattern, make it context-aware
   - If user clearly wants refund → Directly connect to agent
   - Don't create unnecessary decision points

\*\*Solution = Minimal prompt guidance additions, no code, no examplesnstead of context-aware guidance

**Solution = Better prompts, not more code** ✅
