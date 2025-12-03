import requests
import time
import threading

URL = "http://localhost:8000/data"
HEALTH_URL = "http://localhost:8000/health"

def stress_test():
    success_count = 0
    fail_count = 0
    start_time = time.time()
    
    while time.time() - start_time < 10: # Run for 10 seconds
        try:
            # Send valid data
            data = "0.0,0.0,0.0,0.0,0.0,0.0"
            resp = requests.post(URL, data=data, headers={'Content-Type': 'text/plain'}, timeout=0.5)
            if resp.status_code == 200:
                success_count += 1
            else:
                fail_count += 1
                print(f"Failed with status: {resp.status_code}")
        except Exception as e:
            fail_count += 1
            print(f"Exception: {e}")
            
        # Also check health occasionally
        if success_count % 10 == 0:
            try:
                resp = requests.get(HEALTH_URL, timeout=0.5)
                if resp.status_code != 200:
                    print(f"Health check failed: {resp.status_code}")
            except Exception as e:
                print(f"Health check exception: {e}")

    print(f"Stress Test Results: Success={success_count}, Fail={fail_count}")

if __name__ == "__main__":
    threads = []
    for i in range(5): # 5 concurrent threads
        t = threading.Thread(target=stress_test)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
