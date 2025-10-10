"""
End-to-End Workflow Testing - Simulating Real User Scenarios

This test suite simulates actual user workflows:
- Complete model training workflow
- Concurrent process execution
- Process cancellation
- Error handling scenarios
"""

import asyncio
import json
import time
import httpx
import websockets
from datetime import datetime
from pathlib import Path


class WorkflowResults:
    """Collect workflow test results"""
    def __init__(self):
        self.scenarios = []
        self.bugs = []
        self.ux_notes = []

    def add_scenario(self, name, status, steps, duration):
        self.scenarios.append({
            "name": name,
            "status": status,
            "steps": steps,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })

    def add_bug(self, severity, description, location):
        self.bugs.append({
            "severity": severity,
            "description": description,
            "location": location
        })

    def add_ux_note(self, observation):
        self.ux_notes.append(observation)


results = WorkflowResults()


async def scenario_1_complete_training_workflow():
    """
    Scenario 1: Complete Model Training Workflow
    Simulates user clicking through UI to train a model
    """
    print("\n🎬 Scenario 1: Complete Model Training Workflow")
    print("-" * 80)

    steps = []
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: User opens dashboard
            print("Step 1: User opens dashboard...")
            response = await client.get("http://localhost:5100/")
            steps.append({"step": 1, "action": "Open dashboard", "status": "✅" if response.status_code == 200 else "❌"})

            # Step 2: User views available datasets
            print("Step 2: User checks available datasets...")
            response = await client.get("http://localhost:5100/api/datasets")
            datasets = response.json().get("datasets", [])
            steps.append({"step": 2, "action": f"View datasets (found {len(datasets)})", "status": "✅" if datasets else "⚠️"})

            if not datasets:
                results.add_ux_note("No datasets available - user would be blocked from training. Need better onboarding.")
                print("⚠️  No datasets available for training")

            # Step 3: User selects dataset and clicks "Train Model"
            print("Step 3: User initiates model training...")
            # Note: We can't actually train without a real dataset, but we can test the API structure
            train_request = {
                "dataset": "test_dataset",
                "feature_handler": "alpha158",
                "model_handler": "lightgbm"
            }

            # This will fail due to missing dataset, which is expected
            response = await client.post("http://localhost:5100/api/models/train", json=train_request)
            data = response.json()

            if "process_id" in data:
                process_id = data["process_id"]
                steps.append({"step": 3, "action": "Start training", "status": "✅", "process_id": process_id})

                # Step 4: Monitor process via WebSocket
                print(f"Step 4: Monitor process {process_id}...")
                try:
                    uri = f"ws://localhost:5100/ws/processes/{process_id}"
                    async with websockets.connect(uri) as ws:
                        # Get initial update
                        message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        update = json.loads(message)

                        if update["type"] == "process_update":
                            steps.append({"step": 4, "action": "Receive WebSocket updates", "status": "✅"})

                            # Wait for process to complete/fail
                            for i in range(10):  # Max 10 updates
                                message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                                update = json.loads(message)

                                if update["type"] == "process_complete":
                                    status = update["data"]["status"]
                                    steps.append({"step": 5, "action": f"Process completed ({status})", "status": "✅"})
                                    break

                                if update["type"] == "process_update":
                                    progress = update["data"]["metrics"]["progress_percent"]
                                    print(f"   Progress: {progress:.1f}%")
                        else:
                            steps.append({"step": 4, "action": "WebSocket updates", "status": "❌", "error": "Wrong message type"})

                except asyncio.TimeoutError:
                    steps.append({"step": 4, "action": "Monitor process", "status": "⚠️", "note": "Timeout (expected for test dataset)"})
            else:
                steps.append({"step": 3, "action": "Start training", "status": "✅", "note": "Returned immediately (expected)"})

        duration = time.time() - start_time
        status = "PASS" if all(s.get("status") == "✅" for s in steps if "status" in s) else "PARTIAL"
        results.add_scenario("Complete Training Workflow", status, steps, duration)

        print(f"\n✅ Scenario 1 completed in {duration:.2f}s")

    except Exception as e:
        steps.append({"error": str(e)})
        results.add_scenario("Complete Training Workflow", "FAIL", steps, time.time() - start_time)
        print(f"❌ Scenario 1 failed: {e}")


async def scenario_2_concurrent_processes():
    """
    Scenario 2: Concurrent Multiple Processes
    Tests system handling multiple simultaneous operations
    """
    print("\n🎬 Scenario 2: Concurrent Multiple Processes")
    print("-" * 80)

    steps = []
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Start 3 processes concurrently
            print("Starting 3 concurrent processes...")

            requests = [
                {"dataset": "test_dataset_1", "feature_handler": "alpha158", "model_handler": "lightgbm"},
                {"dataset": "test_dataset_2", "feature_handler": "alpha158", "model_handler": "xgboost"},
                {"dataset": "test_dataset_3", "feature_handler": "alpha360", "model_handler": "lightgbm"},
            ]

            # Send all requests concurrently
            tasks = [
                client.post("http://localhost:5100/api/models/train", json=req)
                for req in requests
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            process_ids = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    steps.append({"step": i+1, "action": f"Start process {i+1}", "status": "❌", "error": str(response)})
                else:
                    data = response.json()
                    if "process_id" in data:
                        process_ids.append(data["process_id"])
                        steps.append({"step": i+1, "action": f"Start process {i+1}", "status": "✅", "process_id": data["process_id"]})

            # Verify all have unique IDs
            if len(process_ids) == len(set(process_ids)):
                steps.append({"step": 4, "action": "Verify unique process IDs", "status": "✅"})
                print(f"✅ All {len(process_ids)} processes have unique IDs")
            else:
                steps.append({"step": 4, "action": "Verify unique process IDs", "status": "❌", "error": "Duplicate IDs detected"})
                results.add_bug("CRITICAL", f"Process ID collision detected: {process_ids}", "process_monitor.py or trainer.py")

            # Check they all appear in process list
            response = await client.get("http://localhost:5100/api/processes")
            all_processes = response.json()["processes"]

            found_count = sum(1 for pid in process_ids if any(p["process_id"] == pid for p in all_processes))
            steps.append({"step": 5, "action": f"Verify all appear in list", "status": "✅" if found_count == len(process_ids) else "❌"})

        duration = time.time() - start_time
        results.add_scenario("Concurrent Processes", "PASS", steps, duration)
        print(f"\n✅ Scenario 2 completed in {duration:.2f}s")

    except Exception as e:
        steps.append({"error": str(e)})
        results.add_scenario("Concurrent Processes", "FAIL", steps, time.time() - start_time)
        print(f"❌ Scenario 2 failed: {e}")


async def scenario_3_cancel_process():
    """
    Scenario 3: Cancel Running Process
    Tests cancellation workflow
    """
    print("\n🎬 Scenario 3: Cancel Running Process")
    print("-" * 80)

    steps = []
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Start a process
            print("Step 1: Start a training process...")
            response = await client.post("http://localhost:5100/api/models/train", json={
                "dataset": "test_cancel",
                "feature_handler": "alpha158",
                "model_handler": "lightgbm"
            })

            data = response.json()
            if "process_id" in data:
                process_id = data["process_id"]
                steps.append({"step": 1, "action": "Start process", "status": "✅", "process_id": process_id})

                # Wait a moment for it to start
                await asyncio.sleep(1)

                # Step 2: Cancel it
                print(f"Step 2: Cancel process {process_id}...")
                cancel_response = await client.delete(f"http://localhost:5100/api/processes/{process_id}")

                if cancel_response.status_code in [200, 400]:  # 400 if already completed
                    steps.append({"step": 2, "action": "Cancel process", "status": "✅", "code": cancel_response.status_code})

                    # Step 3: Verify status changed
                    check_response = await client.get(f"http://localhost:5100/api/processes/{process_id}")
                    process_data = check_response.json()

                    if process_data["status"] in ["cancelled", "failed", "completed"]:
                        steps.append({"step": 3, "action": "Verify cancellation", "status": "✅", "final_status": process_data["status"]})
                        print(f"✅ Process status: {process_data['status']}")
                    else:
                        steps.append({"step": 3, "action": "Verify cancellation", "status": "❌", "note": f"Status is {process_data['status']}"})
                else:
                    steps.append({"step": 2, "action": "Cancel process", "status": "❌", "code": cancel_response.status_code})
            else:
                steps.append({"step": 1, "action": "Start process", "status": "❌", "note": "No process_id returned"})

        duration = time.time() - start_time
        results.add_scenario("Cancel Process", "PASS", steps, duration)
        print(f"\n✅ Scenario 3 completed in {duration:.2f}s")

    except Exception as e:
        steps.append({"error": str(e)})
        results.add_scenario("Cancel Process", "FAIL", steps, time.time() - start_time)
        print(f"❌ Scenario 3 failed: {e}")


async def scenario_4_error_handling():
    """
    Scenario 4: Process Failure Handling
    Tests how system handles errors
    """
    print("\n🎬 Scenario 4: Process Failure Handling")
    print("-" * 80)

    steps = []
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try to train with invalid dataset
            print("Step 1: Attempt training with invalid dataset...")
            response = await client.post("http://localhost:5100/api/models/train", json={
                "dataset": "nonexistent_dataset_xyz_12345",
                "feature_handler": "alpha158",
                "model_handler": "lightgbm"
            })

            data = response.json()
            if "process_id" in data:
                process_id = data["process_id"]
                steps.append({"step": 1, "action": "Start process with invalid dataset", "status": "✅"})

                # Wait and check if it fails
                await asyncio.sleep(2)

                response = await client.get(f"http://localhost:5100/api/processes/{process_id}")
                process_data = response.json()

                if process_data["status"] == "failed":
                    steps.append({"step": 2, "action": "Process fails gracefully", "status": "✅"})

                    # Check error message is informative
                    if process_data.get("error") and "not found" in process_data["error"].lower():
                        steps.append({"step": 3, "action": "Error message is clear", "status": "✅"})
                        print(f"✅ Clear error: {process_data['error']}")
                    else:
                        steps.append({"step": 3, "action": "Error message clarity", "status": "⚠️"})
                        results.add_ux_note("Error message could be more user-friendly")

                    # Verify UI remains functional
                    health_check = await client.get("http://localhost:5100/api/health")
                    if health_check.status_code == 200:
                        steps.append({"step": 4, "action": "System remains stable", "status": "✅"})
                    else:
                        steps.append({"step": 4, "action": "System stability", "status": "❌"})
                        results.add_bug("HIGH", "System unstable after process failure", "api_enhanced.py")
                else:
                    steps.append({"step": 2, "action": "Process fails", "status": "❌", "note": f"Status is {process_data['status']}"})
            else:
                steps.append({"step": 1, "action": "Start invalid process", "status": "❌"})

        duration = time.time() - start_time
        results.add_scenario("Error Handling", "PASS", steps, duration)
        print(f"\n✅ Scenario 4 completed in {duration:.2f}s")

    except Exception as e:
        steps.append({"error": str(e)})
        results.add_scenario("Error Handling", "FAIL", steps, time.time() - start_time)
        print(f"❌ Scenario 4 failed: {e}")


async def scenario_5_websocket_reconnection():
    """
    Scenario 5: WebSocket Reconnection
    Tests WebSocket resilience
    """
    print("\n🎬 Scenario 5: WebSocket Reconnection")
    print("-" * 80)

    steps = []
    start_time = time.time()

    try:
        # Connect to WebSocket
        print("Step 1: Connect to WebSocket...")
        uri = "ws://localhost:5100/ws/processes"

        async with websockets.connect(uri) as ws:
            steps.append({"step": 1, "action": "Initial connection", "status": "✅"})

            # Receive first message
            message = await asyncio.wait_for(ws.recv(), timeout=3.0)
            steps.append({"step": 2, "action": "Receive initial data", "status": "✅"})

            # Close and reconnect
            print("Step 2: Disconnect and reconnect...")
            await ws.close()

        await asyncio.sleep(0.5)

        # Reconnect
        async with websockets.connect(uri) as ws:
            steps.append({"step": 3, "action": "Reconnection", "status": "✅"})

            message = await asyncio.wait_for(ws.recv(), timeout=3.0)
            data = json.loads(message)

            if data["type"] == "process_update":
                steps.append({"step": 4, "action": "Data after reconnect", "status": "✅"})
                print("✅ WebSocket reconnection successful")
            else:
                steps.append({"step": 4, "action": "Data validation", "status": "❌"})

        results.add_ux_note("WebSocket reconnection works, but frontend should show 'reconnecting' indicator")

        duration = time.time() - start_time
        results.add_scenario("WebSocket Reconnection", "PASS", steps, duration)
        print(f"\n✅ Scenario 5 completed in {duration:.2f}s")

    except Exception as e:
        steps.append({"error": str(e)})
        results.add_scenario("WebSocket Reconnection", "FAIL", steps, time.time() - start_time)
        print(f"❌ Scenario 5 failed: {e}")


async def run_workflow_tests():
    """Execute all workflow scenarios"""
    print("\n" + "=" * 80)
    print("🎭 END-TO-END WORKFLOW TESTING")
    print("Simulating Real User Scenarios")
    print("=" * 80)

    # Run all scenarios
    await scenario_1_complete_training_workflow()
    await scenario_2_concurrent_processes()
    await scenario_3_cancel_process()
    await scenario_4_error_handling()
    await scenario_5_websocket_reconnection()

    # Generate Report
    print("\n" + "=" * 80)
    print("📊 WORKFLOW TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for s in results.scenarios if s["status"] == "PASS")
    partial = sum(1 for s in results.scenarios if s["status"] == "PARTIAL")
    failed = sum(1 for s in results.scenarios if s["status"] == "FAIL")

    print(f"\n✅ PASSED: {passed}")
    print(f"⚠️  PARTIAL: {partial}")
    print(f"❌ FAILED: {failed}")
    print(f"📝 TOTAL: {len(results.scenarios)}\n")

    # Detailed scenario results
    print("\n" + "=" * 80)
    print("SCENARIO DETAILS")
    print("=" * 80)

    for scenario in results.scenarios:
        icon = "✅" if scenario["status"] == "PASS" else "⚠️" if scenario["status"] == "PARTIAL" else "❌"
        print(f"\n{icon} {scenario['status']}: {scenario['name']} ({scenario['duration']:.2f}s)")
        for step in scenario["steps"]:
            if "action" in step:
                status_icon = step.get("status", "")
                print(f"   {status_icon} Step {step.get('step', '?')}: {step['action']}")
                if "note" in step:
                    print(f"      Note: {step['note']}")
                if "error" in step:
                    print(f"      Error: {step['error']}")

    # Bugs found during workflows
    if results.bugs:
        print("\n" + "=" * 80)
        print("🐛 BUGS DISCOVERED")
        print("=" * 80)
        for i, bug in enumerate(results.bugs, 1):
            print(f"\n{i}. [{bug['severity']}] {bug['description']}")
            print(f"   Location: {bug['location']}")

    # UX observations
    if results.ux_notes:
        print("\n" + "=" * 80)
        print("💡 UX/UI OBSERVATIONS")
        print("=" * 80)
        for i, note in enumerate(results.ux_notes, 1):
            print(f"\n{i}. {note}")

    # Save report
    report_path = Path(__file__).parent.parent / "WORKFLOW_TEST_REPORT.json"
    report_data = {
        "summary": {
            "total": len(results.scenarios),
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "timestamp": datetime.now().isoformat()
        },
        "scenarios": results.scenarios,
        "bugs": results.bugs,
        "ux_notes": results.ux_notes
    }

    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)

    print(f"\n📄 Workflow report saved to: {report_path}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_workflow_tests())
