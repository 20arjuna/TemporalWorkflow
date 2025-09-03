"""
Comprehensive Test Runner

This script runs all test suites in the correct order and provides
a comprehensive report of system health and functionality.

Usage:
    python tests/run_comprehensive_tests.py [--fast] [--stress] [--report]
    
Options:
    --fast: Skip stress tests and chaos engineering (faster execution)
    --stress: Run only stress tests and chaos engineering
    --report: Generate detailed HTML report
"""

import asyncio
import subprocess
import sys
import time
import argparse
from pathlib import Path

def run_test_suite(test_file, description, fast_mode=False, stress_only=False):
    """Run a specific test suite and return results."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    # Skip logic
    if fast_mode and ("stress" in test_file.lower() or "chaos" in test_file.lower()):
        print(f"⏭️  Skipping {test_file} (fast mode)")
        return {"skipped": True, "reason": "fast_mode"}
    
    if stress_only and not ("stress" in test_file.lower() or "chaos" in test_file.lower()):
        print(f"⏭️  Skipping {test_file} (stress only mode)")
        return {"skipped": True, "reason": "stress_only"}
    
    start_time = time.time()
    
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_file, 
            "-v", 
            "--tb=short",
            "--disable-warnings"
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout per suite
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED ({execution_time:.1f}s)")
            passed_count = result.stdout.count(" PASSED")
            return {
                "status": "PASSED", 
                "execution_time": execution_time,
                "passed_count": passed_count,
                "output": result.stdout
            }
        else:
            print(f"❌ {description} - FAILED ({execution_time:.1f}s)")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return {
                "status": "FAILED", 
                "execution_time": execution_time,
                "output": result.stdout,
                "error": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (>5 minutes)")
        return {"status": "TIMEOUT", "execution_time": 300}
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return {"status": "ERROR", "error": str(e)}

def generate_report(results, output_file="test_report.html"):
    """Generate HTML test report."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Temporal Workflow System - Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .passed {{ color: green; }}
            .failed {{ color: red; }}
            .timeout {{ color: orange; }}
            .skipped {{ color: gray; }}
            .summary {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin: 20px 0; }}
            .test-suite {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
            pre {{ background: #f8f8f8; padding: 10px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>🧪 Temporal Workflow System Test Report</h1>
        <p><strong>Generated:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary">
            <h2>📊 Summary</h2>
    """
    
    total_suites = len(results)
    passed_suites = sum(1 for r in results.values() if r.get("status") == "PASSED")
    failed_suites = sum(1 for r in results.values() if r.get("status") == "FAILED")
    skipped_suites = sum(1 for r in results.values() if r.get("skipped", False))
    
    total_time = sum(r.get("execution_time", 0) for r in results.values())
    total_tests = sum(r.get("passed_count", 0) for r in results.values())
    
    html_content += f"""
            <p><strong>Total Test Suites:</strong> {total_suites}</p>
            <p><strong>Passed:</strong> <span class="passed">{passed_suites}</span></p>
            <p><strong>Failed:</strong> <span class="failed">{failed_suites}</span></p>
            <p><strong>Skipped:</strong> <span class="skipped">{skipped_suites}</span></p>
            <p><strong>Total Tests:</strong> {total_tests}</p>
            <p><strong>Total Execution Time:</strong> {total_time:.1f}s</p>
        </div>
        
        <h2>📋 Test Suite Details</h2>
    """
    
    for suite_name, result in results.items():
        status = result.get("status", "SKIPPED" if result.get("skipped") else "UNKNOWN")
        css_class = status.lower()
        
        html_content += f"""
        <div class="test-suite">
            <h3 class="{css_class}">🧪 {suite_name} - {status}</h3>
        """
        
        if not result.get("skipped"):
            html_content += f"<p><strong>Execution Time:</strong> {result.get('execution_time', 0):.1f}s</p>"
            
            if result.get("passed_count"):
                html_content += f"<p><strong>Tests Passed:</strong> {result['passed_count']}</p>"
            
            if result.get("output"):
                html_content += f"<h4>Output:</h4><pre>{result['output']}</pre>"
            
            if result.get("error"):
                html_content += f"<h4>Error:</h4><pre>{result['error']}</pre>"
        else:
            html_content += f"<p><em>Skipped: {result.get('reason', 'Unknown')}</em></p>"
        
        html_content += "</div>"
    
    html_content += """
    </body>
    </html>
    """
    
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"\n📄 Test report generated: {output_file}")

def main():
    """Run comprehensive test suite."""
    parser = argparse.ArgumentParser(description="Run comprehensive Temporal workflow tests")
    parser.add_argument("--fast", action="store_true", help="Skip stress tests for faster execution")
    parser.add_argument("--stress", action="store_true", help="Run only stress tests")
    parser.add_argument("--report", action="store_true", help="Generate HTML report")
    
    args = parser.parse_args()
    
    print("🚀 Starting Comprehensive Test Suite")
    print(f"Mode: {'Fast' if args.fast else 'Stress Only' if args.stress else 'Full'}")
    
    # Define test suites in execution order
    test_suites = [
        ("tests/test_database.py", "Database Foundation Tests"),
        ("tests/test_activity_logic_db.py", "Activity Logic Tests"),
        ("tests/test_e2e_workflow_integration.py", "End-to-End Workflow Integration"),
        ("tests/test_api_endpoints_comprehensive.py", "API Endpoints Comprehensive Tests"),
        ("tests/test_cli_comprehensive.py", "CLI Comprehensive Tests"),
        ("tests/test_system_integration.py", "System Integration Tests"),
        ("tests/test_stress_and_chaos.py", "Stress Tests and Chaos Engineering"),
    ]
    
    overall_start_time = time.time()
    results = {}
    
    for test_file, description in test_suites:
        # Check if test file exists
        if not Path(test_file).exists():
            print(f"⚠️  Test file not found: {test_file}")
            results[description] = {"status": "NOT_FOUND", "execution_time": 0}
            continue
        
        result = run_test_suite(test_file, description, args.fast, args.stress)
        results[description] = result
        
        # Stop on critical failures (optional)
        if result.get("status") == "FAILED" and "Foundation" in description:
            print(f"\n💥 Critical test suite failed: {description}")
            print("🛑 Stopping execution due to foundation failure")
            break
    
    overall_time = time.time() - overall_start_time
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 COMPREHENSIVE TEST SUMMARY")
    print(f"{'='*60}")
    
    for description, result in results.items():
        status = result.get("status", "SKIPPED" if result.get("skipped") else "UNKNOWN")
        exec_time = result.get("execution_time", 0)
        
        status_icon = {
            "PASSED": "✅",
            "FAILED": "❌", 
            "TIMEOUT": "⏰",
            "ERROR": "💥",
            "NOT_FOUND": "⚠️",
            "SKIPPED": "⏭️"
        }.get(status, "❓")
        
        print(f"{status_icon} {description:<40} {status:<10} ({exec_time:.1f}s)")
    
    print(f"\n⏱️  Total execution time: {overall_time:.1f}s")
    
    # Generate report if requested
    if args.report:
        generate_report(results)
    
    # Exit with appropriate code
    failed_count = sum(1 for r in results.values() if r.get("status") == "FAILED")
    if failed_count > 0:
        print(f"\n❌ {failed_count} test suite(s) failed")
        sys.exit(1)
    else:
        print(f"\n🎉 All test suites passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()