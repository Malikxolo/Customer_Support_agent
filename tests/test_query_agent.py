"""
Working MongoDB Query Agent Test
=================================

This test uses proper connection and creates persistent data.
Database: query_agent_db
Collection: inventory

DOES NOT DELETE DATA - Check your MongoDB Atlas to verify!
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from core.mcp.mongodb import MongoDBMCPClient
from core.mcp.query_agent import QueryAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_working_flow():
    """Test with proper connection flow"""
    
    print("\n" + "="*70)
    print("🧪 MONGODB QUERY AGENT - WORKING TEST")
    print("="*70 + "\n")
    
    load_dotenv()
    
    if not os.getenv("MONGODB_MCP_CONNECTION_STRING"):
        print("❌ MONGODB_MCP_CONNECTION_STRING not set")
        return
    
    # Connect with fixed mongodb client
    print("📦 Connecting to MongoDB...")
    mongodb_client = MongoDBMCPClient()
    
    try:
        connected = await mongodb_client.connect()
        if not connected:
            print("❌ Connection failed")
            return
        
        print("✅ Connected to MongoDB\n")
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    # Initialize Query Agent
    print("🤖 Initializing Query Agent...")
    query_agent = QueryAgent()
    tools_prompt = mongodb_client.get_tools_prompt()
    print(f"✅ Query Agent ready\n")
    
    # Database and collection for this test
    DB_NAME = "query_agent_db"
    COLLECTION = "inventory"
    
    print("="*70)
    print(f"📊 Test Database: {DB_NAME}")
    print(f"📊 Test Collection: {COLLECTION}")
    print("="*70 + "\n")
    
    # =================================================================
    # TEST 1: Add products to inventory
    # =================================================================
    print("📌 TEST 1: Add products to inventory")
    print("-" * 70)
    
    products = [
        "laptop",
        "mouse",
        "keyboard"
    ]
    
    for product in products:
        instruction = f"Add {product} to {COLLECTION} collection in {DB_NAME} database"
        print(f"\n💬 \"{instruction}\"")
        
        result = await query_agent.execute(
            tools_prompt=tools_prompt,
            instruction=instruction,
            mcp_client=mongodb_client
        )
        
        if result.success:
            print(f"   ✅ Added {product}")
            print(f"   ID: {result.result}")
        else:
            print(f"   ❌ Failed: {result.error}")
        
        await asyncio.sleep(0.5)
    
    # =================================================================
    # TEST 2: Count inventory items
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 2: Count inventory items")
    print("-" * 70)
    
    instruction = f"How many items are in {COLLECTION} collection in {DB_NAME}?"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Result: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 3: Find all items
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 3: Find all items in inventory")
    print("-" * 70)
    
    instruction = f"Show me all items in {COLLECTION} collection from {DB_NAME}"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Found items:")
        print(f"   {result.result[:500]}...")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 4: Find specific item
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 4: Find laptop in inventory")
    print("-" * 70)
    
    instruction = f"Find laptop in {COLLECTION} collection in {DB_NAME}"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Found: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 5: Update item
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 5: Update laptop with price")
    print("-" * 70)
    
    instruction = f"In {DB_NAME}, update laptop in {COLLECTION} to set price as 1200"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Updated: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 6: Verify update
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 6: Verify laptop has price")
    print("-" * 70)
    
    instruction = f"Find laptop in {COLLECTION} in {DB_NAME} and show its price"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Result: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 7: Add item with multiple fields
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 7: Add item with multiple fields")
    print("-" * 70)
    
    instruction = f"Add monitor to {COLLECTION} in {DB_NAME} with price 300 and brand Dell"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Added: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 8: List all collections
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 8: List all collections in database")
    print("-" * 70)
    
    instruction = f"Show me all collections in {DB_NAME}"
    print(f"\n💬 \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ Collections: {result.result}")
    else:
        print(f"   ❌ Failed: {result.error}")
    
    # =================================================================
    # TEST 9: Clarification test
    # =================================================================
    print("\n" + "="*70)
    print("📌 TEST 9: Test clarification (missing database)")
    print("-" * 70)
    
    instruction = f"Add tablet to {COLLECTION}"  # Missing database!
    print(f"\n💬 \"{instruction}\"")
    print("   (Database missing - should ask for clarification)")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.needs_clarification:
        print(f"   ✅ Correctly asked: {result.clarification_message}")
    else:
        print(f"   ⚠️  Did not ask for clarification")
        if result.success:
            print(f"   Result: {result.result}")
    
    # =================================================================
    # Final Summary
    # =================================================================
    print("\n" + "="*70)
    print("📊 TEST COMPLETE")
    print("="*70)
    
    print(f"\n✅ All operations completed!")
    print(f"\n🔍 CHECK YOUR MONGODB ATLAS:")
    print(f"   Database: {DB_NAME}")
    print(f"   Collection: {COLLECTION}")
    print(f"\n   You should see:")
    print(f"   - laptop (with price: 1200)")
    print(f"   - mouse")
    print(f"   - keyboard")
    print(f"   - monitor (with price: 300, brand: Dell)")
    
    print(f"\n💾 Data is PERSISTENT - not deleted!")
    print(f"   Go to MongoDB Atlas → Browse Collections → {DB_NAME} → {COLLECTION}")
    
    # Stats
    stats = mongodb_client.get_stats()
    print(f"\n📈 MongoDB Client Stats:")
    print(f"   Total calls: {stats['calls']}")
    print(f"   Successes: {stats['successes']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    
    await mongodb_client.disconnect()
    print("\n✅ Disconnected")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║           MONGODB QUERY AGENT - WORKING TEST                    ║
║                                                                  ║
║  Creates: query_agent_db → inventory collection                ║
║  Adds: laptop, mouse, keyboard, monitor                         ║
║  Does NOT delete - verify in MongoDB Atlas!                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(test_working_flow())