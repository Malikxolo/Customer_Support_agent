"""
Customer Support Agent - Intelligent Workflow System

Uses LLM intelligence to naturally follow customer support workflow:
- Analyzes customer intent, sentiment, and urgency
- Selects appropriate tools based on context
- Generates empathetic, helpful responses in customer's language

AVAILABLE TOOLS:
- live_information: Order status, tracking, customer data
- knowledge_base: Policies, FAQs, product info
- verification: Fraud check for sensitive operations
- image_analysis: Analyze product photos for damage/defects
- order_action: Process refunds, cancellations, replacements
- raise_ticket: Create support ticket for escalation (agent assigned in backend)
"""

import json
import logging
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from .config import AddBackgroundTask

logger = logging.getLogger(__name__)



class CustomerSupportAgent:
    """Intelligent customer support agent with minimal LLM calls"""
    
    def __init__(self, brain_llm, heart_llm, tool_manager, language_detector_llm=None):
        self.brain_llm = brain_llm  # For analysis
        self.heart_llm = heart_llm  # For response generation
        self.tool_manager = tool_manager
        self.language_detector_llm = language_detector_llm  # For language detection
        self.available_tools = tool_manager.get_available_tools()
        self.tool_descriptions = self._get_tool_descriptions()
        self.task_queue: asyncio.Queue["AddBackgroundTask"] = asyncio.Queue()
        self._worker_started = False
        
        logger.info(f"CustomerSupportAgent initialized with tools: {self.available_tools}")
    
    def _extract_conversation_state(self, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Extract conversation state from chat history to help LLM maintain context"""
        state = {
            "collected_info": {
                "order_id": None,
                "customer_name": None,
                "phone_number": None,
                "issue_type": None,
                "issue_description": None
            },
            "pending_action": None,
            "escalation_offered": False,
            "escalation_confirmed": False,
            "last_bot_question": None,
            "missing_info_requested": [],
            "ticket_attempted": False,
            "ticket_created": False,
            "out_of_scope_detected": False,
            "out_of_scope_topic": None,
            "info_refused": {},
            "times_asked_for_info": {}
        }
        
        if not chat_history:
            return state
        
        # Patterns to detect in conversation
        for i, msg in enumerate(chat_history):
            role = msg.get('role', '').lower()
            content = msg.get('content', '').lower()
            original_content = msg.get('content', '')
            
            if role == 'user':
                # Extract order ID patterns
                order_match = re.search(r'order\s*(?:id|#|number)?\s*[:#]?\s*(\d+)', content)
                if order_match:
                    state["collected_info"]["order_id"] = order_match.group(1)
                
                # Extract phone number (10 digits)
                phone_match = re.search(r'\b(\d{10})\b', content)
                if phone_match:
                    state["collected_info"]["phone_number"] = phone_match.group(1)
                
                # Extract name patterns
                name_patterns = [
                    r'(?:my name is|name is|i am|i\'m)\s+([A-Za-z]+)',
                    r'name\s*[:\-]?\s*([A-Za-z]+)'
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, content, re.IGNORECASE)
                    if name_match:
                        state["collected_info"]["customer_name"] = name_match.group(1).title()
                        break
                
                # Detect issue types
                if any(word in content for word in ['damaged', 'broken', 'defective', 'not working']):
                    state["collected_info"]["issue_type"] = "damaged_product"
                elif any(word in content for word in ['refund', 'money back']):
                    state["collected_info"]["issue_type"] = "refund"
                elif any(word in content for word in ['cancel', 'cancellation']):
                    state["collected_info"]["issue_type"] = "cancellation"
                elif any(word in content for word in ['wrong item', 'wrong product', 'different item']):
                    state["collected_info"]["issue_type"] = "wrong_item"
                
                # Detect escalation confirmation
                if any(phrase in content for phrase in ['yes', 'please escalate', 'escalate it', 'escalate this', 'talk to agent', 'human agent', 'connect me']):
                    # Check if bot previously offered escalation
                    if state["escalation_offered"]:
                        state["escalation_confirmed"] = True
                
            elif role == 'assistant':
                # Detect if bot offered escalation
                if any(phrase in content for phrase in [
                    'would you like me to escalate',
                    'would you like to escalate',
                    'want me to escalate',
                    'escalate this to our support team',
                    'connect you with a human agent',
                    'escalate to a human agent'
                ]):
                    state["escalation_offered"] = True
                    state["last_bot_question"] = "offered_escalation"
                
                # Detect if bot asked for specific info
                if 'name' in content and ('provide' in content or 'share' in content or 'tell' in content or '?' in content):
                    state["missing_info_requested"].append("customer_name")
                    state["last_bot_question"] = "asked_for_info"
                    state["times_asked_for_info"]["customer_name"] = state["times_asked_for_info"].get("customer_name", 0) + 1
                if 'phone' in content and ('provide' in content or 'share' in content or 'tell' in content or '?' in content):
                    state["missing_info_requested"].append("phone_number")
                    state["last_bot_question"] = "asked_for_info"
                    state["times_asked_for_info"]["phone_number"] = state["times_asked_for_info"].get("phone_number", 0) + 1
                if 'order' in content and ('id' in content or 'number' in content) and '?' in content:
                    state["missing_info_requested"].append("order_id")
                    state["last_bot_question"] = "asked_for_info"
                    state["times_asked_for_info"]["order_id"] = state["times_asked_for_info"].get("order_id", 0) + 1
                
                # Detect ticket creation attempt
                if 'technical issue' in content or 'try again' in content:
                    state["ticket_attempted"] = True
                if 'ticket' in content and ('created' in content or 'raised' in content):
                    state["ticket_created"] = True
                
                # Detect out-of-scope responses from bot
                if any(phrase in content for phrase in [
                    'outside what i can help',
                    'outside my scope',
                    'outside of my scope',
                    'not something i can assist',
                    'beyond my capabilities',
                    'unable to help with'
                ]):
                    state["out_of_scope_detected"] = True
            
            # Detect user refusals in user messages
            if role == 'user':
                refusal_patterns = [
                    (r"(?:i\s+)?(?:don'?t|do not|dont)\s+(?:have|remember|know)\s+(?:my\s+)?(?:the\s+)?order", "order_id"),
                    (r"(?:i\s+)?(?:don'?t|do not|dont)\s+(?:have|remember|know)\s+(?:my\s+)?(?:the\s+)?phone", "phone_number"),
                    (r"(?:i\s+)?(?:don'?t|do not|dont)\s+(?:have|remember|know)\s+(?:my\s+)?(?:the\s+)?name", "customer_name"),
                    (r"(?:i\s+)?(?:can'?t|cannot|cant)\s+(?:provide|give|share|tell)", "general"),
                    (r"(?:i\s+)?(?:don'?t|do not|dont)\s+(?:want to|wanna)\s+(?:provide|give|share|tell)", "general"),
                    (r"(?:i\s+)?(?:won'?t|will not|wont)\s+(?:provide|give|share|tell)", "general"),
                    (r"(?:not willing to|refuse to)\s+(?:provide|give|share)", "general"),
                    (r"(?:i\s+)?(?:don'?t|do not|dont)\s+have\s+(?:any\s+)?(?:image|photo|picture)", "image"),
                    (r"(?:i\s+)?(?:can'?t|cannot|cant)\s+(?:send|share|upload)\s+(?:any\s+)?(?:image|photo|picture)", "image")
                ]
                for pattern, info_type in refusal_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        state["info_refused"][info_type] = True
        
        # Determine pending action
        if state["escalation_confirmed"] and not state["ticket_created"]:
            state["pending_action"] = "raise_ticket"
        elif state["collected_info"]["issue_type"] in ["refund", "cancellation", "damaged_product", "wrong_item"]:
            if not state["escalation_offered"]:
                state["pending_action"] = "offer_escalation"
            elif state["escalation_confirmed"]:
                state["pending_action"] = "raise_ticket"
        
        return state
    
    def _format_conversation_state(self, state: Dict[str, Any]) -> str:
        """Format conversation state into readable text for the analysis prompt"""
        lines = []
        
        # Collected info
        collected = state.get("collected_info", {})
        collected_items = []
        if collected.get("order_id"):
            collected_items.append(f"order_id={collected['order_id']}")
        if collected.get("customer_name"):
            collected_items.append(f"customer_name={collected['customer_name']}")
        if collected.get("phone_number"):
            collected_items.append(f"phone={collected['phone_number']}")
        if collected.get("issue_type"):
            collected_items.append(f"issue_type={collected['issue_type']}")
        if collected.get("issue_description"):
            collected_items.append(f"issue_desc={collected['issue_description'][:50]}")
        
        lines.append(f"COLLECTED INFO: {', '.join(collected_items) if collected_items else 'None yet'}")
        
        # Pending action
        pending = state.get("pending_action")
        lines.append(f"PENDING ACTION: {pending if pending else 'None'}")
        
        # Escalation status
        lines.append(f"ESCALATION OFFERED BY BOT: {state.get('escalation_offered', False)}")
        lines.append(f"ESCALATION CONFIRMED BY USER: {state.get('escalation_confirmed', False)}")
        
        # What bot asked for
        if state.get("missing_info_requested"):
            lines.append(f"BOT PREVIOUSLY ASKED FOR: {', '.join(state['missing_info_requested'])}")
        
        # Last bot question type
        if state.get("last_bot_question"):
            lines.append(f"LAST BOT ACTION: {state['last_bot_question']}")
        
        # Ticket status
        if state.get("ticket_attempted"):
            lines.append("TICKET ATTEMPT: Previous attempt failed (missing info)")
        if state.get("ticket_created"):
            lines.append("TICKET STATUS: Already created")
        
        # Out-of-scope detection
        if state.get("out_of_scope_detected"):
            lines.append("OUT-OF-SCOPE: Bot already identified query as out-of-scope")
        
        # Info refusal tracking
        if state.get("info_refused"):
            refused_items = [k for k, v in state["info_refused"].items() if v]
            if refused_items:
                lines.append(f"INFO REFUSED BY USER: {', '.join(refused_items)}")
        
        # Times asked tracking
        if state.get("times_asked_for_info"):
            asked_counts = [f"{k}({v}x)" for k, v in state["times_asked_for_info"].items() if v > 0]
            if asked_counts:
                lines.append(f"TIMES BOT ASKED FOR INFO: {', '.join(asked_counts)}")
        
        # Add guidance based on state
        lines.append("")
        lines.append("STATE INTERPRETATION:")
        if state.get("out_of_scope_detected"):
            lines.append("→ This query was already identified as OUT OF SCOPE. Keep politely declining.")
        elif state.get("info_refused"):
            refused = [k for k, v in state["info_refused"].items() if v]
            if refused:
                lines.append(f"→ User REFUSED to provide: {', '.join(refused)}. Do NOT ask again. Explain you cannot proceed.")
        elif state.get("escalation_confirmed") and pending == "raise_ticket":
            lines.append("→ User ALREADY confirmed escalation. Proceed with raise_ticket if you have all required info.")
        elif state.get("escalation_offered") and not state.get("escalation_confirmed"):
            lines.append("→ Bot offered escalation but user hasn't confirmed yet.")
        elif state.get("missing_info_requested"):
            lines.append(f"→ Bot asked for {', '.join(state['missing_info_requested'])}. Check if user provided it.")
        
        return "\n".join(lines)
    
    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for LLM prompts"""
        tools_info = {
            "live_information": {
                "purpose": "Get real-time order and customer information",
                "use_when": "Customer asks about order status, tracking, delivery, order history",
                "examples": "Where is my order?, Track order #12345, What's my order status?"
            },
            "knowledge_base": {
                "purpose": "Search company policies, FAQs, product guides",
                "use_when": "Customer asks about policies, returns, shipping info, product questions",
                "examples": "What's your return policy?, How do I return an item?, Shipping times?"
            },
            "verification": {
                "purpose": "Fraud check and risk assessment for sensitive operations",
                "use_when": "Before processing refunds, cancellations, or account changes",
                "returns": "risk_level (low/medium/high) - if high, escalate to human"
            },
            "image_analysis": {
                "purpose": "Analyze product photos for damage, defects, or issues",
                "use_when": "Customer reports broken/defective item AND has shared a photo",
                "returns": "damage assessment, severity, recommendation"
            },
            "order_action": {
                "purpose": "DO NOT USE - Bot cannot process refunds/cancels/replacements",
                "use_when": "NEVER - these actions require human agent approval",
                "important": "Always escalate via raise_ticket for refund/cancel/replace requests"
            },
            "raise_ticket": {
                "purpose": "Create support ticket for escalation - an agent will be assigned in backend",
                "use_when": "After gathering all info (order ID, customer name, phone number, reason) for: refund requests, cancellations, replacements, complex issues, or issues needing research",
                "important": "NEVER create ticket just because user says 'talk to agent' - first ask what their issue is. Gather all info before creating ticket.",
                "required_params": "subject, description, customerName, customerId (phone number), category (based on issue type: damaged_product, refund, cancellation, wrong_item, delivery_issue, technical, billing, general)"
            }
        }
        
        formatted = []
        for name, info in tools_info.items():
            if name in self.available_tools:
                formatted.append(f"• {name}:")
                formatted.append(f"  Purpose: {info['purpose']}")
                formatted.append(f"  Use when: {info['use_when']}")
                if 'examples' in info:
                    formatted.append(f"  Examples: {info['examples']}")
                if 'returns' in info:
                    formatted.append(f"  Returns: {info['returns']}")
                if 'important' in info:
                    formatted.append(f"  ⚠️ {info['important']}")
        
        return "\n".join(formatted)
    
    async def _detect_and_translate(self, query: str, chat_history: List[Dict] = None) -> Dict[str, str]:
        """Detect language and translate to English if needed"""
        
        # If no language detector, default to English
        if not self.language_detector_llm:
            return {
                "detected_language": "english",
                "english_translation": query,
                "original_query": query
            }
        
        # Format chat history for context
        formatted_history = ""
        if chat_history:
            history_entries = []
            for msg in chat_history[-4:]:  # Last 4 messages for context
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                history_entries.append(f"{role}: {content}")
            formatted_history = "\n".join(history_entries)
        
        detection_prompt = f"""Analyze this query and identify its language, then translate if needed.

CONVERSATION HISTORY (for context - check previous turns to understand follow-ups):
{formatted_history if formatted_history else 'No previous conversation.'}

CURRENT QUERY: "{query}"

YOUR TASK:
1. Identify what language this query is written in
2. Be specific with your language detection:
   - If it's Roman/Latin script with Hindi vocabulary → "hinglish"
   - If it's Devanagari script → "hindi"
   - If it's pure English → "english"
   - For other languages, identify accurately (malayalam, tamil, telugu, etc.)
   - If romanized script of any Indian language → add "_romanized" (e.g., "malayalam_romanized")

3. If the query is NOT in English, translate it to English while preserving the exact meaning and intent
4. If already in English, keep it as is

Think naturally using your language understanding. No pattern matching, no hardcoded rules.

Return ONLY valid JSON:
{{
  "detected_language": "<language name or language_romanized>",
  "english_translation": "<English version or original if already English>"
}}

Examples:
- "kya kiya aaj?" → {{"detected_language": "hinglish", "english_translation": "what did you do today?"}}
- "what's the weather?" → {{"detected_language": "english", "english_translation": "what's the weather?"}}
- "क्या हाल है?" → {{"detected_language": "hindi", "english_translation": "how are you?"}}
"""
        
        try:
            logger.info(f"🌍 LANGUAGE DETECTION: Analyzing query...")
            
            response = await self.language_detector_llm.generate(
                messages=[{"role": "user", "content": detection_prompt}],
                system_prompt="You are a language detection expert. Analyze queries and return JSON only.",
                temperature=0.1,
                max_tokens=200
            )
            
            # Extract JSON from response
            json_str = self._extract_json(response)
            result = json.loads(json_str)
            
            detected_lang = result.get('detected_language', 'english')
            english_query = result.get('english_translation', query)
            
            logger.info(f"🌍 DETECTED LANGUAGE: {detected_lang}")
            logger.info(f"📝 ENGLISH TRANSLATION: {english_query}")
            
            return {
                "detected_language": detected_lang,
                "english_translation": english_query,
                "original_query": query
            }
            
        except Exception as e:
            logger.error(f"❌ Language detection failed: {e}, defaulting to English")
            return {
                "detected_language": "english",
                "english_translation": query,
                "original_query": query
            }
    
    async def process_query(self, query: str, chat_history: List[Dict] = None, user_id: str = None) -> Dict[str, Any]:
        """Process customer query with minimal LLM calls"""
        self._start_worker_if_needed()
        logger.info(f"🔵 PROCESSING QUERY: '{query}'")
        start_time = datetime.now()
        
        try:
            # Step 0: Language detection and translation
            language_detection_start = datetime.now()
            language_info = await self._detect_and_translate(query, chat_history)
            detected_language = language_info.get('detected_language', 'english')
            english_query = language_info.get('english_translation', query)
            language_detection_time = (datetime.now() - language_detection_start).total_seconds()
            
            logger.info(f"🌍 Language: {detected_language}, English query: '{english_query}'")
            
            # Step 1: Analyze query (1 LLM call) - use English translation
            analysis_start = datetime.now()
            analysis = await self._analyze_query(english_query, chat_history)
            analysis_time = (datetime.now() - analysis_start).total_seconds()
            
            # Log analysis details
            logger.info(f"📊 ANALYSIS RESULTS:")
            logger.info(f"   Intent: {analysis.get('intent', 'Unknown')}")
            logger.info(f"   Is In Scope: {analysis.get('is_in_scope', True)}")
            logger.info(f"   Out of Scope Reason: {analysis.get('out_of_scope_reason', 'N/A')}")
            logger.info(f"   Sentiment: {analysis.get('sentiment', {})}")
            logger.info(f"   Needs De-escalation: {analysis.get('needs_de_escalation', False)}")
            logger.info(f"   Needs More Info: {analysis.get('needs_more_info', False)}")
            logger.info(f"   Missing Info: {analysis.get('missing_info', 'none')}")
            logger.info(f"   User Refused Info: {analysis.get('user_refused_info', False)}")
            logger.info(f"   Refused Info Type: {analysis.get('refused_info_type', 'N/A')}")
            logger.info(f"   Cannot Proceed Reason: {analysis.get('cannot_proceed_reason', 'N/A')}")
            logger.info(f"   Tools Selected: {analysis.get('tools_to_use', [])}")
            logger.info(f"   Reasoning: {analysis.get('reasoning', 'N/A')}")
            
            # Step 2: Execute tools if needed
            tools_to_use = analysis.get('tools_to_use', [])
            
            if analysis.get('needs_more_info', False):
                logger.info("❓ Need more info - skipping tools")
                tool_results = {}
                tool_time = 0.0
            else:
                tool_start = datetime.now()
                tool_results = await self._execute_tools(tools_to_use, english_query, analysis, user_id)
                tool_time = (datetime.now() - tool_start).total_seconds()
            
            # Step 3: Generate response (1 LLM call) - pass detected language and English query
            response_start = datetime.now()
            final_response = await self._generate_response(english_query, analysis, tool_results, chat_history, detected_language)
            response_time = (datetime.now() - response_start).total_seconds()
            
            total_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ COMPLETED in {total_time:.2f}s (3 LLM calls: detection + analysis + response)")
            
            return {
                "success": True,
                "response": final_response,
                "analysis": analysis,
                "language": detected_language,
                "tool_results": tool_results,
                "tools_used": tools_to_use,
                "processing_time": {
                    "language_detection": language_detection_time,
                    "analysis": analysis_time,
                    "tools": tool_time,
                    "response": response_time,
                    "total": total_time
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": "I apologize, but I encountered an error. Please try again."
            }
    
    async def _analyze_query(self, query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Analyze customer query using LLM intelligence with conversation state tracking"""
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Extract conversation state from history (Fix 2.1)
        conv_state = self._extract_conversation_state(chat_history)
        
        # Format chat history for embedding in prompt
        formatted_history = ""
        if chat_history:
            history_entries = []
            for msg in chat_history[-10:]:  # Last 10 messages for context
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                history_entries.append(f"{role}: {content}")
            formatted_history = "\n".join(history_entries)
        
        # Format conversation state for prompt (Fix 2.2)
        state_summary = self._format_conversation_state(conv_state)
        
        analysis_prompt = f"""You are analyzing a customer support query. Use the CONVERSATION STATE to understand context and make smart decisions.

TODAY'S DATE: {current_date}

CUSTOMER QUERY: {query}

=== CONVERSATION STATE (CRITICAL - USE THIS) ===
{state_summary}

CONVERSATION HISTORY (raw messages for additional context):
{formatted_history if formatted_history else 'No previous conversation.'}

AVAILABLE TOOLS:
{self.tool_descriptions}

=== WORKFLOW GUIDANCE ===

Think through these steps naturally:

0. SCOPE CHECK (DO THIS FIRST - CRITICAL)
   Before anything else, determine if this query is within our support scope.
   
   IN-SCOPE (we CAN help):
   - Orders: status, tracking, delivery, history
   - Refunds, cancellations, replacements
   - Damaged/defective products, wrong items received
   - Return policy, shipping info, product questions
   - Account issues, billing questions
   - Any query related to our products/orders/services
   
   OUT-OF-SCOPE (we CANNOT help - NOT our domain):
   - Utilities: electricity, water, gas, internet outages
   - Weather, traffic, general knowledge
   - Other companies' products/services
   - Government services, legal/medical advice
   - Technical support for unrelated products
   - Random topics unrelated to orders/products
   
   If OUT OF SCOPE:
   - Set is_in_scope = false
   - Set out_of_scope_reason = what the topic is
   - Set tools_to_use = [] (NEVER use tools for out-of-scope)
   - Set needs_more_info = false (we don't need info for out-of-scope)
   - Do NOT offer escalation (escalation is ONLY for in-scope issues)
   - Response should politely decline and clarify what we CAN help with

1. UNDERSTAND THE CUSTOMER
   - How are they feeling? (angry, frustrated, confused, calm, satisfied)
   - How urgent is their issue?
   - If very angry/frustrated with high intensity → they need de-escalation (empathy first)

2. CHECK CONVERSATION STATE
   - What info has ALREADY been collected? (order_id, name, phone, issue type)
   - Is there a PENDING ACTION? (escalation confirmed but not executed?)
   - Did bot already offer escalation? Did user confirm?
   - What was the last thing bot asked for?

3. IDENTIFY THEIR NEED
   - What do they actually want? (refund, order status, information, help with issue, etc.)
   - Is this a follow-up providing info that was requested?
   - IMPORTANT: If user is providing info (name, phone, etc.) that was previously requested,
     this is a CONTINUATION of the previous action, not a new request.

4. DO YOU NEED MORE INFORMATION?
   FIRST: Check CONVERSATION STATE for info already provided.
   
   CRITICAL: Combine info from current message + conversation state.
   - If state shows order_id=89 and user now gives name+phone → you have everything!
   - Don't ask for info that's already in the state.
   
   What's needed for different requests:
   - For refund/cancellation → order ID + reason (need BOTH)
   - For damaged item → order ID + photo + description of damage (need ALL)
   - For wrong item → order ID + photo + what they received vs expected
   - For escalation/talk to agent → order ID + customer name + phone number + clear issue description (need ALL)
   - For "I want to talk to agent" with NO context → what issue they're facing + order ID + customer name + phone number
   
   IMPORTANT: You CANNOT create a ticket without: order_id, customer name, and phone number. Always ask for missing info.
   
   If ALL required info is available (from current message + state), then proceed.

4b. CHECK FOR USER REFUSAL TO PROVIDE INFO
   CRITICAL: Detect if user is refusing or unable to provide required information:
   - "I don't have my order ID" / "don't remember my order number"
   - "I can't provide that" / "I won't share my phone number"
   - "I don't want to give that information"
   - "I don't have any photo/image" / "can't send a picture"
   
   If user REFUSES or CANNOT provide mandatory info:
   - Set user_refused_info = true
   - Set refused_info_type = what they refused (order_id, phone_number, image, etc.)
   - Set cannot_proceed_reason = why this info is essential
   - Set needs_more_info = false (they already said no)
   - Set tools_to_use = [] (cannot proceed without required info)
   - Response should: explain why info is needed, suggest alternatives if any, gracefully close
   - Do NOT keep asking for the same info after explicit refusal
   
   Also check STATE for previous refusals - don't ask again for something user already refused.

5. SELECT TOOLS (only if you have enough info)
   - Order status/tracking questions → live_information
   - Policy/FAQ questions → knowledge_base  
   - Refund/cancel/replace requests → verification ONLY (then offer agent in response, don't auto-assign)
   - Damaged product with photo → image_analysis + verification (then offer agent in response)
   - Non-urgent issue needing research → raise_ticket

6. SPECIAL CASES
   - Customer asks for human BUT has already explained issue and we couldn't help → raise_ticket
   - Customer asks for human WITHOUT explaining issue → Ask what's wrong first (needs_more_info=true)
   - High-risk verification result → raise_ticket
   - Simple greeting or thanks → no tools needed

=== TOOL SELECTION RULES ===

Information-gathering tools (can run together):
   - live_information, knowledge_base, verification, image_analysis

Commitment tools (require user confirmation FIRST):
   - raise_ticket → ONLY use when user explicitly confirms they want escalation. Creates ticket and agent is assigned in backend.
   - order_action → ONLY after verification passes

=== SMART ESCALATION DETECTION (FIX FOR DOUBLE-ASKING) ===

CHECK THE CONVERSATION STATE:
- If escalation_offered=True AND escalation_confirmed=True → User ALREADY gave consent!
- If pending_action="raise_ticket" → We should execute raise_ticket now, not ask again.

DO NOT ask "would you like me to escalate?" if:
1. Bot already asked this in a previous turn (escalation_offered=True)
2. AND user confirmed (escalation_confirmed=True or user said yes/please/escalate in current message)

If escalation is already confirmed:
- Include "raise_ticket" in tools_to_use
- Fill in tool_parameters with ALL collected info from state + current message

=== HANDLING INFO-PROVIDING MESSAGES ===

If user's current message is JUST providing info (name, phone, etc.):
- Check what action was pending (from state)
- If pending_action="raise_ticket" and now we have all info → execute raise_ticket
- Do NOT treat this as a new conversation or ask "how can I help?"
- CONTINUE the pending action with the new info

Return your analysis as JSON:

{{
  "is_in_scope": true or false,
  "out_of_scope_reason": "what the out-of-scope topic is, or null if in-scope",
  "intent": "brief description of what customer wants",
  "explicit_request": "what specific action customer asked for (refund/replacement/cancel/reorder/status/etc) or null if vague",
  "sentiment": {{
    "emotion": "angry|frustrated|confused|neutral|satisfied|urgent",
    "intensity": "low|medium|high",
    "urgency": "low|medium|high|critical"
  }},
  "needs_de_escalation": true or false,
  "de_escalation_approach": "how to acknowledge their feelings if needed, or empty string",
  "needs_more_info": true or false,
  "missing_info": "what specific info is STILL needed (not already in state) or null if none",
  "user_refused_info": true or false,
  "refused_info_type": "what info user refused to provide (order_id/phone_number/image/etc) or null",
  "cannot_proceed_reason": "why we cannot proceed without the refused info, or null",
  "context_from_history": "summary of info from conversation state: order_id, name, phone, issue, etc.",
  "pending_action_from_state": "the pending_action from conversation state or null",
  "escalation_already_confirmed": true or false,
  "tools_to_use": ["tool1", "tool2"] or empty array if no tools needed,
  "tool_queries": {{
    "tool_name": "specific query to pass to this tool"
  }},
  "tool_parameters": {{
    "raise_ticket": {{
      "subject": "brief ticket title based on issue",
      "description": "detailed description including order_id, issue, customer request",
      "customerName": "customer's name from state OR current message",
      "customerId": "customer's phone number from state OR current message",
      "category": "one of: damaged_product, refund, cancellation, wrong_item, delivery_issue, technical, billing, general - based on issue type",
      "priority": "low/medium/high/urgent based on urgency"
    }}
  }},
  "reasoning": "your decision logic: what state shows, what user provided now, why you chose these tools, what should happen next"
}}"""

        try:
            response = await self.brain_llm.generate(
                messages=[{"role": "user", "content": analysis_prompt}],
                system_prompt="You analyze customer support queries intelligently. Return valid JSON only, no other text.",
                temperature=0.1,
                max_tokens=1500
            )
            
            json_str = self._extract_json(response)
            result = json.loads(json_str)
            
            # Merge conversation state info into tool_parameters if raise_ticket is selected
            if 'raise_ticket' in result.get('tools_to_use', []):
                tool_params = result.get('tool_parameters', {}).get('raise_ticket', {})
                # Fill from state if not provided by LLM
                if not tool_params.get('customerName') or tool_params.get('customerName') in ['null', None]:
                    tool_params['customerName'] = conv_state['collected_info'].get('customer_name')
                if not tool_params.get('customerId') or tool_params.get('customerId') in ['null', None]:
                    tool_params['customerId'] = conv_state['collected_info'].get('phone_number')
                if 'raise_ticket' not in result.get('tool_parameters', {}):
                    result['tool_parameters'] = result.get('tool_parameters', {})
                result['tool_parameters']['raise_ticket'] = tool_params
            
            logger.info(f"✅ Analysis complete: {result.get('intent', 'Unknown intent')}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return self._get_fallback_analysis(query)
    
    def _get_fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when parsing fails - signals error to response generator"""
        return {
            "is_in_scope": True,
            "out_of_scope_reason": None,
            "intent": query,
            "sentiment": {"emotion": "neutral", "intensity": "medium", "urgency": "medium"},
            "needs_de_escalation": False,
            "de_escalation_approach": "",
            "needs_more_info": False,
            "missing_info": None,
            "user_refused_info": False,
            "refused_info_type": None,
            "cannot_proceed_reason": None,
            "tools_to_use": [],
            "tool_queries": {},
            "reasoning": "Fallback analysis - JSON parsing failed",
            "is_fallback": True,
            "fallback_response": "I'm having a bit of trouble understanding your request. Could you please rephrase that or tell me more about what you need help with?"
        }

    async def _execute_tools(self, tools: List[str], query: str, analysis: Dict, user_id: str = None) -> Dict[str, Any]:
        """Execute tools in parallel"""
        if not tools:
            return {}
        
        results = {}
        tasks = []
        tool_queries = analysis.get('tool_queries', {})
        tool_parameters = analysis.get('tool_parameters', {})
        
        for i, tool in enumerate(tools):
            if tool not in self.available_tools:
                logger.warning(f"⚠️ Tool '{tool}' not available, skipping")
                continue
            
            tool_key = f"{tool}_{i}"
            tool_query = tool_queries.get(tool, query)
            
            # Get tool-specific parameters if provided by LLM
            extra_params = tool_parameters.get(tool, {})
            
            # Validate required fields for raise_ticket
            if tool == "raise_ticket":
                missing_fields = []
                if not extra_params.get('customerName') or extra_params.get('customerName') in ['null', 'Unknown', None, '']:
                    missing_fields.append('customer name')
                if not extra_params.get('customerId') or extra_params.get('customerId') in ['null', None, '']:
                    missing_fields.append('phone number')
                if not extra_params.get('subject') or extra_params.get('subject') in ['null', None, '']:
                    missing_fields.append('issue subject')
                if not extra_params.get('description') or extra_params.get('description') in ['null', None, '']:
                    missing_fields.append('issue description')
                
                if missing_fields:
                    # Fix 1.1: Return as clarification need, not error
                    results[tool_key] = {
                        "status": "needs_clarification",
                        "success": False,
                        "missing_fields": missing_fields,
                        "clarification_needed": f"To create your support ticket, I need: {', '.join(missing_fields)}"
                    }
                    logger.warning(f"⚠️ raise_ticket needs clarification - missing: {missing_fields}")
                    continue
            
            logger.info(f"🔧 Queueing {tool}: '{tool_query[:50]}...'")
            task = self.tool_manager.execute_tool(tool, query=tool_query, user_id=user_id, **extra_params)
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
    
    async def _generate_response(self, query: str, analysis: Dict, tool_results: Dict, 
                                 chat_history: List[Dict], detected_language: str = "english") -> str:
        """Generate customer support response"""
        
        # Format chat history
        formatted_history = ""
        if chat_history:
            history_entries = []
            for msg in chat_history[-4:]:
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                history_entries.append(f"{role}: {content}")
            formatted_history = "\n".join(history_entries)
        
        # Format tool results
        tool_data = self._format_tool_results(tool_results)
        
        logger.info("="*60)
        logger.info("🔧 TOOL RESULTS FOR RESPONSE:")
        logger.info("="*60)
        logger.info(tool_data)
        logger.info("="*60)
        
        # Check for fallback analysis (Fix 1.4)
        if analysis.get('is_fallback'):
            logger.warning("⚠️ Using fallback response due to analysis failure")
            return analysis.get('fallback_response', "I'm having trouble processing your request. Could you please rephrase that?")
        
        # Extract analysis data
        sentiment = analysis.get('sentiment', {})
        needs_de_escalation = analysis.get('needs_de_escalation', False)
        de_escalation_approach = analysis.get('de_escalation_approach', '')
        needs_more_info = analysis.get('needs_more_info', False)
        missing_info = analysis.get('missing_info')
        intent = analysis.get('intent', '')
        explicit_request = analysis.get('explicit_request')
        reasoning = analysis.get('reasoning', '')
        context_from_history = analysis.get('context_from_history')
        escalation_already_confirmed = analysis.get('escalation_already_confirmed', False)
        pending_action = analysis.get('pending_action_from_state')
        is_in_scope = analysis.get('is_in_scope', True)
        out_of_scope_reason = analysis.get('out_of_scope_reason')
        user_refused_info = analysis.get('user_refused_info', False)
        refused_info_type = analysis.get('refused_info_type')
        cannot_proceed_reason = analysis.get('cannot_proceed_reason')
        
        
        response_prompt = f"""You are a friendly, helpful customer support agent. Generate a response to help this customer.

CUSTOMER QUERY: {query}

RESPOND IN LANGUAGE: {detected_language}
(This is the language the customer used. You MUST respond in this exact language.)

CONVERSATION HISTORY (for context - check previous turns to understand follow-ups):
{formatted_history if formatted_history else 'No previous conversation.'}

CUSTOMER STATE:
- Emotion: {sentiment.get('emotion', 'neutral')}
- Intensity: {sentiment.get('intensity', 'medium')}
- Urgency: {sentiment.get('urgency', 'medium')}
- Needs de-escalation: {needs_de_escalation}

ANALYSIS CONTEXT:
- Intent: {intent}
- Explicit Request: {explicit_request if explicit_request else 'None - customer is vague about what they want'}
- Is In Scope: {is_in_scope}
- Out of Scope Reason: {out_of_scope_reason if out_of_scope_reason else 'N/A - query is in scope'}
- User Refused Info: {user_refused_info}
- Refused Info Type: {refused_info_type if refused_info_type else 'N/A'}
- Cannot Proceed Reason: {cannot_proceed_reason if cannot_proceed_reason else 'N/A'}
- Context from History: {context_from_history if context_from_history else 'None'}
- Pending Action: {pending_action if pending_action else 'None'}
- Escalation Already Confirmed: {escalation_already_confirmed}
- Reasoning: {reasoning}

INFORMATION FROM TOOLS:
{tool_data}

INFORMATION STILL NEEDED FROM CUSTOMER: {missing_info if missing_info else 'None - you have what you need'}

=== RESPONSE GUIDELINES ===

0. OUT-OF-SCOPE HANDLING (if is_in_scope = {is_in_scope}):
   If is_in_scope is FALSE:
   - Politely inform the user this topic is outside your support scope
   - Be clear but kind: "I'm sorry, but [topic] is outside what I can help with."
   - Clarify what you CAN help with: "I'm here to assist with orders, refunds, returns, and product-related queries."
   - Do NOT offer escalation (escalation is ONLY for in-scope issues we can't resolve)
   - Do NOT ask follow-up questions about the out-of-scope topic
   - If user persists, keep politely declining without frustration
   - Optionally suggest where they might get help (e.g., "You may want to contact [appropriate service]")
   - NEVER use any tools for out-of-scope queries

0b. CANNOT PROCEED - USER REFUSED INFO (if user_refused_info = {user_refused_info}):
   If user REFUSED to provide required information:
   - Acknowledge their concern/situation empathetically
   - Clearly state you CANNOT proceed without the required info: "{refused_info_type}"
   - Explain briefly WHY it's needed: "{cannot_proceed_reason}"
   - Offer alternatives if any exist:
     * For order_id: "You can find it in your order confirmation email or account order history"
     * For phone: "This is needed so our team can contact you about your issue"
   - If no alternatives or user is firm: "I understand. Unfortunately, without [info], I'm unable to assist with this request."
   - Do NOT keep asking for the same info after explicit refusal
   - Do NOT escalate just because user won't provide info
   - Offer to help with something else: "Is there anything else I can help you with?"

1. LANGUAGE REQUIREMENT:
   You MUST respond in: {detected_language}
   This is the language the customer used in their original query.
   If it's "hinglish", use romanized Hindi mixed with English.
   If it's a language with "_romanized" suffix, use romanized script.
   Match the customer's language exactly.

2. DE-ESCALATION (if needed = {needs_de_escalation}):
   Start with empathy. Approach: {de_escalation_approach if de_escalation_approach else 'Acknowledge their frustration, show you understand'}

3. MISSING INFORMATION (if needs_more_info = {needs_more_info}):
   - Acknowledge their request warmly
   - Ask specifically for: {missing_info}
   - Explain what you'll do once you have it

4. USING TOOL RESULTS:
   - If verification done → mention you've verified their request
   - If image analyzed → reference what was found
   - If ticket created → give them the ticket number and confirm an agent will reach out
   - If order/policy info retrieved → answer their question directly

5. HANDLE TOOL RESULTS:
   - If tool shows "CLARIFICATION NEEDED" → This is NOT an error! Ask for the missing info naturally.
     Example: "To create your ticket, I just need your name and phone number."
   - If any tool shows "Error" or failed → acknowledge a technical issue
   - For image_analysis error → politely ask customer to share the image again (it may not have uploaded properly)
   - Don't pretend the tool worked if it failed
   - IMPORTANT: If image_analysis failed, focus ONLY on getting a proper image. Do NOT offer agent connection yet.
     Wait until image is successfully analyzed before offering to connect with an agent.

6. OFFERING ESCALATION:
   Check if ticket was already created (look for "TICKET CREATED" in tool results):
   
   - If TICKET CREATED appears in tool results:
     → Ticket is created. Confirm an agent will reach out shortly with the ticket reference.
   
   - If CLARIFICATION NEEDED appears in tool results:
     → This means we tried to create ticket but need more info from customer.
     → Ask ONLY for the specific missing info listed. Be natural: "I just need your name and phone number to create the ticket."
     → Do NOT say "technical issue" - this is normal info gathering.
   
   - If raise_ticket shows actual ERROR (not clarification):
     → Apologize for the technical issue and say you'll try again.
   
   - If escalation_already_confirmed = True but no ticket created:
     → User already confirmed they want escalation. Do NOT ask again.
     → Either create the ticket (if we have info) or ask for the specific missing info.
   
   - If NO ticket created yet AND verification was done AND escalation NOT yet offered:
     → ASK user: "Would you like me to escalate this to our support team? An agent will reach out to help with your [refund/replacement/etc]."
     → Wait for their confirmation before creating ticket.
   
   - If explicit_request is null/None (customer is vague):
     → Ask what they need help with, or if just sharing feedback.
   
   - If needs_more_info = True:
     → Ask for the missing info. If escalation is pending, explain it's needed for the ticket.

7. BOT LIMITATIONS:
   - Bot CANNOT process refunds, cancellations, or replacements directly
   - For these requests: gather info → verify → ASK if they want to escalate → then create ticket
   - Never say "I'll process the refund" - say "Would you like me to escalate this to our support team?"

8. FORMAT:
   - Keep responses extremely short: 1 sentence for most answers within 10-20 wods. Only 2 sentences if absolutely necessary. Be direct and helpful.
   - Be warm but professional
   - End with a helpful next step or question if appropriate
   - Do NOT make up information that wasn't in the tool results
   - Do NOT claim you did something if no tools were executed

Generate your response:"""

        try:
            response = await self.heart_llm.generate(
                messages=[{"role": "user", "content": response_prompt}],
                system_prompt="You are a helpful, empathetic customer support agent. Respond naturally and helpfully.",
                temperature=0.4,
                max_tokens=400
            )
            
            response = self._clean_response(response)
            
            logger.info("="*60)
            logger.info("💬 RESPONSE GENERATED:")
            logger.info("="*60)
            logger.info(response)
            logger.info("="*60)
            logger.info(f"Response length: {len(response)} chars")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Response generation failed: {e}")
            return "I apologize, but I had trouble generating a response. Please try again."
    
    def _format_tool_results(self, tool_results: dict) -> str:
        """Format tool results for response generation"""
        if not tool_results:
            return "No tools were executed - respond based on your knowledge or ask for needed information."
        
        formatted = []
        
        for tool_key, result in tool_results.items():
            # Skip failed results
            if not isinstance(result, dict):
                continue
            
            # Fix 1.1: Handle clarification needs differently from errors
            if result.get('status') == 'needs_clarification':
                missing = result.get('missing_fields', [])
                clarification = result.get('clarification_needed', '')
                formatted.append(f"📋 CLARIFICATION NEEDED FOR TICKET:")
                formatted.append(f"   Missing information: {', '.join(missing)}")
                formatted.append(f"   → Ask the customer for: {clarification}")
                formatted.append(f"   Note: This is NOT an error - just need more info from customer")
                continue
            
            if result.get('error'):
                formatted.append(f"⚠️ {tool_key}: Error - {result.get('error')}")
                continue
            if not result.get('success', True):
                continue
            
            # Extract base tool name (remove _0, _1 suffix)
            tool_name = tool_key.rsplit('_', 1)[0] if '_' in tool_key else tool_key
            
            # Format based on tool type
            if tool_name == "live_information":
                data = result.get('data', {})
                if data:
                    formatted.append("📦 ORDER/CUSTOMER INFORMATION:")
                    for key, value in data.items():
                        formatted.append(f"  • {key}: {value}")
                else:
                    formatted.append("📦 ORDER INFO: No data found for this query")
            
            elif tool_name == "knowledge_base":
                articles = result.get('articles', [])
                retrieved = result.get('retrieved', '')
                if retrieved:
                    formatted.append(f"📚 KNOWLEDGE BASE:\n{retrieved}")
                elif articles:
                    formatted.append("📚 KNOWLEDGE BASE RESULTS:")
                    for article in articles[:3]:
                        title = article.get('title', 'Untitled')
                        content = article.get('content', '')[:300]
                        formatted.append(f"  • {title}: {content}")
                else:
                    formatted.append("📚 KNOWLEDGE BASE: No relevant articles found")
            
            elif tool_name == "verification":
                fraud_check = result.get('fraud_check', {})
                risk_level = fraud_check.get('risk_level', result.get('risk_level', 'unknown'))
                recommendation = fraud_check.get('recommendation', 'proceed')
                formatted.append("🔐 VERIFICATION RESULT:")
                formatted.append(f"  • Risk Level: {risk_level}")
                formatted.append(f"  • Recommendation: {recommendation}")
                if risk_level == 'high':
                    formatted.append("  ⚠️ HIGH RISK - Escalate to human agent")
            
            elif tool_name == "image_analysis":
                analysis = result.get('analysis', {})
                ai_detection = result.get('ai_detection', {})
                if analysis:
                    formatted.append("🖼️ IMAGE ANALYSIS:")
                    formatted.append(f"  • Damage Detected: {analysis.get('damage_detected', 'unknown')}")
                    formatted.append(f"  • Type: {analysis.get('damage_type', 'N/A')}")
                    formatted.append(f"  • Severity: {analysis.get('severity', 'unknown')}")
                    formatted.append(f"  • Description: {analysis.get('description', 'N/A')}")
                    formatted.append(f"  • Recommendation: {analysis.get('recommendation', 'N/A')}")
                if ai_detection.get('is_ai_generated'):
                    formatted.append("  ⚠️ Warning: Image may be AI-generated")
            
            elif tool_name == "raise_ticket":
                formatted.append("🎫 TICKET CREATED:")
                formatted.append(f"  • Ticket ID: {result.get('ticket_id', 'N/A')}")
                formatted.append(f"  • Status: {result.get('status', 'open')}")
                formatted.append(f"  • Priority: {result.get('priority', 'medium')}")
                if result.get('category'):
                    formatted.append(f"  • Category: {result.get('category')}")
                formatted.append("  • An agent will be assigned and will reach out shortly")
            
            elif tool_name == "order_action":
                action = result.get('action', 'unknown')
                formatted.append(f"📋 ORDER ACTION ({action.upper()}):")
                formatted.append(f"  • Status: {result.get('status', 'pending')}")
                if result.get('refund_amount'):
                    formatted.append(f"  • Refund Amount: ${result.get('refund_amount')}")
                if result.get('replacement_order_id'):
                    formatted.append(f"  • Replacement Order: {result.get('replacement_order_id')}")
                if result.get('tracking_number'):
                    formatted.append(f"  • Tracking: {result.get('tracking_number')}")
                if result.get('label_url'):
                    formatted.append(f"  • Return Label: {result.get('label_url')}")
        
        return "\n".join(formatted) if formatted else "No actionable tool results available."

    def _extract_json(self, response: str) -> str:
        """Extract JSON from LLM response"""
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response = '\n'.join(lines)
        
        # Find JSON boundaries
        json_start = response.find('{')
        json_end = response.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_end > json_start:
            return response[json_start:json_end+1]
        
        return response
    
    def _clean_response(self, response: str) -> str:
        """Clean final response for display"""
        response = response.strip()
        
        # Remove any markdown artifacts
        if response.startswith('```'):
            lines = response.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response = '\n'.join(lines)
        
        return response.strip()
    
    async def background_task_worker(self) -> None:
        """Process background tasks like memory storage"""
        while True:
            task: AddBackgroundTask = await self.task_queue.get()
            try:
                messages, user_id = task.params
                await task.func(messages=messages, user_id=user_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background task error: {e}")
            finally:
                self.task_queue.task_done()
    
    def _start_worker_if_needed(self):
        """Start background worker once"""
        if not self._worker_started:
            asyncio.create_task(self.background_task_worker())
            self._worker_started = True
            logger.info("✅ Background worker started")
    
