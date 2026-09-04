"""
Quick test: connect to OKX WebSocket via proxy, subscribe to tickers,
and verify we receive real-time data within a timeout.
"""
import sys
import time
import json
import threading

sys.path.insert(0, r"C:\Users\zhenx\okx-batch-trader")

from okx_client import OKXWebSocketClient

received = []
lock = threading.Lock()
done = threading.Event()


def on_ticker(t):
    with lock:
        received.append(t)
    if len(received) >= 10:
        done.set()


print("=== OKX WebSocket Test ===")
print(f"Connecting via socks5://127.0.0.1:17001 …")

client = OKXWebSocketClient(on_ticker=on_ticker)
client.start()

# Wait for connection
for i in range(50):
    if client.connected:
        print(f"✓ Connected after {i*0.1:.1f}s")
        break
    time.sleep(0.1)
else:
    print("✗ Connection timed out")
    client.stop()
    sys.exit(1)

# Subscribe to a few pairs
test_pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT", "XRP-USDT"]
print(f"Subscribing to {test_pairs} …")
client.subscribe(test_pairs)

# Wait for data
print("Waiting for ticker data …")
done.wait(timeout=15)

with lock:
    count = len(received)

if count > 0:
    print(f"\n✓ SUCCESS — received {count} ticker messages in 15s")
    print("\nSample ticker (most recent):")
    print(json.dumps(received[-1], indent=2, ensure_ascii=False))
else:
    print("\n✗ FAILED — no ticker data received in 15s")

client.stop()
print(f"\nSubscribed pairs confirmed: {client.subscribed_pairs}")
sys.exit(0 if count > 0 else 1)