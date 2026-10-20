"""Bounded asset batches using the available CPUs, with ordered results."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
import os

from . import progress


def worker_count(total: int, *, processes: bool = False) -> int:
    configured = os.environ.get('WAW2BO2_WORKERS')
    available = getattr(os, 'process_cpu_count', os.cpu_count)() or 1
    workers = int(configured) if configured else available
    if workers < 1:
        raise ValueError('WAW2BO2_WORKERS must be a positive integer')
    if processes and os.name == 'nt':
        workers = min(workers, 61)  # ProcessPoolExecutor's Windows handle limit.
    return min(workers, max(1, total))


def ordered_map(function, values, *, label: str, processes: bool = False):
    """Keep reports deterministic and at most two batches in flight.

    Workers own independent assets; shared manifests and output conflicts are
    handled by the caller on the main thread. CPU-heavy Python work uses spawn
    processes; native calls and subprocesses can run concurrently in threads.
    """
    values = list(values)
    workers = worker_count(len(values), processes=processes)
    if not values:
        return
    print(f'[staging] {label}: {workers} parallel workers', flush=True)
    if workers == 1:
        for value in progress.items(label, values):
            yield function(value)
        return
    executor_type = ProcessPoolExecutor if processes else ThreadPoolExecutor
    options = ({'mp_context': multiprocessing.get_context('spawn')} if processes
               else {'thread_name_prefix': 'convert-asset'})
    pool = executor_type(max_workers=workers, **options)
    pending = deque()
    source = iter(values)
    exhausted = object()
    try:
        for _ in range(min(len(values), workers * 2)):
            pending.append(pool.submit(function, next(source)))
        for _ in progress.items(label, range(len(values))):
            result = pending.popleft().result()
            value = next(source, exhausted)
            if value is not exhausted:
                pending.append(pool.submit(function, value))
            yield result
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)


def write_shared(path, data: bytes) -> None:
    """Write a file other workers may write with the same content at the same time
    (content-named shaders, images shared by materials): a private temporary file is
    moved into place, retrying while another worker holds the target open."""
    import time
    from pathlib import Path
    import threading
    path = Path(path)
    try:
        if path.is_file() and path.stat().st_size == len(data) and path.read_bytes() == data:
            return
    except PermissionError:
        pass  # another worker is replacing it right now; write ours below
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    temp.write_bytes(data)
    for attempt in range(50):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.05)
