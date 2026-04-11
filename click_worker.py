import os
import time
from datetime import datetime, timezone

from URLshort import app, db, increment_click_count, redis_client


CLICK_QUEUE_NAME = os.environ.get('CLICK_QUEUE_NAME', 'shortly:click-events')
IDLE_SLEEP_SECONDS = float(os.environ.get('WORKER_IDLE_SLEEP_SECONDS', '0.5'))
LOG_EACH_EVENT = os.environ.get('WORKER_LOG_EACH_EVENT', 'true').lower() == 'true'


def consume_events_forever():
    if not redis_client:
        raise RuntimeError('Redis is required for click_worker.py. Set REDIS_URL and restart worker.')

    print(f'Click worker listening on queue: {CLICK_QUEUE_NAME}')
    processed_count = 0

    while True:
        try:
            message = redis_client.brpop(CLICK_QUEUE_NAME, timeout=5)
            if not message:
                continue

            _, code = message
            with app.app_context():
                updated = increment_click_count(code)

            processed_count += 1
            if LOG_EACH_EVENT:
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                print(
                    f'[{timestamp}] processed click event code={code} '
                    f'updated={updated} total_processed={processed_count}'
                )
        except Exception as exc:
            print(f'Worker error: {exc}')
            time.sleep(IDLE_SLEEP_SECONDS)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    consume_events_forever()
