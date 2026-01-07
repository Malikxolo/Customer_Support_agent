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
    
    def __init__(self, brain_llm, heart_llm, tool_manager):
        self.brain_llm = brain_llm  # For analysis
        self.heart_llm = heart_llm  # For response generation
        self.tool_manager = tool_manager
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
                "purpose": "Process refund, cancel, replace, generate return label",
                "use_when": "After verification passes with low/medium risk",
                "important": "Always use verification tool FIRST before this"
            },
            "assign_agent": {
                "purpose": "Escalate to human agent for immediate help",
                "use_when": "Very frustrated customer, urgent/complex issue, high fraud risk, customer requests human, sensitive operations after verification"
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
    
    async def process_query(self, query: str, chat_history: List[Dict] = None, user_id: str = None) -> Dict[str, Any]:
        """Process customer query with minimal LLM calls"""
        self._start_worker_if_needed()
        logger.info(f"🔵 PROCESSING QUERY: '{query}'")
        start_time = datetime.now()
        
        try:
            # Step 1: Analyze query (1 LLM call)
            analysis_start = datetime.now()
            analysis = await self._analyze_query(query, chat_history)
            analysis_time = (datetime.now() - analysis_start).total_seconds()
            
            # Log analysis details
            logger.info(f"📊 ANALYSIS RESULTS:")
            logger.info(f"   Language: {analysis.get('language', 'en')}")
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
                tool_results = await self._execute_tools(tools_to_use, query, analysis, user_id)
                tool_time = (datetime.now() - tool_start).total_seconds()
            
            # Step 3: Generate response (1 LLM call)
            response_start = datetime.now()
            final_response = await self._generate_response(query, analysis, tool_results, chat_history)
            response_time = (datetime.now() - response_start).total_seconds()
            
            total_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ COMPLETED in {total_time:.2f}s (2 LLM calls)")
            
            return {
                "success": True,
                "response": final_response,
                "analysis": analysis,
                "tool_results": tool_results,
                "tools_used": tools_to_use,
                "processing_time": {
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
   - What language are they writing in? (You must respond in the same language)
   - How are they feeling? (angry, frustrated, confused, calm, satisfied)
   - How urgent is their issue?
   - If very angry/frustrated with high intensity → they need de-escalation (empathy first)

2. IDENTIFY THEIR NEED
   - What do they actually want? (refund, order status, information, help with issue, etc.)
   - Is this a follow-up to previous conversation? Check history for context.

3. DO YOU NEED MORE INFORMATION?
   Consider if you're missing critical info to help them:
   - For refund/cancellation → Do you have the order ID?
   - For damaged item → Do you have a photo? Do you know what happened?
   - For wrong item → Do you have a photo? What did they receive vs expect?
   
   If missing essential info → set needs_more_info=true and specify what's missing

4. SELECT TOOLS (only if you have enough info)
   - Order status/tracking questions → live_information
   - Policy/FAQ questions → knowledge_base  
   - Refund/cancel requests → verification first (check risk), then assign_agent for handling
   - Damaged product with photo → image_analysis + verification + assign_agent
   - Very frustrated or complex issue → assign_agent
   - Non-urgent issue needing research → raise_ticket

5. SPECIAL CASES
   - Customer explicitly asks for human → assign_agent
   - High-risk verification result → assign_agent (not order_action)
   - Simple greeting or thanks → no tools needed

Return your analysis as JSON:

{{
  "language": "detected language code (en, es, fr, ar, de, etc.)",
  "intent": "brief description of what customer wants",
  "sentiment": {{
    "emotion": "angry|frustrated|confused|neutral|satisfied|urgent",
    "intensity": "low|medium|high",
    "urgency": "low|medium|high|critical"
  }},
  "needs_de_escalation": true or false,
  "de_escalation_approach": "how to acknowledge their feelings if needed, or empty string",
  "needs_more_info": true or false,
  "missing_info": "what specific info is needed (order_id, photo, reason, details) or null if none",
  "tools_to_use": ["tool1", "tool2"] or empty array if no tools needed,
  "tool_queries": {{
    "tool_name": "specific query to pass to this tool"
  }},
  "reasoning": "brief explanation of your decision"
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
            "language": "en",
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
                                 chat_history: List[Dict]) -> str:
        """Generate customer support response"""
        
        # Format chat history
        formatted_history = ""
        if chat_history:
            history_entries = []
            for msg in chat_history[-10:]:
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
        language = analysis.get('language', 'en')
        sentiment = analysis.get('sentiment', {})
        needs_de_escalation = analysis.get('needs_de_escalation', False)
        de_escalation_approach = analysis.get('de_escalation_approach', '')
        needs_more_info = analysis.get('needs_more_info', False)
        missing_info = analysis.get('missing_info')
        
        response_prompt = f"""You are a friendly, helpful customer support agent. Generate a response to help this customer.

CUSTOMER QUERY: {query}

RESPOND IN THIS LANGUAGE: {language}

CONVERSATION HISTORY (for context - check previous turns to understand follow-ups):
{formatted_history if formatted_history else 'No previous conversation.'}

CUSTOMER STATE:
- Emotion: {sentiment.get('emotion', 'neutral')}
- Intensity: {sentiment.get('intensity', 'medium')}
- Urgency: {sentiment.get('urgency', 'medium')}
- Needs de-escalation: {needs_de_escalation}

INFORMATION FROM TOOLS:
{tool_data}

INFORMATION STILL NEEDED FROM CUSTOMER: {missing_info if missing_info else 'None - you have what you need'}

=== RESPONSE GUIDELINES ===

1. LANGUAGE: You MUST respond in {language}. Mirror the customer's language exactly.

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

6. FORMAT:
   - Keep it concise (2-4 sentences unless explaining something complex)
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
    
