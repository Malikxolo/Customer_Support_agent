"""
Debug PostgreSQL Workflow - Test bulk insert with realistic customer data
NO explicit instruction - testing raw LLM behavior
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.config import Config
from core.llm_client import LLMClient
from core.tools import ToolManager
from core.optimized_agent import OptimizedAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[logging.StreamHandler()]
)


async def run_postgresql_tests():
    """Test bulk insert with realistic customer data - NO explicit instruction"""
    
    print("\n" + "="*80)
    print("POSTGRESQL BULK INSERT TEST - REALISTIC CUSTOMER DATA")
    print("="*80)
    print("Testing if LLM selects tool N times WITHOUT explicit instruction")
    print("="*80)
    
    # ========================================================================
    # INITIALIZE AGENT
    # ========================================================================
    
    config = Config()
    
    brain_provider = os.getenv('BRAIN_LLM_PROVIDER', 'openrouter')
    brain_model = os.getenv('BRAIN_LLM_MODEL', 'qwen/qwen3-next-80b-a3b-thinking')
    
    heart_provider = os.getenv('HEART_LLM_PROVIDER', 'openrouter')
    heart_model = os.getenv('HEART_LLM_MODEL', 'meta-llama/llama-4-maverick')
    
    router_provider = os.getenv('ROUTER_LLM_PROVIDER', 'openrouter')
    router_model = os.getenv('ROUTER_LLM_MODEL', 'nvidia/llama-3.3-nemotron-super-49b-v1.5')
    
    print(f"\nModels: Router={router_model.split('/')[-1]}")
    
    brain_config = config.create_llm_config(brain_provider, brain_model, max_tokens=16000)
    heart_config = config.create_llm_config(heart_provider, heart_model, max_tokens=1000)
    router_config = config.create_llm_config(router_provider, router_model, max_tokens=2000)
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    router_llm = LLMClient(router_config)
    
    tool_manager = ToolManager(config, brain_llm)
    await tool_manager.initialize_zapier_async()
    
    # Initialize language detector if enabled
    language_detector_llm = None
    if config.language_detection_enabled:
        try:
            lang_detect_config = config.create_language_detection_config()
            language_detector_llm = LLMClient(lang_detect_config)
        except:
            pass
    
    # Create agent
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager,
        router_llm=router_llm,
        indic_llm=None,
        language_detector_llm=language_detector_llm
    )
    
    # =========================================================================
    # TEST: Bulk insert with realistic customer data (NO explicit instruction)
    # =========================================================================
    
    # Realistic customer data - similar to what failed before
    # NO "IMPORTANT" instruction about single-row limitation
    # Using timestamp to avoid cache hit
    timestamp = datetime.now().strftime("%H%M%S")
    test_query = f"""Add these 5 customers to the PostgreSQL table 'playing_with_neon' (request {timestamp}):

1. name='Rahul Sharma', value=1500.00
2. name='Priya Patel', value=2300.50
3. name='Amit Kumar', value=890.75
4. name='Sneha Gupta', value=3200.00
5. name='Vikram Singh', value=1750.25

Insert all of them into the database."""

    print("\n[TEST QUERY - NO EXPLICIT INSTRUCTION ABOUT SINGLE-ROW]:")
    print("-" * 60)
    print(test_query)
    print("-" * 60)
    
    print("\n" + "=" * 80)
    print("RUNNING TEST...")
    print("=" * 80)
    print("Expected: LLM should select postgresql_new_row 5 TIMES")
    print("If it selects only 1 time, that's the BUG!")
    print("-" * 80)
    
    try:
        response = await agent.process_query(
            query=test_query,
            user_id="customer_bulk_test",
            chat_history=[],
            source="whatsapp"
        )
        
        tools_used = response.get("tools_used", [])
        
        # Count how many times postgresql_new_row was selected
        postgresql_new_row_count = sum(1 for t in tools_used if 'new_row' in t.lower())
        
        print(f"\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)
        print(f"   Tools selected: {len(tools_used)}")
        print(f"   Tools list: {tools_used}")
        print(f"   postgresql_new_row calls: {postgresql_new_row_count}")
        
        if postgresql_new_row_count == 5:
            print(f"\n   ✅ SUCCESS: LLM correctly selected tool 5 times!")
        elif postgresql_new_row_count == 1:
            print(f"\n   ❌ BUG CONFIRMED: LLM selected tool only ONCE for 5 customers!")
            print(f"   This is the bug - LLM doesn't understand single-row limitation.")
        else:
            print(f"\n   ⚠️ UNEXPECTED: Got {postgresql_new_row_count} tool calls")
        
        print(f"\n[AGENT RESPONSE]:")
        print("-" * 60)
        print(response.get('response', 'No response'))
        print("-" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_postgresql_tests())
