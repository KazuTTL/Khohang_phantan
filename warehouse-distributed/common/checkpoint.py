# common/checkpoint.py
import json, os, time

class CheckpointManager:
    def __init__(self, service_name, state_getter, state_setter):
        self.service_name = service_name
        self.state_getter = state_getter
        self.state_setter = state_setter
        self.log_file = f"logs/{service_name}_log.jsonl"
        self.ckpt_file = f"logs/{service_name}_ckpt.json"
        os.makedirs("logs", exist_ok=True)

    def take_checkpoint(self):
        state = self.state_getter()
        with open(self.ckpt_file, "w") as f:
            json.dump({"timestamp": time.time(), "state": state}, f)

    def log_operation(self, txn_id, op, payload, state):
        with open(self.log_file, "a") as f:
            f.write(json.dumps({
                "txn_id": txn_id, "op": op,
                "payload": payload, "state": state,
                "ts": time.time()
            }) + "\n")

    def recover(self, replay_fn):
        if not os.path.exists(self.ckpt_file):
            print(f"[{self.service_name}] No checkpoint found")
            return
        with open(self.ckpt_file) as f:
            ckpt = json.load(f)
        self.state_setter(ckpt["state"])
        ckpt_time = ckpt["timestamp"]
        print(f"[{self.service_name}] Restored checkpoint")
        if not os.path.exists(self.log_file):
            return
        replayed = 0
        with open(self.log_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry["ts"] > ckpt_time:
                    replay_fn(entry)
                    replayed += 1
        print(f"[{self.service_name}] Replayed {replayed} entries")