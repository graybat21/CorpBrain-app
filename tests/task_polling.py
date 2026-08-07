"""
Shared polling helper for DEC-04 task endpoints.

Not in `fakes.py`: nothing here is a test double. This drives the real HTTP contract, which is
the point — see the docstring on `poll_until_done`.
"""

import time

TERMINAL = ("completed", "multi_status", "failed")


def poll_until_done(client, headers, task_id, timeout=15.0):
    """
    Poll a task to a terminal status, the way the frontend does (DEC-04).

    Deliberately goes through the HTTP endpoint rather than joining the worker thread: the
    thing under test is that the 202 + polling contract actually reports completion. Joining
    the thread would test threading and skip the contract.

    The interval is 50ms rather than the frontend's 1s so the suite does not spend seconds
    waiting; the contract being exercised is identical either way.
    """
    deadline = time.monotonic() + timeout
    data = None
    while time.monotonic() < deadline:
        res = client.get(f"/api/v1/analyze/{task_id}/progress", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        if data["status"] in TERMINAL:
            return data
        time.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not finish within {timeout}s; last state: {data}")
