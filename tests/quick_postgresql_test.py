"""
Quick PostgreSQL Test - Testing if table name in query works
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.config import Config
from core.llm_client import LLMClient
from core.tools import ToolManager
from core.optimized_agent import OptimizedAgent


async def quick_test():
    """Quick test with explicit table name"""
    
    print("\n" + "="*60)
    print("QUICK POSTGRESQL TEST - Table Name in Query")
    print("="*60)
    
    config = Config()
    
    # Load models
    brain_config = config.create_llm_config(
        os.getenv('BRAIN_LLM_PROVIDER', 'openrouter'),
        os.getenv('BRAIN_LLM_MODEL', 'qwen/qwen3-next-80b-a3b-thinking'),
        max_tokens=16000
    )
    heart_config = config.create_llm_config(
        os.getenv('HEART_LLM_PROVIDER', 'openrouter'),
        os.getenv('HEART_LLM_MODEL', 'meta-llama/llama-4-maverick'),
        max_tokens=1000
    )
    router_config = config.create_llm_config(
        os.getenv('ROUTER_LLM_PROVIDER', 'openrouter'),
        os.getenv('ROUTER_LLM_MODEL', 'nvidia/llama-3.3-nemotron-super-49b-v1.5'),
        max_tokens=2000
    )
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    router_llm = LLMClient(router_config)
    
    # Initialize tools
    tool_manager = ToolManager(config, brain_llm)
    await tool_manager.initialize_zapier_async()
    
    print(f"\n✅ Zapier tools loaded: {len(tool_manager.get_zapier_tools())}")
    
    # Language detector
    language_detector_llm = None
    if config.language_detection_enabled:
        lang_config = config.create_language_detection_config()
        language_detector_llm = LLMClient(lang_config)
    
    # Create agent
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager,
        router_llm=router_llm,
        indic_llm=None,
        language_detector_llm=language_detector_llm
    )
    
    # ================================================================
    # TEST: Insert with EXPLICIT table name
    # ================================================================
    
    test_query = """Find the row in PostgreSQL database table 'playing_with_neon' where name is 'test_from_agent'.

Use the table named 'playing_with_neon' in the neondb database."""
    
    print("\n" + "="*60)
    print("TEST: Insert with explicit table name")
    print("="*60)
    print(f"\nQUERY:\n{test_query}")
    print("-"*60)
    
    try:
        response = await agent.process_query(
            query=test_query,
            user_id="quick_test",
            chat_history=[],
            source="whatsapp"
        )
        
        print(f"\n✅ RESPONSE:")
        print(response.get("response", "No response"))
        
        print(f"\n🔧 TOOLS USED: {response.get('tools_used', [])}")
        
        print(f"\n📊 TOOL RESULTS:")
        for tool_name, result in response.get("tool_results", {}).items():
            status = "✅ SUCCESS" if result.get("success") else "❌ ERROR"
            print(f"   {status}: {tool_name}")
            if result.get("error"):
                print(f"      Error: {result.get('error')}")
            if result.get("data"):
                print(f"      Data: {str(result.get('data'))[:200]}")
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    await agent.close()
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(quick_test())
