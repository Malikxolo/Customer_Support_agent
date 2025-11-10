"""
Standalone Analysis Prompt Tester
==================================
Optimized for thinking models (Qwen, Claude Sonnet, DeepSeek) - leverages their CoT naturally.

Usage:
    pip install aiohttp
    python test_analysis_prompt.py
"""

import asyncio
import json
import logging
from core.llm_client import LLMClient
from core.config import Config
from core.tools import ToolManager

logging.basicConfig(level=logging.INFO)

# ==================== MODEL CONFIGURATION ====================

# NEW: LLMLayer Configuration
LLMLAYER_CONFIG = {
    "enabled": False,  # Set to True to use LLMLayer instead of fact checker
    "api_key": "llm_d16da9b5eaeee7b30d06948d8b5c176f67fd5f61aa163b0389b656f958c22d54",  # Get from https://llmlayer.ai (FREE $2 credits)
    "api_url": "https://api.llmlayer.dev/api/v2/answer"
}

FACT_CHECKER_CONFIG = {
    "provider": "openrouter",
    # "model": "meta-llama/llama-3.3-70b-instruct",  # Set empty to disable fact checker (when using LLMLayer)
    "max_tokens": 2000
}

THINKING_MODEL_CONFIG = {
    "provider": "openrouter",
    "model": "qwen/qwen3-235b-a22b-thinking-2507",
    "max_tokens": 16000
}

# ==================== LLMLAYER CLIENT ====================

class LLMLayerClient:
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
    
    async def search(self, query: str) -> dict:
        import aiohttp
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Answer API payload - query breaking + search + scrape + summarize
        payload = {
            "query": query,
            "model": "groq/openai-gpt-oss-20b",
            "return_sources": True,
            "location": "in"  
        }
        
        print(f"🔍 DEBUG: Calling {self.api_url}")
        print(f"🔍 DEBUG: Payload: {payload}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    print(f"🔍 DEBUG: Status {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Response keys: {list(data.keys())}")
                        return {
                            "success": True,
                            "response": data.get("answer", "")
                        }
                    else:
                        text = await response.text()
                        print(f"❌ DEBUG: {response.status} - {text[:300]}")
                        return {"success": False}
        except Exception as e:
            print(f"❌ DEBUG: {type(e).__name__}: {e}")
            return {"success": False}


# ==================== LAYER 0: LLMLAYER ====================

async def run_llmlayer(query: str):
    if not LLMLAYER_CONFIG.get("enabled"):
        print("⏭️  LLMLayer disabled in config")
        return None
    
    if LLMLAYER_CONFIG["api_key"] == "llm_xxxxxxxxxxxxx":
        print("⚠️  LLMLayer API key not set. Get one at https://llmlayer.ai")
        print("   Sign up → Dashboard → Copy API key → Paste in LLMLAYER_CONFIG")
        return None
    
    print("\n🌐 LAYER 0: LLMLAYER")
    print("="*80)
    
    try:
        client = LLMLayerClient(
            api_key=LLMLAYER_CONFIG["api_key"],
            api_url=LLMLAYER_CONFIG["api_url"]
        )
        
        print(f"📤 Sending query to LLMLayer...")
        result = await client.search(query)
        
        if result.get("success"):
            print(f"✅ LLMLayer response received: {len(result['response'])} chars")
            return result['response']
        else:
            print(f"❌ LLMLayer failed: {result.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"❌ LLMLayer error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================== LAYER 1: FACT CHECKER PROMPT ====================

FACT_CHECKER_PROMPT = """You are an intelligent fact-checker that determines if a query needs current, real-time data to be answered accurately.

CURRENT DATE: {current_date}

USER QUERY: {query}

Your task: Analyze if this query requires information that changes over time and could affect reasoning if outdated.

Think about:
- Does this involve recent product releases, versions, or updates?
- Does this need current prices, availability, or specifications?
- Does this reference "latest", "current", "now", or specific recent timeframes?
- Does this involve time-sensitive data like weather, stocks, news, events?
- Would answering this incorrectly due to outdated information mislead the user?

If YES: Generate focused web search queries to fetch that current data.
- Keep searches short and keyword-focused
- Target the specific facts needed
- Use current year when relevant

If NO: The query can be answered with general knowledge or doesn't depend on time-sensitive facts.

OUTPUT ONLY THIS JSON (no other text):

{{
  "needs_current_data": true or false,
  "reasoning": "explain your decision in one sentence",
  "web_searches": ["search 1", "search 2"] or []
}}

Think carefully, then output your JSON."""

# ==================== LAYER 1: FACT CHECKER ====================

async def run_fact_checker(llm: LLMClient, query: str):
    """
    Layer 1: Check if query needs current data
    Returns: dict with needs_current_data, reasoning, web_searches
    """
    print("\n🔍 LAYER 1: FACT CHECKER")
    print("="*80)
    
    try:
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        
        response = await llm.generate(
            messages=[{"role": "user", "content": FACT_CHECKER_PROMPT.format(
                query=query,
                current_date=current_date
            )}],
            temperature=0.1
        )
        
        # Extract JSON
        json_str = response.strip()
        if json_str.startswith('```'):
            json_start = json_str.find('{')
            json_end = json_str.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = json_str[json_start:json_end+1]
        
        result = json.loads(json_str)
        
        if result.get('needs_current_data'):
            print(f"✅ Needs current data: {result.get('reasoning')}")
            print(f"🌐 Web searches to execute: {len(result.get('web_searches', []))}")
            for i, search in enumerate(result.get('web_searches', []), 1):
                print(f"   {i}. {search}")
        else:
            print(f"⏭️  No current data needed: {result.get('reasoning')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Fact checker error: {e}")
        return {"needs_current_data": False, "reasoning": "error in fact checking", "web_searches": []}

async def execute_web_searches(tool_manager: ToolManager, searches: list) -> str:
    """
    Execute web searches using ToolManager and format results
    Returns formatted web search data as string
    """
    if not searches:
        return ""
    
    print("\n🌐 EXECUTING WEB SEARCHES")
    print("="*80)
    
    all_results = []
    
    for i, search_query in enumerate(searches, 1):
        print(f"\n🔍 Search {i}/{len(searches)}: {search_query}")
        try:
            result = await tool_manager.execute_tool("web_search", query=search_query, scrape_top=1)
            
            if result.get('success') and result.get('results'):
                print(f"✅ Found {len(result['results'])} results")
                
                formatted = f"\nWEB SEARCH RESULTS for: {search_query}\n"
                formatted += "="*60 + "\n"
                
                for item in result['results'][:3]:
                    title = item.get('title', 'No title')
                    snippet = item.get('snippet', '')
                    
                    if 'scraped_content' in item and item['scraped_content']:
                        content = item['scraped_content']
                        if not content.startswith("["):
                            lines = content.split('\n')
                            cleaned_lines = []
                            for line in lines:
                                line = line.strip()
                                if len(line) < 40:
                                    continue
                                if line.count('http') > 2:
                                    continue
                                if line.startswith('![') or line.startswith('Image'):
                                    continue
                                cleaned_lines.append(line)
                            content = '\n'.join(cleaned_lines)
                        else:
                            content = snippet
                    else:
                        content = snippet
                    
                    # Debug prints
                    print(f"\n{'─'*60}")
                    print(f"📄 TITLE: {title}")
                    print(f"📊 CONTENT LENGTH: {len(content)} chars")
                    print(f"📝 CONTENT PREVIEW (first 200 chars):\n{content[:200]}...")
                    print(f"{'─'*60}")
                    
                    formatted += f"\n📄 {title}\n"
                    formatted += f"{content}\n"
                    formatted += "-"*60 + "\n"
                
                all_results.append(formatted)
            else:
                print(f"⚠️  No results for: {search_query}")
                
        except Exception as e:
            print(f"❌ Search failed: {e}")
    
    if all_results:
        return "\n\n".join(all_results)
    return ""

# ==================== LAYER 2: ANALYSIS PROMPT  ====================

ANALYSIS_PROMPT = """You are analyzing a user query for Mochan-D - an AI chatbot that automates customer support across WhatsApp, Facebook, Instagram with RAG and web search capabilities.

Available tools:
- web_search: Current internet data
- rag: Knowledge base retrieval  
- calculator: Math operations

USER QUERY: {query}

{current_facts}

CRITICAL INSTRUCTION - DATA FRESHNESS:
Any information that is liable to change, USE web-search to validate that. For standard definitions and facts, use your base data. Based on that, expand on the dimensionality aspect to retrieve all that information at once.

CORE PRINCIPLE: Think like a world-class consultant.
When someone asks for X, you don't just give X. You think: "What else do they need to make X truly successful?"

Your superpower: MULTI-DIMENSIONAL REASONING
- User mentions restaurant recommendations → Think: What about parking? Dietary restrictions? Price range?
- User asks for laptop → Think: What about accessories? Software? Warranty options?
- User wants recipe → Think: What about substitutes? Cooking tips? Storage instructions?

THINK THROUGH THESE QUESTIONS (use your intelligence, not rules):

1. WHAT DOES THE USER REALLY WANT?
   - Look beyond the literal words - what's their actual goal?
   - What emotional state are they in?
   - Is this one request or multiple separate things?

2. INFORMATION QUALITY CHECK - THINK BEYOND THE OBVIOUS
   Ask yourself repeatedly: "What am I missing?"
   
   - If I answer just what they asked, will it be complete?
   - What did the user NOT mention but would obviously need?
   - What alternatives or related options should they consider?
   - What context or background would make this more valuable?
   
   MULTI-DIMENSIONAL THINKING:
   Don't just answer the literal question. Think about:
   - WHAT they asked for (explicit need)
   - WHAT they forgot to ask (implicit need)
   - WHAT alternatives exist (options they should know about)
   - WHAT context matters (surrounding information)
   
   Mental process training:
   User says: "best laptop for video editing"
   Your thinking: "They said video editing... but they'll also need: storage solutions (external drives),
   editing software recommendations, color-accurate monitors, backup strategies. That's 5 dimensions:
   laptop specs + storage + software + display + backup. Each needs separate focused research."
   
   Use this expansion mindset for EVERY query.

3. IS THIS A BUSINESS PROBLEM?
   Think naturally: Does this query relate to challenges that an AI chatbot could solve?
   - Customer communication problems?
   - Need for automation or always-available support?
   - Managing multiple platforms or scaling interactions?
   
   If yes → this is a business context (you should include rag to provide Mochan-D context)
   If no → just answer the query directly

4. MULTI-DIMENSIONAL TASK BREAKDOWN - FIND ALL THE HIDDEN ANGLES
   
   Your job: Identify EVERY dimension of this query, including what user didn't explicitly say.
   
   CRITICAL MINDSET: When you think you have enough searches, DOUBLE IT.
   Most people under-search. You're smarter than that.
   
   Step 1: What did they LITERALLY ask for?
   Step 2: What did they IMPLY but not say?
   Step 3: What ALTERNATIVES should they know about?
   Step 4: What RELATED INFORMATION would be valuable?
   Step 5: What would a world-class expert include that others miss?
   
   Mental exercise for EVERY query:
   - If they mention ONE audience, are there OTHER audiences? (Create separate search for EACH)
   - If they ask for ONE thing, what RELATED things do they need? (Separate search for EACH)
   - If they want X, should they also know about Y and Z? (Separate search for EACH)
   - What examples would make this concrete? (Separate search)
   - What data would make this credible? (Separate search)
   - What best practices exist? (Separate search)
   - What alternatives or comparisons? (Separate search)
   
   RULE: Create a SEPARATE search for EACH dimension you discover.
   Don't merge dimensions - keep each one focused and distinct.
   If you're generating less than 5 searches for a complex query, you're missing dimensions.

5. HOW TO FORMAT YOUR QUERIES (CRITICAL):
   
   For web_search queries:
   - Write like you're typing into Google: SHORT, keyword-focused
   - Keep it under 6-8 words maximum
   - Focus on core terms only
   - Include year (2025) for time-sensitive topics
   
   For rag queries:
   - Natural language is OK: "product features value proposition"
   - You're searching internal documents

6. CAN TASKS RUN TOGETHER OR MUST THEY BE SEQUENTIAL?
   Default to PARALLEL (faster) unless:
   - One task clearly needs the results from another task to proceed
   - Think: "weather and what to wear" → clothing depends on weather data
   
7. FOR EACH WEB SEARCH, HOW DEEP SHOULD IT GO?
   Think about what's needed:
   - Quick factual lookup? → fewer pages
   - Need verification from multiple sources? → more pages
   - Complex research requiring comprehensive coverage? → more pages
   
   Decide naturally based on the query's nature

8. HOW SHOULD THE RESPONSE FEEL?
   Based on the user's tone and needs:
   - What personality would work best? (empathetic, professional, casual, excited, urgent)
   - How much detail do they need? (brief, moderate, comprehensive)
   - What language style fits? (formal english, casual english, hinglish)

FINAL CHECK BEFORE YOU OUTPUT:
- Did I find ALL dimensions of this query?
- Am I being generous with search count or conservative? (Be generous!)
- Did I use proper key names? (rag_0, web_search_0, web_search_1, etc.)
- For complex queries: Did I generate at least 5-7 searches?

OUTPUT THIS EXACT JSON STRUCTURE:

{{
  "reasoning_summary": "2-3 sentences explaining your thinking process",
  
  "intent_analysis": {{
    "real_goal": "what user actually wants to achieve",
    "user_emotion": "their emotional state",
    "query_complexity": "your assessment of complexity"
  }},
  
  "business_opportunity": {{
    "detected": true or false,
    "confidence": 0-100,
    "reasoning": "why you think this is/isn't business-related",
    "pain_points": ["specific problems you identified"] or []
  }},
  
  "task_breakdown": {{
    "multi_task": true or false,
    "tasks": ["each distinct task"],
    "expansion_applied": true or false,
    "expansion_reason": "why you expanded or kept it simple"
  }},
  
  "execution_plan": {{
    "mode": "parallel or sequential",
    "tools": ["list each tool - be generous with count"],
    "dependency_reason": "explain if sequential",
    "queries": {{
      "rag_0": "query for rag (use _0 suffix)",
      "web_search_0": "first focused search",
      "web_search_1": "second focused search",
      "web_search_2": "third focused search"
    }}
  }},
  
  "scraping_guidance": {{
    "web_search_0": {{
      "level": "low or medium or high",
      "pages": number you decide,
      "reason": "why this depth"
    }}
  }},
  
  "response_strategy": {{
    "personality": "tone you'll use",
    "length": "response length needed",
    "language": "language style",
    "key_points": ["main points to address"]
  }}
}}

Now analyze: {query}

Think through each question naturally, then return ONLY the JSON. No other text."""

# ==================== LAYER 2: THINKING MODEL ====================

async def run_thinking_model(llm: LLMClient, query: str, fact_check_result: dict, current_facts_data: str = ""):
    """
    Layer 2: Deep analysis with thinking model
    Uses current facts from Layer 1 if available
    """
    print("\n🧠 LAYER 2: THINKING MODEL")
    print("="*80)
    
    from datetime import datetime
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Build current facts section - will be placed at END of prompt
    if fact_check_result.get('needs_current_data') and current_facts_data:
        current_facts_text = f"""

⚠️ CRITICAL - REAL-TIME DATA (retrieved just now on {current_date}):
{current_facts_data}

IMPORTANT: Use the above CURRENT data in your reasoning. Do NOT use outdated training data.
"""
    else:
        current_facts_text = ""
    
    try:
        # Build main prompt
        main_prompt = ANALYSIS_PROMPT.format(
            query=query,
            current_facts=""  # Keep empty in main body
        )
        
        # Insert current facts RIGHT BEFORE the final "Now analyze" instruction
        final_prompt = main_prompt.replace(
            f"Now analyze: {query}",
            f"{current_facts_text}\n\nNow analyze: {query}"
        )
        
        # Enhanced system prompt with current date
        system_prompt = f"""You are analyzing queries as of {current_date}. 
When provided with real-time data, you MUST use it instead of your training data.
Think step by step, then output valid JSON only."""
        
        response = await llm.generate(
            messages=[{"role": "user", "content": final_prompt}],
            system_prompt=system_prompt,
            temperature=0.1
        )
        
        print(f"✅ Response: {len(response)} chars\n")
        
        # Extract JSON - handle thinking models
        json_str = response.strip()
        
        if json_str.startswith('```'):
            json_start = json_str.find('{')
            json_end = json_str.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = json_str[json_start:json_end+1]
        else:
            lines = json_str.split('\n')
            json_start = -1
            for i, line in enumerate(lines):
                if line.strip().startswith('{'):
                    json_start = json_str.find(line.strip())
                    break
            
            json_end = json_str.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                # Show thinking process if it exists
                if json_start > 0:
                    thinking = json_str[:json_start].strip()
                    if thinking:
                        print("\n" + "="*80)
                        print("💭 THINKING PROCESS:")
                        print("="*80)
                        print(thinking[:1000] + "..." if len(thinking) > 1000 else thinking)
                        print("\n")
                
                json_str = json_str[json_start:json_end+1]
        
        result = json.loads(json_str)
        return result
        
    except Exception as e:
        print(f"❌ Thinking model error: {e}")
        return None

# ==================== TEST QUERIES ====================

QUERIES = [
    "iPhone 16 price",
    "iPhone 16 vs Samsung S24 price",
    "Between the iPhone 16 Pro Max and the Samsung Galaxy S25 Ultra, which one has the better battery endurance, camera performance in low light, and real-time AI photo processing? Also, does Apple’s on-device ‘Apple Intelligence’ actually outperform Samsung’s Galaxy AI features when summarizing messages and generating custom emojis?",
    "Design a 7-day workout plan for a beginner aiming to build muscle and lose fat.",
    "Compare the top 3 CRM tools for small businesses",
    "Help me write a cold email to potential customers",
    "I need to plan a trip to Paris in December",
    "What's the current price of Bitcoin?",
    "Latest updates on OpenAI's GPT models"
]

# ==================== TEST RUNNER ====================

async def test_single_query(fact_checker_llm: LLMClient, thinking_llm: LLMClient, tool_manager: ToolManager, query: str, query_num: int, total: int):
    """Test a single query through both layers"""
    print(f"\n{'='*80}")
    print(f"📝 Query {query_num}/{total}: {query}")
    print(f"{'='*80}")
    
    try:
        # Try LLMLayer first
        llmlayer_data = await run_llmlayer(query)
        
        if llmlayer_data:
            # Use LLMLayer data
            analysis_result = await run_thinking_model(thinking_llm, query, {"needs_current_data": True}, llmlayer_data)
        else:
            # Use fact checker (only if fact checker model is set)
            if FACT_CHECKER_CONFIG.get('model'):
                fact_check_result = await run_fact_checker(fact_checker_llm, query)
                
                # Execute web searches if needed
                current_facts_data = ""
                if fact_check_result.get('needs_current_data') and fact_check_result.get('web_searches'):
                    current_facts_data = await execute_web_searches(tool_manager, fact_check_result['web_searches'])
                
                analysis_result = await run_thinking_model(thinking_llm, query, fact_check_result, current_facts_data)
            else:
                print("⚠️  Fact checker disabled and LLMLayer not available")
                analysis_result = await run_thinking_model(thinking_llm, query, {"needs_current_data": False}, "")
        
        if analysis_result:
            # Display results
            print("\n" + "="*80)
            print("📊 FINAL RESULTS")
            print("="*80)
            
            print(f"\n🎯 Intent Analysis:")
            print(f"   Real Goal: {analysis_result.get('intent_analysis', {}).get('real_goal', 'N/A')}")
            print(f"   User Emotion: {analysis_result.get('intent_analysis', {}).get('user_emotion', 'N/A')}")
            
            print(f"\n🔧 Execution Plan:")
            print(f"   Multi-Task: {analysis_result.get('task_breakdown', {}).get('multi_task', 'N/A')}")
            print(f"   Tools Count: {len(analysis_result.get('execution_plan', {}).get('tools', []))}")
            
            queries = analysis_result.get('execution_plan', {}).get('queries', {})
            web_searches = [k for k in queries.keys() if k.startswith('web_search')]
            print(f"   Web Searches: {len(web_searches)}")
            
            if web_searches:
                print(f"\n   🌐 Web Search Queries:")
                for ws in sorted(web_searches):
                    print(f"      • {queries[ws]}")
            
            print(f"\n📄 FULL JSON:\n{json.dumps(analysis_result, indent=2)}")
            return True
        else:
            return False
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

async def test():
    """Interactive test mode"""
    print(f"\n{'='*80}")
    print(f"🧪 ANALYSIS SYSTEM")
    print(f"{'='*80}")
    
    if LLMLAYER_CONFIG.get('enabled'):
        print(f"Layer 0 (LLMLayer): ENABLED")
        if LLMLAYER_CONFIG["api_key"] != "llm_xxxxxxxxxxxxx":
            print(f"  ✅ API Key configured")
        else:
            print(f"  ⚠️  API Key not set - will fallback to fact checker")
    
    if FACT_CHECKER_CONFIG.get('model'):
        print(f"Layer 1 (Fact Checker): {FACT_CHECKER_CONFIG['model']}")
    else:
        print(f"Layer 1 (Fact Checker): DISABLED")
    
    print(f"Layer 2 (Thinking Model): {THINKING_MODEL_CONFIG['model']}")
    print(f"{'='*80}\n")
    
    print("Choose test mode:")
    print("  1. Test single query (choose from list)")
    print("  2. Test all queries")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    # Create LLM clients and ToolManager
    config = Config()
    
    # Only create fact checker if model is set
    fact_checker_llm = None
    if FACT_CHECKER_CONFIG.get('model'):
        fact_checker_config = config.create_llm_config(
            provider=FACT_CHECKER_CONFIG['provider'],
            model=FACT_CHECKER_CONFIG['model'],
            max_tokens=FACT_CHECKER_CONFIG['max_tokens']
        )
        fact_checker_llm = LLMClient(fact_checker_config)
    
    thinking_config = config.create_llm_config(
        provider=THINKING_MODEL_CONFIG['provider'],
        model=THINKING_MODEL_CONFIG['model'],
        max_tokens=THINKING_MODEL_CONFIG['max_tokens']
    )
    thinking_llm = LLMClient(thinking_config)
    
    dummy_llm = thinking_llm
    
    tool_manager = ToolManager(
        config=config,
        llm_client=dummy_llm,
        web_model=None,
        use_premium_search=False
    )
    
    try:
        if choice == '1':
            print(f"\n{'='*80}")
            print("Available queries:")
            print(f"{'='*80}\n")
            
            for i, query in enumerate(QUERIES, 1):
                preview = query[:70] + "..." if len(query) > 70 else query
                print(f"  {i}. {preview}")
            
            try:
                query_num = int(input("\nSelect query number: ").strip())
                if 1 <= query_num <= len(QUERIES):
                    selected_query = QUERIES[query_num - 1]
                    await test_single_query(fact_checker_llm, thinking_llm, tool_manager, selected_query, 1, 1)
                else:
                    print("❌ Invalid number")
            except ValueError:
                print("❌ Please enter a valid number")
                
        elif choice == '2':
            success_count = 0
            for i, query in enumerate(QUERIES, 1):
                if await test_single_query(fact_checker_llm, thinking_llm, tool_manager, query, i, len(QUERIES)):
                    success_count += 1
                
                if i < len(QUERIES):
                    print(f"\n{'─'*80}")
                    print("⏸️  Pausing 2 seconds before next query...")
                    await asyncio.sleep(2)
            
            print(f"\n\n{'='*80}")
            print(f"✅ SUMMARY: {success_count}/{len(QUERIES)} queries successful")
            print(f"{'='*80}\n")
        else:
            print("❌ Invalid choice")
            
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(test())
