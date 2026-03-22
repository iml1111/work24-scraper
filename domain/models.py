from dataclasses import asdict, dataclass


@dataclass
class JobRef:
    wanted_auth_no: str
    info_type_cd: str
    info_type_group: str


@dataclass
class Job:
    wanted_auth_no: str
    info_type_cd: str
    info_type_group: str
    scraped_at: str
    title: str
    job_description: str
    qualification: str
    experience: str
    preferences: str | None
    location: str
    detail_url: str
    hiring_process: str
    employment_conditions: str
    company: str
    benefits: str | None
    application_method: str
    deadline_date: str
    registration_date: str


def job_to_dict(job: Job) -> dict:
    return asdict(job)


def job_from_dict(d: dict) -> Job:
    return Job(**d)
