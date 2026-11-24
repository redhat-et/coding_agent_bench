"""Bound synchronization waits in async tests."""

import asyncio


async def wait_for_signal(event, task):
    signal = asyncio.create_task(event.wait())
    try:
        done, _ = await asyncio.wait((signal, task), timeout=2, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task  # Surface the worker's exception, if any.
        if signal not in done:
            raise AssertionError("Worker exited or timed out before its expected signal")
    except BaseException:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
    finally:
        signal.cancel()
        await asyncio.gather(signal, return_exceptions=True)
