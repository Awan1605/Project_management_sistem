"""List available Gemini models for the configured API key."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arviga.settings')

import django
django.setup()

from google import genai
from django.conf import settings

print("=" * 60)
print("CHECKING AVAILABLE GEMINI MODELS")
print("=" * 60)

try:
    # Create client with v1 API
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options={'api_version': 'v1'}
    )
    
    print("\n✅ Client created successfully (API v1)")
    print(f"API Key: {settings.GEMINI_API_KEY[:15]}...")
    
    # List all available models
    print("\n📋 Available Models:")
    print("-" * 60)
    
    models = client.models.list()
    
    if not models:
        print("❌ No models found!")
    else:
        for i, model in enumerate(models, 1):
            # Check if model supports generateContent
            supported_methods = getattr(model, 'supported_generation_methods', [])
            has_generate = 'generateContent' in supported_methods
            
            status = "✅" if has_generate else "⚠️ "
            print(f"{i}. {status} {model.name}")
            
            if has_generate:
                print(f"   - Supports: generateContent ✅")
            
            print()
    
    # Try to find a working model
    print("\n🔍 Testing models for generateContent support...")
    print("-" * 60)
    
    working_models = []
    
    for model in models:
        model_name = model.name.replace('models/', '')
        
        try:
            # Quick test
            response = client.models.generate_content(
                model=model_name,
                contents="Hi"
            )
            
            if response and response.text:
                print(f"✅ WORKING: {model_name}")
                working_models.append(model_name)
                
        except Exception as e:
            error_msg = str(e)
            if 'NOT_FOUND' in error_msg:
                print(f"❌ NOT_FOUND: {model_name}")
            elif 'QUOTA' in error_msg.upper():
                print(f"⚠️  QUOTA EXCEEDED: {model_name}")
            else:
                print(f"⚠️  ERROR: {model_name} - {error_msg[:50]}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    
    if working_models:
        print(f"\n✅ Use one of these models:")
        for model in working_models[:3]:
            print(f"   - {model}")
        
        print(f"\nUpdate ai_services.py with:")
        print(f"   self.model_name = '{working_models[0]}'")
    else:
        print("\n❌ No working models found!")
        print("Possible issues:")
        print("   1. API key invalid")
        print("   2. All quotas exceeded")
        print("   3. API version mismatch")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
