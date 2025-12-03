"""
Interactive Debug test for Zapier tool execution and response handling.

Run this file and type queries interactively to test the agent.
Type 'quit' or 'exit' to stop.
Type 'tools' to see available tools.
Type 'clear' to clear chat history.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def interactive_zapier_test():
    """Interactive test for Zapier scenarios."""
    print("=" * 70)
    print("INTERACTIVE ZAPIER DEBUG")
    print("=" * 70)
    print("Commands:")
    print("  - Type your query to test")
    print("  - 'tools' - Show available tools with descriptions")
    print("  - 'clear' - Clear chat history")
    print("  - 'quit' or 'exit' - Exit")
    print("=" * 70)
    
    from core.config import Config
    from core.llm_client import LLMClient
    from core.tools import ToolManager
    from core.optimized_agent import OptimizedAgent
    from api.global_config import settings
    
    config = Config()
    providers = config.get_available_providers()
    
    if "openrouter" not in providers:
        print("❌ OpenRouter not configured")
        return
    
    # Use models from .env
    brain_model = os.getenv("BRAIN_LLM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    heart_model = os.getenv("HEART_LLM_MODEL", "meta-llama/llama-4-maverick")
    
    print(f"\n[CONFIG] Brain Model: {brain_model}")
    print(f"[CONFIG] Heart Model: {heart_model}")
    
    brain_config = config.create_llm_config("openrouter", brain_model)
    heart_config = config.create_llm_config("openrouter", heart_model)
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    
    # Initialize Indic LLM for Sarvam (Indian language responses)
    indic_llm = None
    if settings.indic_provider and settings.indic_model:
        try:
            indic_model_config = config.create_llm_config(
                provider=settings.indic_provider,
                model=settings.indic_model,
                max_tokens=1000
            )
            indic_llm = LLMClient(indic_model_config)
            print(f"[CONFIG] Indic LLM: {settings.indic_provider}/{settings.indic_model} ✅")
        except Exception as e:
            print(f"[CONFIG] Indic LLM initialization failed: {e}")
            indic_llm = None
    
    # Initialize language detector if enabled
    language_detector_llm = None
    if config.language_detection_enabled:
        try:
            lang_detect_config = config.create_language_detection_config()
            language_detector_llm = LLMClient(lang_detect_config)
            print(f"[CONFIG] Language Detector: {config.language_detection_provider}/{config.language_detection_model} ✅")
        except Exception as e:
            print(f"[CONFIG] Language detection initialization failed: {e}")
            language_detector_llm = None
    
    tool_manager = ToolManager(config, heart_llm)
    await tool_manager.initialize_zapier_async()
    
    # Initialize agent with language detection components
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager,
        router_llm=None,
        indic_llm=indic_llm,
        language_detector_llm=language_detector_llm
    )
    
    print(f"\n[TOOLS] Available Tools: {agent.available_tools}")
    
    # Show Zapier tools with descriptions
    zapier_tools = tool_manager.get_zapier_tools()
    print(f"\n[ZAPIER] {len(zapier_tools)} Zapier Tools Available:")
    if tool_manager._zapier_manager:
        for tool_name in zapier_tools:
            schema = tool_manager._zapier_manager._tool_schemas.get(tool_name, {})
            desc = schema.get('description', 'No description')[:80]
            print(f"   • {tool_name}: {desc}...")
    
    # Chat history for conversation context
    chat_history = []
    
    print("\n" + "=" * 70)
    print("Ready! Type your query below:")
    print("=" * 70 + "\n")
    
    while True:
        try:
            # Get user input
            user_input = input("\n🧑 YOU: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Exiting...")
                break
            
            if user_input.lower() == 'clear':
                chat_history = []
                print("✅ Chat history cleared!")
                continue
            
            if user_input.lower() == 'tools':
                print("\n📋 AVAILABLE TOOLS WITH DESCRIPTIONS:")
                print("-" * 60)
                if tool_manager._zapier_manager:
                    for tool_name in zapier_tools:
                        schema = tool_manager._zapier_manager._tool_schemas.get(tool_name, {})
                        desc = schema.get('description', 'No description')
                        app = schema.get('app', 'Unknown')
                        action = schema.get('action', 'Unknown')
                        print(f"\n🔧 {tool_name}")
                        print(f"   App: {app}")
                        print(f"   Action: {action}")
                        print(f"   Description: {desc}")
                print("-" * 60)
                continue
            
            if user_input.lower() == 'history':
                print("\n📜 CHAT HISTORY:")
                for i, msg in enumerate(chat_history):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:100]
                    print(f"   [{i+1}] {role}: {content}...")
                continue
            
            # Process query
            print("\n⏳ Processing...")
            
            result = await agent.process_query(
                query=user_input,
                chat_history=chat_history,
                user_id="test_debug",
                source="whatsapp"
            )
            
            # Get response
            response = result.get('response', 'NO RESPONSE')
            tools_used = result.get('tools_used', [])
            tool_results = result.get('tool_results', {})
            
            # Print response
            print(f"\n🤖 BOT: {response}")
            
            # Print tool info
            if tools_used:
                print(f"\n   📦 Tools Used: {tools_used}")
                
                for tool_name, tool_result in tool_results.items():
                    if isinstance(tool_result, dict):
                        success = tool_result.get('success', False)
                        error = tool_result.get('error')
                        status = "✅" if success else "❌"
                        print(f"   {status} {tool_name}: {'Success' if success else error}")
            
            # Update chat history
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": response})
            
            # Keep history manageable
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted! Exiting...")
            break
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    # Cleanup
    print("\n[CLEANUP] Cleaning up...")
    await brain_llm.close_session()
    await heart_llm.close_session()
    if indic_llm:
        await indic_llm.close_session()
    if language_detector_llm:
        await language_detector_llm.close_session()
    if tool_manager._zapier_manager:
        await tool_manager._zapier_manager.close()
    
    print("\n" + "=" * 70)
    print("DEBUG SESSION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(interactive_zapier_test())
