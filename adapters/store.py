import json
import os
import tempfile

from domain.models import Job, job_from_dict, job_to_dict


class JsonJobStore:
    def __init__(self, path: str = "data/jobs.json"):
        self.path = path

    def load_all(self) -> dict[str, Job]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: job_from_dict(v) for k, v in raw.items()}

    def save_all(self, jobs: dict[str, Job]) -> None:
        raw = {k: job_to_dict(v) for k, v in jobs.items()}
        dir_path = os.path.dirname(self.path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except:
            os.unlink(tmp_path)
            raise

    def get_all_ids(self) -> set[str]:
        if not os.path.exists(self.path):
            return set()
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return set(raw.keys())

    def add_job(self, job: Job) -> None:
        jobs = self.load_all()
        jobs[job.wanted_auth_no] = job
        self.save_all(jobs)

    def remove_job(self, wanted_auth_no: str) -> None:
        jobs = self.load_all()
        jobs.pop(wanted_auth_no, None)
        self.save_all(jobs)

    def clear(self) -> None:
        self.save_all({})
