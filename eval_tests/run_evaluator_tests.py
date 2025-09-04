"""
Temporal Workflow - Complete Evaluator Test Runner

Runs all evaluator tests in the correct order with proper setup validation.
Designed to work on any Python environment without architecture issues.
"""

import subprocess
import sys
import os
import time
import requests
from typing import List, Tuple

def check_system_prerequisites() -> List[str]:
    """Check if system is ready for testing."""
    issues = []
    
    # Check if requests is available
    try:
        import requests
    except ImportError:
        issues.append("❌ 'requests' library not installed. Run: pip install requests")
    
    # Check if API server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code != 200:
            issues.append(f"❌ API server unhealthy (status {response.status_code})")
    except Exception:
        issues.append("❌ API server not running. Start with: python run_api.py")
    
    # Check if Docker Compose is running
    try:
        result = subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True, timeout=10)
        if "postgres" not in result.stdout or "temporal" not in result.stdout:
            issues.append("❌ Docker Compose services not running. Start with: docker-compose up -d")
    except Exception as e:
        print(e)
        issues.append("❌ Docker Compose not available or not running")
    
    return issues

def run_test_suite(test_file: str, description: str) -> Tuple[bool, str]:
    """Run a test suite and return (success, output)."""
    print(f"\n🧪 Running: {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_file, 
            "-v", "-s", "--tb=short"
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"✅ {description} - ALL PASSED")
            # Extract key success messages
            lines = result.stdout.split('\n')
            for line in lines:
                if "✅" in line or "passed" in line.lower():
                    if not line.strip().startswith("="):  # Skip pytest headers
                        print(f"   {line.strip()}")
            return True, result.stdout
        else:
            print(f"❌ {description} - FAILED")
            print(result.stdout)
            return False, result.stdout
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (120s)")
        return False, "Test timed out"
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False, str(e)

def main():
    """Run complete evaluator test suite."""
    print("🚀 TEMPORAL WORKFLOW - EVALUATOR TEST SUITE")
    print("=" * 60)
    print("Testing complete Temporal workflow system for takehome evaluation")
    print("=" * 60)
    
    # Check prerequisites
    print("\n🔍 Checking system prerequisites...")
    issues = check_system_prerequisites()
    
    if issues:
        print("\n❌ SYSTEM NOT READY:")
        for issue in issues:
            print(f"   {issue}")
        print("\n🔧 RUN THIS:")
        print("  docker-compose up -d")
        return 1
    
    print("✅ System prerequisites met")
    
    # Test suites to run
    test_suites = [
        ("test_temporal_concepts.py", "Temporal Concepts & Logic"),
        ("test_cli_functionality.py", "CLI Business Logic"),
        ("test_api_endpoints.py", "API Integration & Workflows"),
    ]
    
    results = []
    total_start_time = time.time()
    
    # Run each test suite
    for test_file, description in test_suites:
        if not os.path.exists(test_file):
            print(f"⚠️  Skipping {test_file} - file not found")
            continue
        
        success, output = run_test_suite(test_file, description)
        results.append((description, success, test_file))
    
    total_time = time.time() - total_start_time
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 TEMPORAL WORKFLOW EVALUATION RESULTS")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for description, success, test_file in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:<8} {description}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} test suites passed")
    print(f"Total time: {total_time:.1f}s")
    
    if passed == total:
        print("\n🎉 ALL EVALUATOR TESTS PASSED!")
        print("✅ Temporal workflow system is working correctly")
        print("✅ Ready for production deployment")
        return 0
    else:
        print(f"\n❌ {total - passed} test suite(s) failed")
        print("🔧 Review failed tests and fix issues before submission")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)