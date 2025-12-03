"""
Debug test for multi-step Zapier workflow:
1. First query: Plan for Manali trip
2. Second query: Add details to Google Sheets

This tests if the agent correctly:
- Uses Nemotron model (not Maverick) for analysis
- Selects multiple tools when needed (create spreadsheet + add row)
"""

import asyncio
import logging
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def test_manali_trip_workflow():
    """Test the Manali trip planning + Google Sheets workflow."""
    
    print("=" * 80)
    print("MANALI TRIP + GOOGLE SHEETS DEBUG TEST")
    print("=" * 80)
    
    from core.config import Config
    from core.llm_client import LLMClient
    from core.tools import ToolManager
    from core.optimized_agent import OptimizedAgent
    
    config = Config()
    
    # ========================================
    # STEP 1: Load models from .env (like chat.py does)
    # ========================================
    print("\n[STEP 1] Loading models from .env...")
    
    brain_provider = os.getenv('BRAIN_LLM_PROVIDER', 'openrouter')
    brain_model = os.getenv('BRAIN_LLM_MODEL', 'qwen/qwen3-next-80b-a3b-thinking')
    
    heart_provider = os.getenv('HEART_LLM_PROVIDER', 'openrouter')
    heart_model = os.getenv('HEART_LLM_MODEL', 'meta-llama/llama-4-maverick')
    
    router_provider = os.getenv('ROUTER_LLM_PROVIDER', 'openrouter')
    router_model = os.getenv('ROUTER_LLM_MODEL', 'nvidia/llama-3.3-nemotron-super-49b-v1.5')
    
    print(f"   Brain Model: {brain_provider}/{brain_model}")
    print(f"   Heart Model: {heart_provider}/{heart_model}")
    print(f"   Router Model: {router_provider}/{router_model}")
    
    # ========================================
    # STEP 2: Create LLM clients (like chat.py does)
    # ========================================
    print("\n[STEP 2] Creating LLM clients...")
    
    brain_config = config.create_llm_config(brain_provider, brain_model, max_tokens=16000)
    heart_config = config.create_llm_config(heart_provider, heart_model, max_tokens=1000)
    router_config = config.create_llm_config(router_provider, router_model, max_tokens=2000)
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    router_llm = LLMClient(router_config)  # <-- IMPORTANT: Separate router LLM!
    
    print(f"   ✅ Brain LLM: {brain_model}")
    print(f"   ✅ Heart LLM: {heart_model}")
    print(f"   ✅ Router LLM: {router_model}")
    
    # ========================================
    # STEP 3: Initialize Tool Manager + Zapier
    # ========================================
    print("\n[STEP 3] Initializing Tool Manager + Zapier...")
    
    tool_manager = ToolManager(config, brain_llm)
    await tool_manager.initialize_zapier_async()
    
    zapier_tools = tool_manager.get_zapier_tools()
    print(f"   ✅ Zapier tools loaded: {len(zapier_tools)}")
    
    # Show spreadsheet tools
    print("\n   [SPREADSHEET TOOLS]:")
    for tool in zapier_tools:
        if 'sheet' in tool.lower() or 'excel' in tool.lower():
            print(f"      • {tool}")
    
    # ========================================
    # STEP 4: Create OptimizedAgent WITH router_llm
    # ========================================
    print("\n[STEP 4] Creating OptimizedAgent...")
    
    # Initialize language detector if enabled
    language_detector_llm = None
    if config.language_detection_enabled:
        try:
            lang_detect_config = config.create_language_detection_config()
            language_detector_llm = LLMClient(lang_detect_config)
            print(f"   ✅ Language Detector: Enabled")
        except Exception as e:
            print(f"   ⚠️ Language Detector: Failed - {e}")
    
    # Create agent with SEPARATE router_llm (not shared with heart_llm)
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager,
        router_llm=router_llm,  # <-- IMPORTANT: Pass router_llm separately!
        indic_llm=None,
        language_detector_llm=language_detector_llm
    )
    
    print(f"   ✅ Agent initialized with tools: {agent.available_tools}")
    
    # ========================================
    # STEP 5: Check which LLM will be used
    # ========================================
    print("\n[STEP 5] Checking model routing...")
    print(f"   Router LLM (for simple_analysis): {router_model}")
    print(f"   Brain LLM (for comprehensive_analysis): {brain_model}")
    print(f"   Source='whatsapp' → uses simple_analysis → uses Router LLM ({router_model})")
    
    # ========================================
    # QUERY 1: Plan for Manali trip
    # ========================================
    query1 = "Make a plan for 6 person 3 days 2 night budget plan for manali tirp"
    
    print("\n" + "=" * 80)
    print(f"QUERY 1: {query1}")
    print("=" * 80)
    
    chat_history = []
    
    result1 = await agent.process_query(
        query=query1,
        chat_history=chat_history,
        user_id="test_manali_debug",
        source="whatsapp"  # This triggers simple_analysis with router_llm
    )
    
    response1 = result1.get('response', 'NO RESPONSE')
    tools_used1 = result1.get('tools_used', [])
    
    print(f"\n[RESPONSE 1]:\n{response1[:1000]}...")
    print(f"\n[TOOLS USED]: {tools_used1}")
    
    # Update chat history
    chat_history.append({"role": "user", "content": query1})
    chat_history.append({"role": "assistant", "content": response1})
    
    # ========================================
    # QUERY 2: Add to Google Sheets
    # ========================================
    query2 = "Okay add these details in google sheets and named that sheet as 'Manali trips planning'okay?"
    
    print("\n" + "=" * 80)
    print(f"QUERY 2: {query2}")
    print("=" * 80)
    
    result2 = await agent.process_query(
        query=query2,
        chat_history=chat_history,
        user_id="test_manali_debug",
        source="whatsapp"
    )
    
    response2 = result2.get('response', 'NO RESPONSE')
    tools_used2 = result2.get('tools_used', [])
    tool_results2 = result2.get('tool_results', {})
    
    print(f"\n[RESPONSE 2]:\n{response2[:1000]}...")
    print(f"\n[TOOLS USED]: {tools_used2}")
    print(f"\n[TOOL RESULTS]:")
    for tool_name, tool_result in tool_results2.items():
        if isinstance(tool_result, dict):
            success = tool_result.get('success', False)
            error = tool_result.get('error')
            status = "✅" if success else "❌"
            print(f"   {status} {tool_name}: {'Success' if success else error}")
    
    # ========================================
    # ANALYSIS: Did it select correct tools?
    # ========================================
    print("\n" + "=" * 80)
    print("ANALYSIS: Tool Selection for Query 2")
    print("=" * 80)
    
    expected_tools = ['zapier_google_sheets_create_spreadsheet_2', 'zapier_google_sheets_create_spreadsheet_row']
    
    print(f"\n   Expected tools: {expected_tools}")
    print(f"   Actual tools:   {tools_used2}")
    
    if 'zapier_google_sheets_create_spreadsheet_2' in tools_used2:
        print("   ✅ Create Spreadsheet tool selected")
    else:
        print("   ❌ Create Spreadsheet tool NOT selected")
    
    if 'zapier_google_sheets_create_spreadsheet_row' in tools_used2:
        print("   ✅ Add Row tool selected")
    else:
        print("   ❌ Add Row tool NOT selected")
    
    if len(tools_used2) >= 2:
        print("\n   ✅ PASS: Multiple tools selected for multi-step task")
    else:
        print("\n   ❌ FAIL: Only 1 tool selected - LLM didn't understand multi-step workflow")
    
    # ========================================
    # Cleanup
    # ========================================
    print("\n[CLEANUP]")
    await brain_llm.close_session()
    await heart_llm.close_session()
    await router_llm.close_session()
    if language_detector_llm:
        await language_detector_llm.close_session()
    if tool_manager._zapier_manager:
        await tool_manager._zapier_manager.close()
    
    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_manali_trip_workflow())
