import asyncio
import os
from dotenv import load_dotenv
from core.cs_tools import RaiseTicketTool

# Load environment variables
load_dotenv()

async def test_raise_ticket():
    """Test the RaiseTicketTool"""
    
    # Get configuration from environment
    base_url = os.getenv("RAISE_TICKET_BASE_URL")
    business_id = os.getenv("BUSINESS_ID")
    
    if not all([base_url, business_id]):
        print("❌ Missing environment variables. Please set RAISE_TICKET_BASE_URL and BUSINESS_ID in .env")
        return
    
    # Initialize the tool
    tool = RaiseTicketTool(
        base_url=base_url,
        business_id=business_id,
        api_key=None  # No API key needed
    )
    
    try:
        # Test ticket creation
        result = await tool.execute(
            user_id="916306755990",
            subject="Test Issue ",
            description="This is a test ticket created via the API",
            priority="high",
            category="order",
            customerName="Faizan",
            channel="whatsapp"
        )
        
        print("✅ Test Result:")
        print(f"Success: {result.get('success')}")
        print(f"Ticket ID: {result.get('ticket_id')}")
        print(f"Message: {result.get('message')}")
        if result.get('ticket'):
            print(f"Full Ticket Data: {result['ticket']}")
    
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    finally:
        # Clean up
        await tool.close()

if __name__ == "__main__":
    asyncio.run(test_raise_ticket())