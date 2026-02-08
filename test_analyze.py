"""
Test script for fish image analysis endpoint
Tests the /fish/analyze endpoint with a sample image
"""
import requests
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{API_BASE_URL}/auth/login"
ANALYZE_ENDPOINT = f"{API_BASE_URL}/fish/analyze"

# Test credentials (adjust as needed)
TEST_EMAIL = "admin@example.com"  # Change this to your test user email
TEST_PASSWORD = "password"  # Change this to your test user password


def login():
    """Login and get access token"""
    print("🔑 Logging in...")
    response = requests.post(
        LOGIN_ENDPOINT,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    if response.status_code == 200:
        data = response.json()
        access_token = data.get("accessToken")
        print(f"✅ Login successful!")
        return access_token
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None


def test_analyze_with_dummy_image(access_token):
    """Test analyze endpoint with a simple dummy image"""
    print("\n🔬 Testing fish analysis...")

    # Create a simple dummy image (1x1 pixel red image)
    from PIL import Image
    from io import BytesIO

    # Create a simple test image
    img = Image.new('RGB', (800, 600), color=(73, 109, 137))
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)

    files = {
        'image': ('test_fish.jpg', img_bytes, 'image/jpeg')
    }

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    params = {
        'singleFish': True,
        'scaleReferenceCm': 10.0
    }

    try:
        response = requests.post(
            ANALYZE_ENDPOINT,
            files=files,
            headers=headers,
            params=params,
            timeout=30
        )

        print(f"📊 Response Status: {response.status_code}")

        if response.status_code in [200, 201]:
            print("✅ Analysis successful!")
            data = response.json()
            print(f"\n📋 Analysis Results:")
            print(f"   - Image URL: {data.get('imageUrl')}")
            print(f"   - Detections: {len(data.get('detections', []))}")
            print(f"   - Total Weight: {data.get('totalEstimatedWeight', 0):.2f} kg")
            print(f"   - Predicted Price: ${data.get('predictedPrice', 0):.2f}")
            print(f"   - Species Count: {data.get('speciesCount')}")

            for i, detection in enumerate(data.get('detections', []), 1):
                print(f"\n   Detection #{i}:")
                print(f"      - Species: {detection.get('species')}")
                print(f"      - Confidence: {detection.get('confidence', 0):.2%}")
                print(f"      - Weight: {detection.get('estimatedWeight', 0):.2f} kg")
                print(f"      - Size: {detection.get('sizeCategory')}")

            return True
        else:
            print(f"❌ Analysis failed!")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_analyze_with_real_image(access_token, image_path):
    """Test analyze endpoint with a real image file"""
    print(f"\n🖼️  Testing with real image: {image_path}")

    if not os.path.exists(image_path):
        print(f"❌ Image file not found: {image_path}")
        return False

    with open(image_path, 'rb') as f:
        files = {
            'image': (os.path.basename(image_path), f, 'image/jpeg')
        }

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        params = {
            'singleFish': False
        }

        try:
            response = requests.post(
                ANALYZE_ENDPOINT,
                files=files,
                headers=headers,
                params=params,
                timeout=30
            )

            print(f"📊 Response Status: {response.status_code}")

            if response.status_code in [200, 201]:
                print("✅ Analysis successful!")
                data = response.json()
                print(f"   - Detections: {len(data.get('detections', []))}")
                print(f"   - Total Weight: {data.get('totalEstimatedWeight', 0):.2f} kg")
                print(f"   - Species: {', '.join(data.get('speciesCount', {}).keys())}")
                return True
            else:
                print(f"❌ Analysis failed!")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False


def main():
    print("=" * 60)
    print("🐟 Fish Image Analysis Test Script")
    print("=" * 60)

    # Check if server is running
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Backend server is running")
        else:
            print("⚠️  Backend server responded but may have issues")
    except Exception as e:
        print(f"❌ Cannot connect to backend server at {API_BASE_URL}")
        print(f"   Make sure the server is running: uvicorn app.main:app --reload")
        return

    # Login
    access_token = login()
    if not access_token:
        print("\n❌ Cannot proceed without authentication")
        print(f"   Update TEST_EMAIL and TEST_PASSWORD in this script")
        return

    # Test with dummy image
    print("\n" + "=" * 60)
    print("Test 1: Dummy Image (Tests ML fallback)")
    print("=" * 60)
    test_analyze_with_dummy_image(access_token)

    # Test with real image if provided
    print("\n" + "=" * 60)
    print("Test 2: Real Image (Optional)")
    print("=" * 60)
    image_path = input("\nEnter path to a fish image (or press Enter to skip): ").strip()
    if image_path:
        test_analyze_with_real_image(access_token, image_path)
    else:
        print("⏭️  Skipping real image test")

    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
