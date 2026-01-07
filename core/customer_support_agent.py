"""
Optimized Single-Pass Agent System with Workflow Routing
Combines semantic analysis, tool execution, and response generation in minimal LLM calls
Now supports sequential tool execution with middleware for dependent tools

WORKFLOW STAGES (follows JSON workflow):
1. AIIntakeLayer → Initial sentiment analysis and categorization
2. DeEscalation → Handles frustrated/angry customers with empathy
3. PreEscalationGathering → Gather info (photo/reason) before escalation
4. SensitiveTask → Decision: Refund/cancel/personal data?
5. ComplianceVerification → Fraud check + image analysis for sensitive operations
6. SecureHandlingTeam → Human handles verified sensitive operations
7. AIResolvable → Decision: Can AI handle this?
8. AIAutoResponse → AI provides information (order status, FAQs)
9. InstantConfirmation → Quick resolution confirmation
10. ImmediateIssue → Decision: Urgent or can wait?
11. AIAssistedRouting → Urgent escalation to human agent
12. TicketCreation → Create ticket for non-urgent issues

TOOLS:
- live_information, knowledge_base, verification, image_analysis, 
  assign_agent, raise_ticket, order_action (all placeholders)
"""

import json
import logging
import asyncio
import uuid
import re
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from os import getenv
from functools import partial
from .config import AddBackgroundTask

logger = logging.getLogger(__name__)



class CustomerSupportAgent:
    """Simplified agent for customer support with minimal LLM calls"""
    
    def __init__(self, brain_llm, heart_llm, tool_manager):
        self.brain_llm = brain_llm  # For analysis
        self.heart_llm = heart_llm  # For response generation
        self.tool_manager = tool_manager
        self.available_tools = tool_manager.get_available_tools()
        self.task_queue: asyncio.Queue["AddBackgroundTask"] = asyncio.Queue()
        self._worker_started = False
        
        logger.info(f"CustomerSupportAgent initialized with tools: {self.available_tools}")
    
    async def process_query(self, query: str, chat_history: List[Dict] = None, user_id: str = None) -> Dict[str, Any]:
        """Process customer query with minimal LLM calls"""
        self._start_worker_if_needed()
        logger.info(f"🔵 PROCESSING QUERY: '{query}'")
        start_time = datetime.now()
        
        analysis = None
        analysis_time = 0.0
        
        try:
            logger.info(f"🧠 Using chat history for context")
            
            # Analyze query
            analysis_start = datetime.now()
            analysis = await self._analyze_query(query, chat_history)
            analysis_time = (datetime.now() - analysis_start).total_seconds()
            
            # Log analysis results
            logger.info(f"📊 ANALYSIS RESULTS:")
            logger.info(f"   Intent: {analysis.get('intent', 'Unknown')}")
            logger.info(f"   Sentiment: {analysis.get('sentiment', {}).get('emotion', 'neutral')}")
            logger.info(f"   Needs More Info: {analysis.get('needs_more_info', False)}")
            logger.info(f"   Missing Info: {analysis.get('missing_info', 'none')}")
            logger.info(f"   Tools Selected: {analysis.get('tools_to_use', [])}")
            logger.info(f"   Tool Sequence: {analysis.get('tool_sequence', 'parallel')}")
            logger.info(f"   Needs De-escalation: {analysis.get('needs_de_escalation', False)}")
            
            # WORKFLOW ROUTING: Validate and route based on workflow stage
            workflow_stage = analysis.get('workflow_stage', 'AIAutoResponse')
            next_stage = analysis.get('next_stage', '')
            workflow_path = analysis.get('workflow_path', [workflow_stage])
            
            logger.info(f"📍 WORKFLOW ROUTING:")
            logger.info(f"   Current Stage: {workflow_stage}")
            logger.info(f"   Next Stage: {next_stage}")
            logger.info(f"   Workflow Path: {' → '.join(workflow_path)}")
            
            # Validate tools match workflow stage
            tools_to_use = self._validate_workflow_tools(workflow_stage, analysis.get('tools_to_use', []), analysis)
            
            logger.info(f"   Validated Tools: {tools_to_use}")
            
            # STEP 2: Skip tool execution if we need more info from customer
            if analysis.get('needs_more_info', False):
                logger.info("❓ Need more info from customer - skipping tools")
                tool_results = {}
                tool_time = 0.0
            else:
                # Execute tools
                tool_start = datetime.now()
                tool_results = await self._execute_tools(tools_to_use, query, analysis, user_id)
                tool_time = (datetime.now() - tool_start).total_seconds()
            
            # STEP 3: Generate response
            response_start = datetime.now()
            
            final_response = await self._generate_response(
                query, analysis, tool_results, chat_history
            )
            
            response_time = (datetime.now() - response_start).total_seconds()
            total_time = (datetime.now() - start_time).total_seconds()
            
            # Count LLM calls (always 2: Analysis + Response)
            llm_calls = 2
            
            logger.info(f"✅ COMPLETED in {total_time:.2f}s ({llm_calls} LLM calls)")
            
            return {
                "success": True,
                "response": final_response,
                "analysis": analysis,
                "tool_results": tool_results,
                "tools_used": tools_to_use,
                "workflow": {
                    "current_stage": workflow_stage,
                    "next_stage": next_stage,
                    "workflow_path": workflow_path,
                    "is_complete": analysis.get('is_workflow_complete', False)
                },
                "processing_time": {
                    "analysis": analysis_time,
                    "tools": tool_time,
                    "response": response_time,
                    "total": total_time
                },
                "llm_calls": llm_calls
            }
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": "I apologize, but I encountered an error. Please try again."
            }
    
    async def _analyze_query(self, query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """Analyze customer query to understand intent and select appropriate tools"""
        from datetime import datetime
        
        context = chat_history[-5:] if chat_history else []
        current_date = datetime.now().strftime("%B %d, %Y")
        
        analysis_prompt = f"""Analyze customer support query (date: {current_date})

        QUERY: {query}
        HISTORY: {context}

        WORKFLOW STAGES (follow in order):

        1. AIIntakeLayer: Analyze sentiment (emotion, intensity, urgency)
        
        2. De-Escalation: If emotion=angry/frustrated AND intensity=high → needs_de_escalation=true
        
        3. Sensitive Task (refund/cancel/exchange)?
           YES → Check what info needed FIRST:
           
           INFORMATION GATHERING:
           - If mentions: broken, defective, damaged, cracked, not working
             → missing_info="photo+reason", info_category="product_defect"
           
           - If mentions: don't like, changed mind, wrong size, don't need
             → missing_info="reason", info_category="preference_change"
           
           - If mentions: wrong item, different product
             → missing_info="photo+description", info_category="wrong_item"
           
           - If missing order_id → missing_info="order_id"
           
           THEN determine workflow:
           - If missing info → needs_more_info=true, workflow_stage="PreEscalationGathering"
           - If have all info → workflow_stage="ComplianceVerification"
             Tools: ["verification", "image_analysis", "assign_agent"] (sequential)
             Note: Only include image_analysis if photo was provided
           
           NO → Continue to Stage 4
        
        4. AI Resolvable (order status, FAQs, policies)?
           YES → workflow_stage="AIAutoResponse"
                 Tools: ["live_information"] or ["knowledge_base"]
           NO → Continue to Stage 5
        
        5. Urgent?
           YES → workflow_stage="AIAssistedRouting", tools=["assign_agent"]
           NO → workflow_stage="TicketCreation", tools=["raise_ticket"]

        Analyze and return JSON:

        1. CUSTOMER INTENT: What does the customer need?
        2. SENTIMENT: Emotion, intensity, urgency
        3. CONVERSATION STATE: Do you need more information before taking action?
        4. TOOL SELECTION: Which tools (if any) based on principles above
        5. RESPONSE STRATEGY: Tone, length, priority

        {{
        "intent": "what customer needs",
        "sentiment": {{"emotion": "frustrated|satisfied|confused|urgent|neutral", "intensity": "low|medium|high", "urgency": "low|medium|high"}},
        "needs_more_info": true or false,
        "missing_info": "order_id|photo|reason|photo+reason|photo+description|details|none",
        "info_category": "product_defect|preference_change|wrong_item|missing_order|none",
        "needs_de_escalation": true or false,
        "de_escalation_message": "brief empathy if needed",
        "tools_to_use": ["tool1", "tool2"],
        "tool_sequence": "parallel|sequential",
        "enhanced_queries": {{"live_information_0": "query", "knowledge_base_0": "query", "image_analysis_0": "analyze defect"}},
        "response_strategy": {{"tone": "empathetic|professional|friendly", "length": "brief|moderate", "priority": "emotion_first|solution_first"}},
        "workflow_stage": "AIIntakeLayer|DeEscalation|PreEscalationGathering|ComplianceVerification|SecureHandlingTeam|AIAutoResponse|AIAssistedRouting|TicketCreation",
        "next_stage": "next stage",
        "workflow_path": ["stage1", "stage2"]
        }}"""

        try:
            response = await self.brain_llm.generate(
                messages=[{"role": "user", "content": analysis_prompt}],
                system_prompt=f"You analyze customer queries as of {current_date}. Return JSON only.",
                temperature=0.1,
                max_tokens=2000
            )
            
            json_str = self._extract_json(response)
            result = json.loads(json_str)
            
            logger.info(f"✅ Analysis complete")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return self._get_fallback_analysis(query)
    
    def _get_fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis when parsing fails"""
        return {
            "intent": query,
            "sentiment": {
                "emotion": "neutral",
                "intensity": "medium",
                "urgency": "medium"
            },
            "needs_more_info": False,
            "missing_info": "none",
            "needs_de_escalation": False,
            "de_escalation_message": "",
            "tools_to_use": [],
            "tool_sequence": "parallel",
            "enhanced_queries": {},
            "response_strategy": {
                "tone": "professional",
                "length": "moderate",
                "priority": "solution_first"
            },
            "key_points": []
        }

    async def _execute_tools(self, tools: List[str], query: str, analysis: Dict, user_id: str = None) -> Dict[str, Any]:
        """Execute tools in parallel or sequentially based on analysis"""
        if not tools:
            return {}
        
        results = {}
        enhanced_queries = analysis.get('enhanced_queries', {})
        tool_sequence = analysis.get('tool_sequence', 'parallel')
        
        # Check if we need sequential execution (verification → order_action)
        if tool_sequence == 'sequential' and 'verification' in tools:
            # Run verification first
            logger.info("🔐 Running verification check first...")
            result = await self.tool_manager.execute_tool('verification', query=query, user_id=user_id)
            results['verification_0'] = result
            
            # Check risk level
            risk = result.get('fraud_check', {}).get('risk_level', 'low')
            if risk == 'high':
                logger.warning("⚠️ High fraud risk detected - skipping order_action")
                # Remove order_action from tools
                tools = [t for t in tools if t != 'order_action']
                # Add assign_agent instead
                if 'assign_agent' not in tools:
                    tools.append('assign_agent')
                    logger.info("🚨 Adding assign_agent for human review")
            
            # Now run remaining tools in parallel
            remaining_tools = [t for t in tools if t != 'verification']
            if remaining_tools:
                await self._execute_parallel(remaining_tools, enhanced_queries, query, user_id, results)
        else:
            # Parallel execution (existing logic)
            await self._execute_parallel(tools, enhanced_queries, query, user_id, results)
        
        return results
    
    async def _execute_parallel(self, tools: List[str], enhanced_queries: Dict, query: str, user_id: str, results: Dict):
        """Helper for parallel tool execution"""
        tasks = []
        tool_counter = {}
        
        for tool in tools:
            if tool in self.available_tools:
                count = tool_counter.get(tool, 0)
                tool_counter[tool] = count + 1
                
                indexed_key = f"{tool}_{count}"
                tool_query = enhanced_queries.get(indexed_key, query)
                
                logger.info(f"🔧 Executing {indexed_key}: '{tool_query}'")
                
                task = self.tool_manager.execute_tool(tool, query=tool_query, user_id=user_id)
                tasks.append((indexed_key, task))
        
        # Gather results
        for tool_name, task in tasks:
            try:
                result = await task
                results[tool_name] = result
                logger.info(f"✅ {tool_name} completed")
            except Exception as e:
                logger.error(f"❌ {tool_name} failed: {e}")
                results[tool_name] = {"error": str(e)}
    
    def _validate_workflow_tools(self, workflow_stage: str, selected_tools: List[str], analysis: Dict) -> List[str]:
        """Validate that selected tools align with workflow stage and adjust if needed"""
        
        # Define expected tools for each workflow stage
        stage_tool_mapping = {
            "AIIntakeLayer": [],
            "DeEscalation": [],
            "PreEscalationGathering": [],  # NEW - gathering info before escalation
            "SensitiveTask": [],
            "ComplianceVerification": ["verification", "image_analysis", "assign_agent"],  # Updated - added image_analysis
            "SecureHandlingTeam": ["assign_agent"],
            "AIResolvable": [],
            "AIAutoResponse": ["live_information", "knowledge_base"],
            "InstantConfirmation": [],
            "ImmediateIssue": [],
            "AIAssistedRouting": ["assign_agent"],
            "LiveAgentAssist": ["assign_agent"],
            "QuickResolution": ["order_action"],
            "TicketCreation": ["raise_ticket"],
            "Investigation": [],
            "FollowUp": [],
            "PostResolution": []
        }
        
        expected_tools = stage_tool_mapping.get(workflow_stage, [])
        
        # If stage has expected tools, validate selection
        if expected_tools:
            # Check if selected tools align with stage
            valid_tools = [tool for tool in selected_tools if tool in expected_tools or tool in self.available_tools]
            
            # If ComplianceVerification, ensure proper tool chain
            if workflow_stage == "ComplianceVerification":
                # Always need verification and assign_agent
                if "verification" not in valid_tools:
                    valid_tools.insert(0, "verification")
                if "assign_agent" not in valid_tools:
                    valid_tools.append("assign_agent")
                
                # Add image_analysis only if customer provided photo (check missing_info)
                missing_info = analysis.get('missing_info', 'none')
                if 'photo' not in missing_info and "image_analysis" not in valid_tools:
                    # Photo was provided, add image_analysis
                    valid_tools.insert(1, "image_analysis")
                    logger.info(f"   🖼️ Added image_analysis (photo available)")
                elif 'photo' in missing_info and "image_analysis" in valid_tools:
                    # Photo not provided yet, remove image_analysis
                    valid_tools.remove("image_analysis")
                    logger.info(f"   ⚠️ Removed image_analysis (no photo yet)")
                
                # Ensure sequential execution
                analysis['tool_sequence'] = 'sequential'
                logger.info(f"   ⚙️ ComplianceVerification chain: {valid_tools}")
            
            # If no valid tools but stage expects tools, use first expected tool
            if not valid_tools and expected_tools:
                valid_tools = [expected_tools[0]]
                logger.warning(f"   ⚠️ No valid tools for {workflow_stage}, using default: {expected_tools[0]}")
            
            return valid_tools
        
        # For decision stages or no-tool stages, return selected tools as-is
        return selected_tools
    
    async def _generate_response(self, query: str, analysis: Dict, tool_results: Dict, 
                                 chat_history: List[Dict]) -> str:
        """Generate customer support response"""
        
        intent = analysis.get('intent', '')
        sentiment = analysis.get('sentiment', {})
        strategy = analysis.get('response_strategy', {})
        
        # Format tool results
        tool_data = self._format_tool_results(tool_results)
        context = chat_history[-5:] if chat_history else []
        
        response_prompt = f"""Customer support response generation.

        QUERY: {query}
        INTENT: {intent}
        SENTIMENT: {sentiment.get('emotion')}, urgency={sentiment.get('urgency')}
        WORKFLOW: {analysis.get('workflow_stage')}
        
        TOOLS EXECUTED: {"Yes" if tool_data != "No additional data available" else "No"}
        TOOL DATA: {tool_data}

        ============ RESPONSE RULES ============
        
        1. CHECK TOOL EXECUTION
        - If TOOLS EXECUTED=No → DO NOT claim "I've verified/connected/created"
        - Only describe actions if you see ACTUAL tool results
        
        2. HANDLE MISSING INFO (PRIORITY #1)
        If Needs More Info={analysis.get('needs_more_info', False)}, Missing={analysis.get('missing_info', 'none')}, Category={analysis.get('info_category', 'none')}:
          
          a) Show empathy (1 sentence)
          b) Ask specifically based on missing_info:
             - "order_id" → "Could you provide your order number?"
             - "photo" → "Could you share a photo of [the issue]?"
             - "reason" → "Could you tell me why you'd like [refund/exchange]?"
             - "photo+reason" → "Could you share a photo and briefly describe what happened?"
             - "photo+description" → "Could you share a photo and describe what you ordered vs what you got?"
          c) Explain next step: "Once I have that, I'll [verify/connect/help]."
          
          STOP HERE if needs_more_info=True
        
        3. DE-ESCALATION
        If needs_de_escalation={analysis.get('needs_de_escalation', False)}:
          START with: {analysis.get('de_escalation_message', '')}
        
        4. USE TOOL DATA
        - verification + image_analysis + assign_agent → "I've analyzed the issue and connected you with a specialist."
        - verification + assign_agent → "I've verified your request and connected you with a specialist."
        - assign_agent only → "Connecting you with an agent."
        - live_information/knowledge_base → Answer directly from data
        - raise_ticket → "Created ticket #[number]. Team will respond within [time]."
        
        5. FORMAT: Maximum 3-4 sentences, {strategy.get('tone', 'professional')} tone

        Generate response:"""

        try:
            max_tokens = {
                "brief": 150,
                "moderate": 300,
                "detailed": 500
            }.get(strategy.get('length', 'moderate'), 300)
            
            messages = chat_history[-4:] if chat_history else []
            messages.append({"role": "user", "content": response_prompt})
            
            logger.info("="*80)
            logger.info("💬 RESPONSE GENERATION PROMPT:")
            logger.info("="*80)
            logger.info(f"QUERY: {query}")
            logger.info(f"INTENT: {intent}")
            logger.info(f"SENTIMENT: {sentiment}")
            logger.info(f"TOOL RESULTS:\n{tool_data}")
            logger.info(f"MAX TOKENS: {max_tokens}")
            logger.info("="*80)
            
            response = await self.heart_llm.generate(
                messages,
                temperature=0.4,
                max_tokens=max_tokens,
                system_prompt="You are a helpful customer support assistant."
            )
            
            response = self._clean_response(response)
            
            logger.info("="*80)
            logger.info("✅ FULL RESPONSE GENERATED:")
            logger.info("="*80)
            logger.info(response)
            logger.info("="*80)
            logger.info(f"Response length: {len(response)} chars")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Response generation failed: {e}")
            return "I apologize, but I had trouble generating a response. Please try again."
    
    def _format_tool_results(self, tool_results: dict) -> str:
        """Format tool results for response generation"""
        if not tool_results:
            return "No additional data available"
        
        formatted = []
        
        for tool, result in tool_results.items():
            if isinstance(result, dict) and 'error' not in result:
                if "success" in result and result["success"]:
                    # Knowledge base results
                    if "retrieved" in result:
                        formatted.append(f"{tool.upper()}:\n{result.get('retrieved', '')}\n")
                    
                    # Web search results
                    elif 'results' in result and isinstance(result['results'], list):
                        formatted.append(f"{tool.upper()} RESULTS:\n")
                        for item in result['results'][:3]:
                            title = item.get('title', '')
                            snippet = item.get('snippet', '')
                            formatted.append(f"- {title}\n  {snippet}\n")
                    
                    # Calculator or other results
                    elif 'result' in result:
                        formatted.append(f"{tool.upper()}: {result['result']}")
        
        return "\n".join(formatted) if formatted else "No usable data"

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
    
    @staticmethod
    def get_workflow_stage_info() -> Dict[str, Dict[str, Any]]:
        """Get information about all workflow stages for documentation/debugging"""
        return {
            "AIIntakeLayer": {
                "description": "Initial sentiment analysis and categorization",
                "tools": [],
                "next_stages": ["DeEscalation", "SensitiveTask"],
                "decision": "Check if customer needs de-escalation"
            },
            "DeEscalation": {
                "description": "Handles frustrated/angry customers with empathy",
                "tools": [],
                "next_stages": ["SensitiveTask"],
                "decision": "After calming, proceed to task classification"
            },
            "PreEscalationGathering": {
                "description": "Gather info (photo/reason) before escalation",
                "tools": [],
                "next_stages": ["ComplianceVerification"],
                "decision": "Ask for photo/reason, then proceed to verification"
            },
            "SensitiveTask": {
                "description": "Decision: Refund/cancel/personal data?",
                "tools": [],
                "next_stages": ["PreEscalationGathering", "ComplianceVerification", "AIResolvable"],
                "decision": "Check if info needed → PreEscalationGathering, else → ComplianceVerification"
            },
            "ComplianceVerification": {
                "description": "Fraud check + image analysis for sensitive operations",
                "tools": ["verification", "image_analysis", "assign_agent"],
                "next_stages": ["SecureHandlingTeam"],
                "decision": "Verify fraud risk + analyze image (if provided) + escalate to human"
            },
            "SecureHandlingTeam": {
                "description": "Human handles verified sensitive operations",
                "tools": ["assign_agent"],
                "next_stages": ["PostResolution"],
                "decision": "Human agent handles the case"
            },
            "AIResolvable": {
                "description": "Decision: Can AI handle this?",
                "tools": [],
                "next_stages": ["AIAutoResponse", "ImmediateIssue"],
                "decision": "AI can resolve → AIAutoResponse, else → ImmediateIssue"
            },
            "AIAutoResponse": {
                "description": "AI provides information (order status, FAQs)",
                "tools": ["live_information", "knowledge_base"],
                "next_stages": ["InstantConfirmation"],
                "decision": "Issue resolved by AI"
            },
            "InstantConfirmation": {
                "description": "Quick resolution confirmation",
                "tools": [],
                "next_stages": ["PostResolution"],
                "decision": "Confirm resolution and close"
            },
            "ImmediateIssue": {
                "description": "Decision: Urgent or can wait?",
                "tools": [],
                "next_stages": ["AIAssistedRouting", "TicketCreation"],
                "decision": "Urgent → AIAssistedRouting, else → TicketCreation"
            },
            "AIAssistedRouting": {
                "description": "Urgent escalation to human agent",
                "tools": ["assign_agent"],
                "next_stages": ["LiveAgentAssist"],
                "decision": "Route to available agent immediately"
            },
            "LiveAgentAssist": {
                "description": "Human agent with AI assistance",
                "tools": ["assign_agent"],
                "next_stages": ["QuickResolution"],
                "decision": "Agent resolves the issue"
            },
            "QuickResolution": {
                "description": "Execute resolution (refund/replacement)",
                "tools": ["order_action"],
                "next_stages": ["PostResolution"],
                "decision": "Action completed"
            },
            "TicketCreation": {
                "description": "Create ticket for non-urgent issues",
                "tools": ["raise_ticket"],
                "next_stages": ["Investigation"],
                "decision": "Ticket created for later investigation"
            },
            "Investigation": {
                "description": "Background investigation (warehouse/courier)",
                "tools": [],
                "next_stages": ["FollowUp"],
                "decision": "Investigation in progress"
            },
            "FollowUp": {
                "description": "Proactive follow-up after resolution",
                "tools": [],
                "next_stages": ["PostResolution"],
                "decision": "Follow up with customer"
            },
            "PostResolution": {
                "description": "Final confirmation and feedback collection",
                "tools": [],
                "next_stages": [],
                "decision": "Workflow complete"
            }
        }