from domain.models import Job, job_from_dict, job_to_dict


def make_sample_job() -> Job:
    return Job(
        wanted_auth_no="KF10882603180014",
        info_type_cd="VALIDATION",
        info_type_group="tb_workinfoworknet",
        scraped_at="2026-03-18T18:00:00",
        title="[장기동] 재가요양보호사 모집",
        job_description="장기동 장기주공아파트 3등급 여자어르신 가사서비스",
        qualification="학력무관 | 자격면허: 요양보호사",
        experience="관계없음",
        preferences=None,
        location="대구광역시 달서구 용산로 88",
        detail_url="https://www.work24.go.kr/wk/a/b/1500/empDetailAuthView.do?wantedAuthNo=KF10882603180014&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet",
        hiring_process="면접",
        employment_conditions="기간의 정함이 없는 근로계약(시간제) | 시급 10,320원 이상 | 주 2일 근무 (주 6시간) | 14:00~17:00",
        company="해맑은노인복지센터 | 사회복지 상담서비스 제공업 | 52명",
        benefits=None,
        application_method="방문 | 이력서 | 채용시까지 (마감: 2026-04-01)",
        deadline_date="2026-04-01",
        registration_date="2026-03-18",
    )


def test_job_to_dict_roundtrip():
    job = make_sample_job()
    d = job_to_dict(job)
    restored = job_from_dict(d)
    assert restored == job


def test_job_to_dict_contains_all_fields():
    job = make_sample_job()
    d = job_to_dict(job)
    assert d["wanted_auth_no"] == "KF10882603180014"
    assert d["title"] == "[장기동] 재가요양보호사 모집"
    assert d["preferences"] is None


def test_job_from_dict_with_none_fields():
    job = make_sample_job()
    d = job_to_dict(job)
    d["preferences"] = None
    d["benefits"] = None
    restored = job_from_dict(d)
    assert restored.preferences is None
    assert restored.benefits is None
