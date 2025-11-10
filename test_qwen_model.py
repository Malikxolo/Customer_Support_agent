"""
Test Qwen Thinking Model - Raw Output Analysis
Tests how qwen/qwen3-next-80b-a3b-thinking responds to prompts
"""

import asyncio
import os
from dotenv import load_dotenv
from core.llm_client import LLMClient
from core.config import LLMConfig

load_dotenv()

async def test_qwen_simple():
    """Test 1: Simple question to see basic output format"""
    print("\n" + "="*80)
    print("TEST 1: Simple Question")
    print("="*80)
    
    config = LLMConfig(
        provider="openrouter",
        model="qwen/qwen3-next-80b-a3b-thinking",
        api_key=os.getenv('OPENROUTER_API_KEY'),
        max_tokens=2000,
        base_url="https://openrouter.ai/api/v1"
    )
    
    client = LLMClient(config)
    await client.start_session()
    
    messages = [{"role": "user", "content": "What is 2+2? Explain your reasoning."}]
    
    response = await client.generate(
        messages=messages,
        temperature=0.1,
        system_prompt="You are a helpful assistant."
    )
    
    print(f"\n📊 Response Length: {len(response)} chars")
    print(f"\n📝 Full Response:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    await client.close_session()
    return response


async def test_qwen_json_request():
    """Test 2: Request JSON output to see how model handles it"""
    print("\n" + "="*80)
    print("TEST 2: JSON Output Request")
    print("="*80)
    
    config = LLMConfig(
        provider="openrouter",
        model="qwen/qwen3-next-80b-a3b-thinking",
        api_key=os.getenv('OPENROUTER_API_KEY'),
        max_tokens=2000,
        base_url="https://openrouter.ai/api/v1"
    )
    
    client = LLMClient(config)
    await client.start_session()
    
    prompt = """Analyze this query: "Create a pitch deck for investors"

Return your analysis as JSON with this structure:
{
    "intent": "what user wants",
    "complexity": "simple or complex",
    "tools_needed": ["list of tools"]
}"""
    
    messages = [{"role": "user", "content": prompt}]
    
    response = await client.generate(
        messages=messages,
        temperature=0.1,
        system_prompt="You are an analyst. Return valid JSON."
    )
    
    print(f"\n📊 Response Length: {len(response)} chars")
    print(f"\n📝 Full Response:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    # Analyze structure
    print(f"\n🔍 Analysis:")
    print(f"   Starts with '{{': {response.strip().startswith('{')}")
    print(f"   Contains '{{': {'{' in response}")
    print(f"   Contains thinking markers: {'<think>' in response.lower() or 'reasoning:' in response.lower()}")
    
    # Try to find JSON
    if '{' in response:
        first_brace = response.find('{')
        print(f"   First '{{' at position: {first_brace}")
        print(f"   Text before first brace: {response[:first_brace][:100]}...")
    
    await client.close_session()
    return response


async def test_qwen_with_thinking_allowance():
    """Test 3: Explicitly allow thinking, then request JSON"""
    print("\n" + "="*80)
    print("TEST 3: Allow Thinking + JSON Request")
    print("="*80)
    
    config = LLMConfig(
        provider="openrouter",
        model="qwen/qwen3-next-80b-a3b-thinking",
        api_key=os.getenv('OPENROUTER_API_KEY'),
        max_tokens=2000,
        base_url="https://openrouter.ai/api/v1"
    )
    
    client = LLMClient(config)
    await client.start_session()
    
    prompt = """Analyze this query: "Create a pitch deck for investors"

You can think through your reasoning naturally, but MUST end with JSON.

Structure:
1. Think through the analysis (your reasoning)
2. Then provide JSON in this format:

{
    "intent": "what user wants",
    "complexity": "simple or complex",
    "tools_needed": ["list of tools"]
}"""
    
    messages = [{"role": "user", "content": prompt}]
    
    response = await client.generate(
        messages=messages,
        temperature=0.1,
        system_prompt="You can think naturally, then provide valid JSON."
    )
    
    print(f"\n📊 Response Length: {len(response)} chars")
    print(f"\n📝 Full Response:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    # Analyze structure
    print(f"\n🔍 Analysis:")
    print(f"   Starts with '{{': {response.strip().startswith('{')}")
    print(f"   Contains '{{': {'{' in response}")
    
    if '{' in response:
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        print(f"   First '{{' at position: {first_brace}")
        print(f"   Last '}}' at position: {last_brace}")
        
        if first_brace > 0:
            print(f"\n   📄 Reasoning prefix (first 200 chars):")
            print(f"   {response[:first_brace][:200]}")
        
        if first_brace >= 0 and last_brace > first_brace:
            json_candidate = response[first_brace:last_brace+1]
            print(f"\n   ✅ Extracted JSON candidate ({len(json_candidate)} chars):")
            print(f"   {json_candidate[:300]}...")
    
    await client.close_session()
    return response


async def test_qwen_complex_query():
    """Test 4: Complex query similar to actual usage"""
    print("\n" + "="*80)
    print("TEST 4: Complex Query (Similar to Production)")
    print("="*80)
    
    config = LLMConfig(
        provider="openrouter",
        model="qwen/qwen3-next-80b-a3b-thinking",
        api_key=os.getenv('OPENROUTER_API_KEY'),
        max_tokens=3000,
        base_url="https://openrouter.ai/api/v1"
    )
    
    client = LLMClient(config)
    await client.start_session()
    
    prompt = """USER QUERY: "Create investor pitch deck for Mochan-D with market data and examples"

Analyze this query and return JSON:

You can think naturally about:
- What does the user actually want?
- What information is missing that would help?
- How many searches would be needed?

Then provide your analysis in this JSON format:
{
    "semantic_intent": "clear description",
    "tools_to_use": ["rag", "web_search", etc],
    "expansion_reasoning": "why you chose these tools",
    "enhanced_queries": {
        "rag_0": "query for rag",
        "web_search_0": "query for web"
    }
}"""
    
    messages = [{"role": "user", "content": prompt}]
    
    response = await client.generate(
        messages=messages,
        temperature=0.1,
        system_prompt="You can think naturally, then provide your final analysis as valid JSON."
    )
    
    print(f"\n📊 Response Length: {len(response)} chars")
    print(f"\n📝 Full Response:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    # Try JSON extraction
    if '{' in response:
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        
        print(f"\n🔍 JSON Extraction Analysis:")
        print(f"   Has reasoning prefix: {first_brace > 100}")
        print(f"   Prefix length: {first_brace} chars")
        print(f"   JSON length: {last_brace - first_brace + 1} chars")
        
        if first_brace >= 0 and last_brace > first_brace:
            json_candidate = response[first_brace:last_brace+1]
            
            # Try to parse
            import json
            try:
                parsed = json.loads(json_candidate)
                print(f"\n   ✅ Successfully parsed JSON!")
                print(f"   Keys found: {list(parsed.keys())}")
            except json.JSONDecodeError as e:
                print(f"\n   ❌ JSON parse failed: {e}")
                print(f"   First 200 chars of candidate: {json_candidate[:200]}")
    
    await client.close_session()
    return response


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 QWEN THINKING MODEL TESTING SUITE")
    print("Model: qwen/qwen3-next-80b-a3b-thinking")
    print("="*80)
    
    try:
        # Test 1: Simple
        await test_qwen_simple()
        await asyncio.sleep(1)
        
        # Test 2: JSON request
        await test_qwen_json_request()
        await asyncio.sleep(1)
        
        # Test 3: Thinking + JSON
        await test_qwen_with_thinking_allowance()
        await asyncio.sleep(1)
        
        # Test 4: Complex query
        await test_qwen_complex_query()
        
        print("\n" + "="*80)
        print("✅ All tests completed!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
