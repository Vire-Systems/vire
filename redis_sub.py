import asyncio
import time
import redis

r = redis.Redis.from_url("redis://127.0.0.1:6379")

# Setup stream name and starting point
user_uuid = input("USER UUID: ")
job_uuid = input("Job UUID: ")
stream = f"logs:{user_uuid}/{job_uuid}"
last_id = "0-0"  # Read from the beginning. Use "$" to tail only new logs instead.

print(f"Streaming logs from {stream}...")

# Continuous reader loop
while True:
    try:
        # Read available blocks
        response = r.xread({stream: last_id}, count=100, block=1000)

        if not response:
            time.sleep(1)
            continue

        for stream_name, messages in response:
            for msg_id, data in messages:
                # Handle potential raw byte keys/values from redis
                payload = data.get(b"payload" if b"payload" in data else "payload")

                if payload:
                    log_line = (
                        payload.decode("utf-8")
                        if isinstance(payload, bytes)
                        else payload
                    )
                    print(log_line, flush=True)  # Or forward it where it needs to go

                last_id = msg_id  # Advance offset to avoid duplicate reads

    except asyncio.CancelledError:
        print("Reader stopped.")
        break
    except Exception as e:
        print(f"Stream error: {e}")
        time.sleep(1)
