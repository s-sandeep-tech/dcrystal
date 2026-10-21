#!/usr/bin/env python3
"""
Diagnostic test script to verify Google Gemini API connectivity.
Can be run on the host or inside the Docker container.
"""
import os
import sys
import argparse

# Ensure src is in search path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

def test_gemini(api_key: str = None, model: str = "gemini-3.8-flash"):

    print("=" * 60)
    print("  GEMINI API CONNECTIVITY & INTELLIGENCE TEST")
    print("=" * 60)

    # 1. Resolve API key
    resolved_key = (
        api_key
        or os.getenv("INTELLIGENCE_GEMINI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not resolved_key:
        # Check root .env
        env_path = os.path.join(base_dir, "..", ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                content = f.read()
                for line in content.splitlines():
                    if line.startswith("INTELLIGENCE_GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        if val:
                            resolved_key = val
                            break
                if not resolved_key:
                    for line in content.splitlines():
                        if line.startswith("GEMINI_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip("'\"")
                            if val:
                                resolved_key = val
                                break

    if not resolved_key:
        print("\n❌ [ERROR] INTELLIGENCE_GEMINI_API_KEY is not set!")
        print("Please set it in your .env file:")
        print("  INTELLIGENCE_GEMINI_API_KEY=AIzaSy...")
        print("Or run with:")
        print("  python test_gemini.py --key YOUR_API_KEY")
        print("  or")
        print("  docker compose exec -e INTELLIGENCE_GEMINI_API_KEY=YOUR_KEY intelligence-engine python test_gemini.py")
        sys.exit(1)


    masked_key = resolved_key[:6] + "..." + resolved_key[-4:] if len(resolved_key) > 10 else "***"
    print(f"✓ Detected API Key: {masked_key}")
    print(f"✓ Target Model    : {model}")

    # 2. Test raw google.genai client
    print("\n[Step 1] Testing direct connection to Google Gemini API...")
    from google import genai
    client = genai.Client(api_key=resolved_key)
    candidate_models = [model]
    for m in ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]:
        if m not in candidate_models:
            candidate_models.append(m)

    connected_model = None
    for target in candidate_models:
        try:
            print(f"Connecting using model '{target}'...")
            response = client.models.generate_content(
                model=target,
                contents="Respond with only: 'GEMINI_ONLINE_OK'"
            )
            reply = response.text.strip()
            print(f"✓ Response from {target}: {reply}")
            connected_model = target
            print(f"✓ Basic API connectivity SUCCESSFUL with model: {target}!")
            break
        except Exception as e:
            print(f"  Note: {target} returned error ({e}). Trying next model...")

    if not connected_model:
        print("\n❌ [ERROR] Could not connect to any candidate Gemini model.")
        sys.exit(1)


    # 3. Test structured supply chain & climate intelligence enrichment
    print("\n[Step 2] Testing structured climate & regional intelligence enrichment...")
    try:
        os.environ["GEMINI_API_KEY"] = resolved_key
        from src.external.gemini_enricher import GeminiExternalEnricher
        enricher = GeminiExternalEnricher()
        
        result = enricher.analyze_external_context(
            region="Mumbai, Maharashtra",
            industry="jewelry_manufacturing_and_retail",
            specific_factors=["monsoon rainfall", "transport corridor alerts"]
        )

        print("✓ Structured Intelligence Output Received:")
        import json
        print(json.dumps(result, indent=2))

        if result.get("mode") == "offline_fallback":
            print("\n⚠️ Note: Returned offline fallback mode. Check API key.")
        else:
            print("\n🎉 ALL GEMINI TESTS PASSED! Real-time external intelligence is fully working!")

    except Exception as e:
        print(f"\n❌ [ERROR] Enricher parsing failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test Google Gemini API integration")
    parser.add_argument("--key", type=str, default=None, help="Gemini API Key")
    parser.add_argument("--model", type=str, default="gemini-3.8-flash", help="Gemini Model")

    args = parser.parse_args()

    test_gemini(api_key=args.key, model=args.model)

if __name__ == "__main__":
    main()
