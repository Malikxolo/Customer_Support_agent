"""
Test script for ImageAnalysisTool
Place test images in the 'test_images' folder and run this script.

Usage:
    python test_image_analysis.py
    python test_image_analysis.py --image path/to/image.jpg
    python test_image_analysis.py --url https://example.com/image.jpg
"""

import asyncio
import os
import sys
import base64
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from core.cs_tools import ImageAnalysisTool

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_image_as_base64(image_path: str) -> str:
    """Load a local image file and convert to base64 data URL"""
    path = Path(image_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Detect media type from extension
    ext = path.suffix.lower()
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    media_type = media_types.get(ext, 'image/jpeg')
    
    with open(path, 'rb') as f:
        image_data = f.read()
    
    encoded = base64.b64encode(image_data).decode('utf-8')
    return f"data:{media_type};base64,{encoded}"


async def test_single_image(tool: ImageAnalysisTool, image_path: str, 
                           customer_query: str = None, product_name: str = None):
    """Test analysis on a single image"""
    print(f"\n{'='*60}")
    print(f"📷 Testing image: {image_path}")
    print(f"{'='*60}")
    
    # Load image
    try:
        image_base64 = load_image_as_base64(image_path)
        print(f"✅ Image loaded ({len(image_base64)} bytes encoded)")
    except Exception as e:
        print(f"❌ Failed to load image: {e}")
        return None
    
    # Run analysis
    print(f"\n🔍 Analyzing with model: {tool.vision_model}")
    if customer_query:
        print(f"   Customer query: {customer_query}")
    if product_name:
        print(f"   Product name: {product_name}")
    
    result = await tool.execute(
        image_base64=image_base64,
        query=customer_query,
        product_name=product_name
    )
    
    # Display results
    print(f"\n📊 Results:")
    print(f"   Success: {result.get('success')}")
    
    if result.get('success'):
        analysis = result.get('analysis', {})
        ai_detection = result.get('ai_detection', {})
        
        print(f"\n   🤖 AI Detection:")
        print(f"   ├── Is AI Generated: {ai_detection.get('is_ai_generated', 'N/A')}")
        print(f"   ├── Confidence: {ai_detection.get('confidence', 0.0):.2f}")
        print(f"   ├── Signals: {', '.join(ai_detection.get('signals', []))}")
        print(f"   │")
        print(f"   🔎 Vision Analysis:")
        print(f"   ├── Damage Detected: {analysis.get('damage_detected')}")
        print(f"   ├── Damage Type: {analysis.get('damage_type')}")
        print(f"   ├── Severity: {analysis.get('severity')}")
        print(f"   ├── Confidence: {analysis.get('confidence', 0.0):.2f}")
        print(f"   ├── Recommendation: {analysis.get('recommendation')}")
        print(f"   ├── Matches Claim: {analysis.get('matches_customer_claim')}")
        print(f"   │")
        print(f"   ├── Description:")
        desc = analysis.get('description', 'N/A')
        for line in desc.split('. '):
            print(f"   │   {line}")
        print(f"   │")
        print(f"   └── Reasoning:")
        reasoning = analysis.get('reasoning', 'N/A')
        for line in reasoning.split('. '):
            print(f"       {line}")
    else:
        print(f"   ❌ Error: {result.get('error')}")
    
    return result


async def test_with_url(tool: ImageAnalysisTool, image_url: str,
                       customer_query: str = None):
    """Test analysis with an image URL"""
    print(f"\n{'='*60}")
    print(f"🌐 Testing URL: {image_url[:50]}...")
    print(f"{'='*60}")
    
    print(f"\n🔍 Analyzing with model: {tool.vision_model}")
    
    result = await tool.execute(
        image_url=image_url,
        query=customer_query
    )
    
    print(f"\n📊 Results:")
    print(f"   Success: {result.get('success')}")
    
    if result.get('success'):
        analysis = result.get('analysis', {})
        print(f"\n   🔎 Analysis:")
        print(json.dumps(analysis, indent=4))
    else:
        print(f"   ❌ Error: {result.get('error')}")
    
    return result


async def test_all_images_in_folder(tool: ImageAnalysisTool, folder_path: str):
    """Test all images in the test_images folder"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Folder not found: {folder_path}")
        print(f"   Creating folder...")
        folder.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ Created: {folder_path}")
        print(f"\n📁 Place test images in this folder and run again.")
        return
    
    # Find all images
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in folder.iterdir() if f.suffix.lower() in image_extensions]
    
    if not images:
        print(f"\n📁 No images found in: {folder_path}")
        print(f"   Supported formats: {', '.join(image_extensions)}")
        print(f"\n   Example test images to add:")
        print(f"   - damaged_phone.jpg (broken screen)")
        print(f"   - wrong_item.png (different product than ordered)")
        print(f"   - good_product.jpg (product in perfect condition)")
        return
    
    print(f"\n📁 Found {len(images)} images in {folder_path}")
    
    results = []
    for image_path in images:
        # Use filename as context hint
        filename = image_path.stem.lower()
        
        # Auto-detect query from filename
        query = None
        if 'damaged' in filename or 'broken' in filename:
            query = "The product arrived damaged"
        elif 'wrong' in filename:
            query = "I received the wrong item"
        elif 'defect' in filename:
            query = "The product has a defect"
        
        result = await test_single_image(tool, str(image_path), customer_query=query)
        results.append({
            'image': image_path.name,
            'result': result
        })
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY")
    print(f"{'='*60}")
    
    for r in results:
        status = "✅" if r['result'] and r['result'].get('success') else "❌"
        analysis = r['result'].get('analysis', {}) if r['result'] else {}
        ai_detection = r['result'].get('ai_detection', {}) if r['result'] else {}
        damage = analysis.get('damage_detected', 'N/A')
        severity = analysis.get('severity', 'N/A')
        recommendation = analysis.get('recommendation', 'N/A')
        ai_generated = ai_detection.get('is_ai_generated', 'N/A')
        print(f"{status} {r['image']}: damage={damage}, severity={severity}, rec={recommendation}, ai={ai_generated}")


async def main():
    parser = argparse.ArgumentParser(description='Test ImageAnalysisTool')
    parser.add_argument('--image', type=str, help='Path to a specific image to test')
    parser.add_argument('--url', type=str, help='URL of an image to test')
    parser.add_argument('--query', type=str, help='Customer complaint/query')
    parser.add_argument('--product', type=str, help='Expected product name')
    parser.add_argument('--folder', type=str, default='test_images', help='Folder with test images')
    args = parser.parse_args()
    
    # Show config
    print("\n🔧 Configuration:")
    print(f"   VISION_MODEL: {os.getenv('VISION_MODEL', 'openai/gpt-4o')} (default)")
    print(f"   OPENROUTER_API_KEY: {'✅ Set' if os.getenv('OPENROUTER_API_KEY') else '❌ Not set'}")
    
    # Initialize tool
    tool = ImageAnalysisTool()
    
    try:
        if args.url:
            # Test with URL
            await test_with_url(tool, args.url, args.query)
        elif args.image:
            # Test specific image
            await test_single_image(tool, args.image, args.query, args.product)
        else:
            # Test all images in folder
            folder_path = os.path.join(os.path.dirname(__file__), args.folder)
            await test_all_images_in_folder(tool, folder_path)
    finally:
        await tool.close()
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
