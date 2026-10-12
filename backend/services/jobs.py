import uuid

jobs: dict[str, dict] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "percent": 0}
    return job_id


def get_job(job_id: str) -> dict | None:
    return jobs.get(job_id)


def update_job(job_id: str, **fields) -> dict:
    jobs[job_id].update(fields)
    return jobs[job_id]