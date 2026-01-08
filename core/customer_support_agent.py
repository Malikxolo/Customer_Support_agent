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
- assign_agent: Escalate to human agent
- raise_ticket: Create support ticket for investigation
"""

import json
import logging
import asyncio
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
                "important": "Always escalate to assign_agent for refund/cancel/replace requests"
            },
            "assign_agent": {
                "purpose": "Connect customer with a human agent who can process refunds, replacements, etc.",
                "use_when": "After gathering all info (order ID, reason, photos if applicable) for: refund requests, cancellations, replacements, complex issues",
                "important": "NEVER use just because user says 'talk to agent' - first ask what their issue is. Gather all info before escalating."
            },
            "raise_ticket": {
                "purpose": "Create support ticket for investigation",
                "use_when": "Issue needs research (warehouse/courier checks) but is not urgent"
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
            logger.info(f"   Sentiment: {analysis.get('sentiment', {})}")
            logger.info(f"   Needs De-escalation: {analysis.get('needs_de_escalation', False)}")
            logger.info(f"   Needs More Info: {analysis.get('needs_more_info', False)}")
            logger.info(f"   Missing Info: {analysis.get('missing_info', 'none')}")
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
        """Analyze customer query using LLM intelligence"""
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Format chat history for embedding in prompt
        formatted_history = ""
        if chat_history:
            history_entries = []
            for msg in chat_history[-10:]:  # Last 10 messages for context
                role = msg.get('role', 'unknown').upper()
                content = msg.get('content', '')
                history_entries.append(f"{role}: {content}")
            formatted_history = "\n".join(history_entries)
        
        analysis_prompt = f"""You are analyzing a customer support query. Understand what the customer needs and decide how to help them.

TODAY'S DATE: {current_date}

CUSTOMER QUERY: {query}

CONVERSATION HISTORY (for context - check previous turns to understand follow-ups):
{formatted_history if formatted_history else 'No previous conversation.'}

AVAILABLE TOOLS:
{self.tool_descriptions}

=== WORKFLOW GUIDANCE ===

Think through these steps naturally:

1. UNDERSTAND THE CUSTOMER
   - How are they feeling? (angry, frustrated, confused, calm, satisfied)
   - How urgent is their issue?
   - If very angry/frustrated with high intensity → they need de-escalation (empathy first)

2. IDENTIFY THEIR NEED
   - What do they actually want? (refund, order status, information, help with issue, etc.)
   - Is this a follow-up to previous conversation? Check history for context.

3. DO YOU NEED MORE INFORMATION?
   FIRST: Check conversation history for info already provided.
   
   CRITICAL: If you previously asked for MULTIPLE pieces of info, verify ALL were provided.
   - If you asked for "order ID AND reason" → user must provide BOTH, not just one
   - If user only provided partial info → still mark needs_more_info=true for the remaining items
   - Do NOT proceed until you have everything you asked for
   
   What's needed for different requests:
   - For refund/cancellation → order ID + reason (need BOTH)
   - For damaged item → photo + description of damage
   - For wrong item → photo + what they received vs expected
   - For "I want to talk to agent" with NO context → what issue they're facing
   
   If ALL required info is available (from current message + history), then proceed.

4. SELECT TOOLS (only if you have enough info)
   - Order status/tracking questions → live_information
   - Policy/FAQ questions → knowledge_base  
   - Refund/cancel/replace requests → verification ONLY (then offer agent in response, don't auto-assign)
   - Damaged product with photo → image_analysis + verification (then offer agent in response)
   - Non-urgent issue needing research → raise_ticket

5. SPECIAL CASES
   - Customer asks for human BUT has already explained issue and we couldn't help → assign_agent
   - Customer asks for human WITHOUT explaining issue → Ask what's wrong first (needs_more_info=true)
   - High-risk verification result → assign_agent
   - Simple greeting or thanks → no tools needed

=== TOOL SELECTION RULES ===

Information-gathering tools (can run together):
   - live_information, knowledge_base, verification, image_analysis

Commitment tools (require user confirmation FIRST):
   - assign_agent → ONLY use when user explicitly confirms they want an agent
   - order_action → ONLY after verification passes
   - raise_ticket → creates a permanent record
   
ABSOLUTE RULE FOR ASSIGN_AGENT (HARD CONSTRAINT):

assign_agent is NOT a problem-solving step.
assign_agent is a permission-based action.

You MUST NOT include "assign_agent" in tools_to_use
unless the user has explicitly requested or confirmed
that they want to talk to a human agent
in their CURRENT message.

If escalation seems appropriate but the user has NOT confirmed:
- Do NOT select assign_agent
- Ask the user if they want to be connected to an agent
- Wait for their response in the next turn


Return your analysis as JSON:

{{
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
  "missing_info": "what specific info is needed (order_id, photo, reason, details) or null if none",
  "context_from_history": "any relevant info already provided in earlier messages (order_id, reason, etc) or null",
  "tools_to_use": ["tool1", "tool2"] or empty array if no tools needed,
  "tool_queries": {{
    "tool_name": "specific query to pass to this tool"
  }},
  "reasoning": "your decision logic: what user wants, why you chose these tools, what should happen next"
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
            
            logger.info(f"✅ Analysis complete: {result.get('intent', 'Unknown intent')}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return self._get_fallback_analysis(query)
    
    def _get_fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when parsing fails"""
        return {
            "intent": query,
            "sentiment": {"emotion": "neutral", "intensity": "medium", "urgency": "medium"},
            "needs_de_escalation": False,
            "de_escalation_approach": "",
            "needs_more_info": False,
            "missing_info": None,
            "tools_to_use": [],
            "tool_queries": {},
            "reasoning": "Fallback analysis - JSON parsing failed"
        }

    async def _execute_tools(self, tools: List[str], query: str, analysis: Dict, user_id: str = None) -> Dict[str, Any]:
        """Execute tools in parallel"""
        if not tools:
            return {}
        
        results = {}
        tasks = []
        tool_queries = analysis.get('tool_queries', {})
        
        for i, tool in enumerate(tools):
            if tool not in self.available_tools:
                logger.warning(f"⚠️ Tool '{tool}' not available, skipping")
                continue
            
            tool_key = f"{tool}_{i}"
            tool_query = tool_queries.get(tool, query)
            
            logger.info(f"🔧 Queueing {tool}: '{tool_query[:50]}...'")
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
- Context from History: {context_from_history if context_from_history else 'None'}
- Reasoning: {reasoning}

INFORMATION FROM TOOLS:
{tool_data}

INFORMATION STILL NEEDED FROM CUSTOMER: {missing_info if missing_info else 'None - you have what you need'}

=== RESPONSE GUIDELINES ===

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
   - If agent assigned → confirm help is on the way with ETA
   - If ticket created → give them the ticket number and timeline
   - If order/policy info retrieved → answer their question directly

5. HANDLE TOOL ERRORS:
   - If any tool shows "Error" or failed → acknowledge the issue
   - For image_analysis error → politely ask customer to share the image again (it may not have uploaded properly)
   - Don't pretend the tool worked if it failed
   - IMPORTANT: If image_analysis failed, focus ONLY on getting a proper image. Do NOT offer agent connection yet.
     Wait until image is successfully analyzed before offering to connect with an agent.

6. OFFERING ESCALATION:
   Check if agent was already assigned (look for "AGENT ASSIGNED" in tool results):
   
   - If AGENT ASSIGNED appears in tool results:
     → Agent is already connected. Confirm help is on the way with ETA.
   
   - If NO agent assigned yet AND verification was done:
     → ASK user: "Would you like me to connect you with an agent who can help with your [refund/replacement/etc]?"
     → Wait for their confirmation before actually assigning.
   
   - If explicit_request is null/None (customer is vague):
     → Ask what they need help with, or if just sharing feedback.
   
   - If needs_more_info = True:
     → Do NOT offer escalation. Just ask for the missing info.

7. BOT LIMITATIONS:
   - Bot CANNOT process refunds, cancellations, or replacements directly
   - For these requests: gather info → verify → ASK if they want agent → then connect
   - Never say "I'll process the refund" - say "Would you like me to connect you with an agent who can help?"

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
            
            elif tool_name == "assign_agent":
                agent_info = result.get('agent_info', {})
                formatted.append("👤 AGENT ASSIGNED:")
                formatted.append(f"  • Agent: {agent_info.get('agent_name', 'Support Specialist')}")
                formatted.append(f"  • ETA: {result.get('eta', '5-10 minutes')}")
                formatted.append(f"  • Channel: {result.get('channel', 'chat')}")
                if result.get('assignment_id'):
                    formatted.append(f"  • Reference: {result.get('assignment_id')}")
            
            elif tool_name == "raise_ticket":
                formatted.append("🎫 TICKET CREATED:")
                formatted.append(f"  • Ticket ID: {result.get('ticket_id', 'N/A')}")
                formatted.append(f"  • Status: {result.get('status', 'open')}")
                formatted.append(f"  • Priority: {result.get('priority', 'medium')}")
                if result.get('category'):
                    formatted.append(f"  • Category: {result.get('category')}")
            
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
    
