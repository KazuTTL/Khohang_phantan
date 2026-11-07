# common/heartbeat.py
import threading, time, requests

class HeartbeatSender(threading.Thread):
    def __init__(self, my_url, coordinator_url):
        super().__init__(daemon=True)
        self.my_url = my_url
        self.coordinator_url = coordinator_url

    def run(self):
        while True:
            try:
                requests.post(
                    f"{self.coordinator_url}/heartbeat",
                    json={"url": self.my_url},
                    timeout=1
                )
            except Exception:
                pass
            time.sleep(2)