# 고용24 사이트 구조 분석 보고서

> 조사일: 2026-03-18
> 대상: https://www.work24.go.kr

---

## 1. 사이트 개요

- 고용노동부 + 한국고용정보원 운영
- 구 워크넷(Worknet)에서 2024-09-23 고용24로 리브랜딩
- 총 채용공고 수: **약 130,000건** (조사 시점)
- 기술 스택: **jQuery + 바닐라 JS** (SPA 프레임워크 없음)
- 렌더링 방식: **서버사이드 렌더링(SSR)** - HTTP 요청만으로 데이터 수집 가능

---

## 2. 채용공고 목록 페이지

### URL

| 구분 | URL | Method |
|------|-----|--------|
| 초기 로드 | `/wk/a/b/1200/retriveDtlEmpSrchList.do` | GET |
| 검색/페이지 이동 | `/wk/a/b/1200/retriveDtlEmpSrchListInPost.do` | POST |

### 렌더링 방식

- **SSR (서버사이드 렌더링)**: 목록 데이터가 HTML 응답에 직접 포함됨
- HTTP 요청(requests/httpx)만으로 데이터 수집 **가능** (헤드리스 브라우저 불필요)
- POST → 302 리다이렉트 → GET 응답에 데이터 포함
- D-day 계산만 JS 의존 (마감일 원본 날짜는 HTML에 포함)

### 목록 아이템 데이터 구조

각 공고는 `<table>` 내 `<tr>` 행으로 표현. 한 행에 포함되는 정보:

| 필드 | 예시 | 비고 |
|------|------|------|
| 회사명 | 해맑은노인복지센터 | 링크 (회사 상세) |
| 채용공고명 | [장기동] 재가요양보호사 모집 | 링크 (상세 페이지) |
| 정보제공처 | 고용24 | 이미지 태그 |
| 급여 | 시급 10,320원 이상 | 시급/월급/연봉 형태 |
| 경력 | 경력무관 | |
| 학력 | 학력무관 | |
| 근무일수 | 주2일 / 주5일 / 주6일 | |
| 근무시간 | 주 6시간 근로, 14:00~17:00 | 선택적 |
| 근무지역 | 대구광역시 달서구 용산로 | |
| 마감 상태 | 채용시까지 / D-6 / D-7 | `<strong>` 태그 |
| 마감일 | 2026-04-01 | |
| 등록일 | 2026-03-18 | |
| 기업 태그 | 대기업, 코스피, 가족 등 | 선택적 |
| 고용24 입사지원 가능 | 표시 여부 | `<strong>` 태그 |

### 상세 페이지 링크 패턴

```
/wk/a/b/1500/empDetailAuthView.do
  ?wantedAuthNo=KF10882603180014
  &infoTypeCd=VALIDATION
  &infoTypeGroup=tb_workinfoworknet
```

- `wantedAuthNo`: 공고 고유 ID (구인인증번호)
- ID 형식 예시: `KF10882603180014`, `KJKB002603180001`, `K180632603180002`

### 페이지네이션

```javascript
paginationInfo = {
  currentPageNo: 1,
  recordCountPerPage: 10,  // 10, 30, 50 선택 가능
  pageSize: 10,
  totalRecordCount: 130297,
  totalPageCount: 13030,
  lastPageNo: 13030
}
```

- 페이지 이동: POST `pageIndex` 파라미터
- 페이지당 건수: POST `resultCnt` 파라미터 (10/30/50)
- 총 건수: HTML 내 `totalRecordCount` 값에서 추출
- 페이지 간 데이터 중복 없음 (검증 완료)

### 검색 필터 파라미터 (POST)

| 파라미터 | 설명 | 타입 |
|---------|------|------|
| `srcKeyword` | 검색어 | text |
| `notSrcKeyword` | 제외 검색어 | text |
| `occupationParam[]` | 직종 | checkbox (다중) |
| `regionParam[]` | 지역 | checkbox (다중) |
| `careerType[]` | 경력 (신입/경력/관계없음) | checkbox |
| `employGbnParam[]` | 고용형태 | checkbox (다중) |
| `academicGbn` | 학력 | radio |
| `payGbn` | 임금형태 | select |
| `b_minPay` / `b_maxPay` | 급여 범위 | text |
| `cloDateStdt` / `cloDateEndt` | 마감일 범위 | date |
| `regDateStdt` / `regDateEndt` | 등록일 범위 | date |
| `siteClcd[]` | 정보제공처 | checkbox |
| `sortField` | 정렬 기준 (DATE 등) | hidden |
| `sortOrderBy` | 정렬 방향 (DESC/ASC) | hidden |
| `currentPageNo` | 현재 페이지 | hidden |
| `recordCountPerPage` | 페이지당 건수 | select |

### 정렬 옵션

- 최근등록일순 / 예전등록일순
- 회사명 (ㄱ→ㅎ / ㅎ→ㄱ)
- 임금높은순 / 임금낮은순
- 학력높은순 / 학력낮은순
- 경력많은순 / 경력적은순
- 마감일순(오늘~) / 마감일순(상시~)

---

## 3. 채용공고 상세 페이지

### URL

```
GET /wk/a/b/1500/empDetailAuthView.do
  ?wantedAuthNo={구인인증번호}
  &infoTypeCd=VALIDATION
  &infoTypeGroup=tb_workinfoworknet
```

### 렌더링 방식

- Playwright로 정상 접근 확인 (목록 페이지에서 링크 클릭으로 이동)
- WebFetch(JS 미실행)로 직접 접근 시 **"구인정보를 확인할 수 없습니다"** 오류
- **세션 또는 레퍼러 필요** 가능성 있음

### 상세 페이지 데이터 필드

#### 상단 요약

| 필드 | 설명 |
|------|------|
| 회사명 | 기업 이름 |
| 공고 제목 | 채용공고 제목 |
| 조회수 | 공고 조회 횟수 |
| 마감 상태 | 채용시까지 / D-N / 마감 |
| 경력 | 관계없음, 신입, 경력 등 |
| 학력 | 학력무관, 대졸 이상 등 |
| 임금 | 시급/월급/연봉 + 금액 |
| 근무지 | 전체 주소 |
| 고용형태 | 기간의 정함이 없는 근로계약 등 |
| 근무형태 | 주 N일 근무 (주 소정근로시간: N시간) |

#### 탭별 상세 정보

**모집요강**
- 직무내용 (자유 텍스트)
- 모집인원, 장애인 채용인원
- 모집직종, 관련직종, 직종 키워드
- 경력, 학력, 자격면허

**근무조건**
- 고용형태, 임금조건
- 근무시간 (주 소정근로시간, 상세 근무시간)
- 휴게시간, 근무형태
- 사회보험, 퇴직급여
- 근무예정지 (전체 주소), 인근 전철역, 버스 노선

**우대사항**
- 전공, 컴퓨터 활용 능력, 외국어 능력
- 우대조건, 기타 우대사항

**복리후생**
- 통근버스, 기숙사, 차량유지비, 교육비 지원 등 (제공/미제공)
- 장애인용 복지시설

**전형방법**
- 전형 종류 (서류/면접/필기/기타)
- 접수 마감일 + 마감시간
- 접수 방법, 제출 서류

**기업정보**
- 기업명, 업종, 기업규모
- 설립연도, 연매출액, 근로자수

**인증기관 정보**
- 채용공고 등록일시 (초 단위)
- 인증기관명, 연락처
- 구인인증번호 (= wantedAuthNo)

---

## 4. robots.txt

```
User-Agent: *
disallow: /cm/common/
disallow: /sa/
disallow: /ei/
Disallow: /cm/f/c/0100/selectUnifySearchPost.do
Allow: /
Sitemap: https://www.work24.go.kr/cm/static/sitemap.xml
```

- 채용공고 관련 경로(`/wk/`)는 **허용**됨
- sitemap.xml 제공 (약 50개 URL)

---

## 5. Open API 현황

### 5-1. 고용24 자체 Open API

- URL: `https://www.work24.go.kr/cm/e/a/0110/selectOpenApiIntro.do`
- **기업회원 전용**, 심사 후 인증키 발급
- 제공 API: 채용정보, 채용행사, 공채속보, 직업정보, 훈련과정 등
- 데이터 형식: XML (UTF-8)
- POC 용도로는 **부적합** (기업회원 가입 + 심사 필요)

### 5-2. 공공데이터포털 API

- URL: `https://www.data.go.kr/data/3038225/openapi.do`
- **개인도 신청 가능** (API Key 발급)
- 채용 목록 + 상세 정보 조회 가능

#### 요청 파라미터 (주요)

| 파라미터 | 설명 |
|---------|------|
| 인증키 | API Key |
| 시작페이지 | 페이지 번호 |
| 출력건수 | 페이지당 건수 |
| 근무지역 | 지역 코드 |
| 직종 | 직종 코드 |
| 임금형태 | 시급/월급/연봉 |
| 최소/최대급여 | 급여 범위 |
| 학력 | 학력 조건 |
| 경력 | 경력 조건 |
| 키워드 | 검색어 |
| 등록일 | 등록 날짜 |
| 채용여부 | 채용 상태 |
| 정렬방식 | 정렬 기준 |

#### 응답 필드 (주요)

| 필드 | 설명 |
|------|------|
| 구인인증번호 | wantedAuthNo |
| 회사명 | 기업명 |
| 채용제목 | 공고 제목 |
| 임금형태 / 급여 | 급여 정보 |
| 근무지역 | 지역 |
| 경력 / 학력 | 자격 조건 |
| 등록일자 / 마감일자 | 날짜 정보 |
| 채용정보URL | 상세 페이지 URL |
| 고용형태코드 | 고용 형태 |
| 직종코드 | 직종 분류 |

---

## 6. 네트워크 요청 분석 (Playwright 관측)

목록 페이지 로드 시 발생하는 주요 XHR/POST 요청:

| 엔드포인트 | 용도 |
|-----------|------|
| `/wk/cmm/menu/checkProhibitedUrl.do` | URL 차단 확인 |
| `/wk/cmm/menu/checkMenuAuth.do` | 메뉴 권한 확인 |
| `/wk/cmm/menu/checkMenuInfo.do` | 메뉴 정보 확인 |
| `/cm/f/c/0100/retrieveRecommandWord.do` | 추천 검색어 |
| `/wk/l/b/1100/selectJobsSubSearchList.do` | 직종 하위 목록 |
| `/wk/p/c/1310/retriveStaAreaCodeSrchListAjax.do` | 지역 코드 목록 |
| `/wk/a/b/1200/retrieveRegionEmpSubListAjax.do` | 지역별 채용 목록 |
| `/wk/p/a/1300/selectCertLicSubSearchList.do` | 자격증 목록 |
| `/wk/common/getRenderPaging.do` | 페이지네이션 렌더링 |

---

## 7. 핵심 인사이트

### 스크래핑 가능성 평가 (검증 완료)

| 방식 | 목록 수집 | 상세 수집 | 마감 판별 | 난이도 | 안정성 |
|------|----------|----------|----------|--------|--------|
| **HTTP 요청 (requests/httpx)** | **O** | **O** | **O** | **하** | **상** |
| Playwright (headless) | O | O | O | 중 | 중 |
| 공공데이터포털 API | O | O | ? | 하 | 상 |
| 고용24 자체 API | O | O | ? | 하 | 상 |

### 검증된 HTTP 요청 방식 (curl 테스트 완료)

**목록 수집:**
```bash
POST /wk/a/b/1200/retriveDtlEmpSrchListInPost.do
  Body: sortField=DATE&sortOrderBy=DESC&pageIndex=1&resultCnt=50
  → 302 리다이렉트 → GET 응답 (HTML에 50건 데이터 포함)
```

**상세 수집:**
```bash
GET /wk/a/b/1500/empDetailAuthView.do
  ?wantedAuthNo={ID}&infoTypeCd=VALIDATION&infoTypeGroup=tb_workinfoworknet
  → HTML 응답 (모든 상세 데이터 포함)
```

**마감 판별:**
```bash
GET /wk/a/b/1500/empDetailAuthView.do?wantedAuthNo={만료된ID}&...
  → HTML 응답에 alert("구인정보를 확인할 수 없습니다") + history.back 포함
```

### 권장 접근법

**1순위: HTTP 요청 (requests/httpx) + HTML 파싱 (BeautifulSoup)**
- 헤드리스 브라우저 **불필요**
- 세션/쿠키 **불필요** (stateless 요청으로 동작)
- 50건/page로 전체 130,000건 수집 시 약 2,606 페이지 요청
- 상세 페이지도 직접 GET 접근 가능

### 마감 여부 판별

- 목록 페이지: 마감일 원본 날짜가 HTML에 포함 (`var date = '2026-03-27'`)
- 상세 페이지: 접수 마감일 + 마감 상태 표시
- 만료/삭제된 공고: `alert("구인정보를 확인할 수 없습니다")` + `history.back` 패턴으로 판별

### 공고 ID 체계

- `wantedAuthNo` = 구인인증번호
- 형식: 알파벳 접두사 + 숫자 (예: `KF10882603180014`)
- 이 ID로 상세 페이지 직접 접근 가능

---

## 8. 기술적 제약사항

1. **기본 필터**: 초기 로드 시 "상용직" 필터가 기본 적용됨 (POST 파라미터로 제어 가능)
2. **Rate Limiting**: 명시적 제한 없으나, 관공서 사이트로 적절한 딜레이 필요
3. **CAPTCHA**: 현재 관측되지 않음
4. **SSL**: TLSv1.3 지원, 인증서 유효

---

## 9. HTTP 요청 방식 상세 검증 결과

| 테스트 항목 | 결과 | 비고 |
|------------|------|------|
| 목록 POST → 리다이렉트 → GET | 성공 | 302 redirect, `-L` 플래그로 follow |
| resultCnt=50 (50건/page) | 성공 | 50개 unique wantedAuthNo 반환 |
| pageIndex=2 (2페이지) | 성공 | 1페이지와 중복 없는 50건 |
| totalRecordCount 추출 | 성공 | HTML 내 JS 변수에서 추출 가능 |
| 상세 페이지 GET 직접 접근 | 성공 | 세션/쿠키 없이 동작 |
| 만료 공고 접근 | 성공 | alert + history.back 패턴으로 판별 |
| 쿠키 없이 요청 | 성공 | stateless 동작 확인 |
