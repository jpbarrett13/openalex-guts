import argparse
import csv
from time import gmtime, mktime, sleep

from redis import Redis

from app import REDIS_QUEUE_URL, db
from models import REDIS_WORK_QUEUE
from util import openalex_works_paginate, chunks

_redis = Redis.from_url(REDIS_QUEUE_URL)


def front_of_fast_queue_one_batch(work_ids, no_redis=False):
    """Adds a list of work IDs to the redis fast queue as one batch.
    `work_ids` is a list of integers
    `if `no_redis` is True: return batch but don't actually make the change to the fast queue
    Returns the batch (dict used to add to redis queue)"""
    batch = {work_id: -1 for work_id in work_ids}
    if (batch) and (no_redis is False):
        _redis.zadd(REDIS_WORK_QUEUE, batch)
    return batch


def front_of_fast_queue(file_name, batch_size, no_redis=False):
    """
    Takes a list of work IDs in a CSV and moves them to the front of the fast queue.
    Run with CSV file in root of project directory.
    Test and see IDs: `heroku local:run python -m scripts.front_of_fast_queue --file ids_to_run.csv --no-redis`
    Store in redis: `heroku local:run python -m scripts.front_of_fast_queue --file ids_to_run.csv`
    """

    with open(file_name, 'r') as f:
        count = 0

        reader = csv.reader(f)
        work_ids_for_fast_queue = []

        # iterate through the CSV file in batches
        for i, row in enumerate(reader):
            if i % batch_size == 0 and work_ids_for_fast_queue:
                batch = front_of_fast_queue_one_batch(work_ids_for_fast_queue,
                                                      no_redis=no_redis)
                if no_redis:
                    print(batch)
                work_ids_for_fast_queue = []
                print(f"processed {count} rows")
                sleep(0.5)

            work_id = int(row[0].replace("https://openalex.org/W", ""))
            work_ids_for_fast_queue.append(work_id)
            count += 1

        # add remaining items in the batch if any
        if work_ids_for_fast_queue:
            batch = front_of_fast_queue_one_batch(work_ids_for_fast_queue,
                                                  no_redis=no_redis)
            if no_redis:
                print(batch)
            print(f"finished processing file, count is {count}")


def front_of_fast_queue_api(oax_filter, batch_size, no_redis=False):
    batch = []
    count = 0
    for page in openalex_works_paginate(oax_filter, select='id'):
        for work in page:
            count += 1
            try:
                work_id = int(work['id'].split('/W')[-1])
                batch.append(work_id)
                if len(batch) == batch_size:
                    front_of_fast_queue_one_batch(batch, no_redis=no_redis)
                    print(
                        f'Enqueued {len(batch)} ({count} total) works to front of fast queue from filter: {oax_filter}')
                    batch.clear()
            except Exception as e:
                print(e)
    front_of_fast_queue_one_batch(batch, no_redis=no_redis)
    print(
        f'Enqueued {len(batch)} ({count} total) works to front of fast queue from filter: {oax_filter}')
    batch.clear()


def front_of_fast_queue_sql(sql_query, batch_size, no_redis=False):
    rows = db.session.execute(sql_query).fetchall()
    work_ids = [row[0] for row in rows]
    count = 0
    for chunk in chunks(work_ids, batch_size):
        try:
            front_of_fast_queue_one_batch(chunk, no_redis)
            count += len(chunk)
            print(
                f'Enqueued {count} ({len(work_ids)} total) works to front of fast queue from SQL query: {sql_query}')
        except Exception as e:
            print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Front of Fast Queue Script")
    parser.add_argument('--oax_filter', '-oaxf',
                        help='OpenAlex API filter(s) to enqueue works',
                        action='append')
    parser.add_argument('--sql_query', '-sql', type=str,
                        help='SQL query to fetch work IDs enqueue')
    parser.add_argument("--file", help="Input CSV file name")
    parser.add_argument("--batch-size", type=int, default=10000,
                        help="Batch size (default: 10000)")
    parser.add_argument("--no-redis", action="store_true",
                        help="Test script without saving to Redis")
    args = parser.parse_args()
    if not args.oax_filter and not args.file and not args.sql_query:
        raise ValueError('Either --oax_filter or --file or --sql_query must be specified')
    if args.file:
        front_of_fast_queue(args.file, args.batch_size, args.no_redis)
    elif args.oax_filter:
        for _filter in args.oax_filter:
            print(f'Enqueueing works from OpenAlex filter: {_filter}')
            front_of_fast_queue_api(_filter, args.batch_size, args.no_redis)
    elif args.sql_query:
        front_of_fast_queue_sql(args.sql_query, args.batch_size, args.no_redis)
