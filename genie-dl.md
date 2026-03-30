# GENIE-DL v1.0.5 - 지니뮤직 음원 다운로더 완전 분석 가이드

> **제작자**: vank0n (SJJeon)  
> **목적**: 지니뮤직(genie.co.kr) 스트리밍 서비스에서 음원을 다운로드하는 CLI(명령줄) 도구  
> **언어**: Python 3  
> **분석일**: 2026-03-30

---

## 📖 목차

1. [이 프로그램은 왜 만들어졌나?](#1-이-프로그램은-왜-만들어졌나)
2. [개발자의 설계 철학](#2-개발자의-설계-철학)
3. [전체 실행 흐름 요약](#3-전체-실행-흐름-요약)
4. [코드 구조 상세 분석](#4-코드-구조-상세-분석)
5. [지니 API 통신 구조](#5-지니-api-통신-구조)
6. [전역 변수 사전](#6-전역-변수-사전)
7. [함수 레퍼런스](#7-함수-레퍼런스)
8. [파일/폴더 구조](#8-파일폴더-구조)
9. [사용법](#9-사용법)
10. [알려진 이슈 및 개선점](#10-알려진-이슈-및-개선점)

---

## 1. 이 프로그램은 왜 만들어졌나?

### 배경

지니뮤직은 한국의 대표적인 음원 스트리밍 서비스다. 유료 회원은 앱을 통해 음악을 스트리밍할 수 있지만, **PC에서 직접 음원 파일을 저장**하는 공식적인 방법은 없다.

### 개발 동기

개발자(vank0n)는 이 문제를 해결하기 위해 **지니뮤직의 모바일 앱 API를 분석**했다. 앱이 서버와 통신하는 방식을 역공학(Reverse Engineering)하여, 같은 API를 파이썬으로 호출하면 음원 파일의 직접 URL을 받아올 수 있다는 것을 발견했다.

### 핵심 아이디어

```
유료 회원 로그인 → 인증 토큰 획득 → 토큰으로 스트리밍 URL 요청 → URL로 파일 다운로드
```

이 흐름을 자동화한 것이 GENIE-DL이다.

---

## 2. 개발자의 설계 철학

### "두 가지 모드"를 지원하자

개발자는 사용자 편의를 위해 **두 가지 실행 방식**을 설계했다:

| 모드 | 설명 | 사용 시나리오 |
|------|------|-------------|
| **대화형 모드** | 옵션 없이 실행하면 터미널에 메뉴가 나타나고, 화살표 키로 선택 | 처음 쓰는 사용자, 탐색적 사용 |
| **CLI 모드** | `-c`, `-i` 옵션으로 직접 지정하여 바로 실행 | 자동화, 스크립트 연동, 고급 사용자 |

### "설정 파일"로 반복 입력 방지

매번 아이디/비밀번호를 입력하는 것은 비효율적이므로, `genie-dl-settings.ini` 파일에 한 번 저장하면 다음부터 자동으로 읽어온다.

### "전역 변수"로 데이터 공유

개발자는 함수 간 데이터 전달에 **전역 변수(global)**를 적극 활용했다. 이는 파이썬 초보자에게 익숙한 패턴이며, 코드가 빠르게 동작하도록 한다. (다만 유지보수 측면에서는 개선 여지가 있다.)

### "URL 파라미터"로 유형 판별

지니뮤직 URL에는 항상 특정 키워드가 포함되어 있다:
- `xgnm` = 곡(Track)
- `axnm` = 앨범(Album)
- `xxnm` = 아티스트(Artist)
- `plmSeq` = 플레이리스트(Playlist)

이 패턴을 이용해 URL만으로 어떤 종류의 콘텐츠인지 자동 판별한다.

---

## 3. 전체 실행 흐름 요약

### 3.1 프로그램 시작 시 분기

```
python genie-dl.py 실행
        │
        ├─ 옵션 없음? ──→ main() 호출 ──→ 대화형 메뉴 표시
        │
        ├─ -c 옵션? ──→ 차트 범위 파싱 ──→ download_realtime_chart()
        │
        └─ -i 옵션? ──→ URL 파싱 ──→ parse_user_input() ──→ 유형별 다운로드
```

### 3.2 모든 다운로드의 공통 흐름

어떤 방식으로 시작하든, **모든 곡 다운로드는 동일한 핵심 경로**를 거친다:

```
1. read_config()      → ID/PW 로드
2. login()            → 서버 인증 → user_num, user_token, stm_token 획득
3. parse_track_data() → 곡 ID + 토큰으로 스트리밍 URL 획득
4. download_track()   → 스트리밍 URL에서 실제 파일 다운로드
```

### 3.3 앨범 다운로드의 경우

```
parse_album_data(앨범코드)
   └→ 앨범 정보 API 호출 → 트랙 목록 수집
   └→ 폴더 생성: downloads/아티스트/[날짜] 앨범명/
   └→ for each 트랙:
       ├→ parse_track_data(트랙코드) → 스트리밍 URL
       └→ download_track(URL) → 파일 저장
```

### 3.4 아티스트 다운로드의 경우 (가장 큰 범위)

```
get_artist_albums(아티스트코드)
   └→ 앨범 목록 전체 수집
parse_artist_data(아티스트코드)
   └→ 아티스트 이름 확인
for each 앨범:
   └→ download_album(앨범코드)
       └→ (위의 앨범 다운로드 흐름과 동일)
```

---

## 4. 코드 구조 상세 분석

### 4.1 임포트 영역 (1~17행)

| 라이브러리 | 역할 | 왜 필요한가? |
|-----------|------|------------|
| `requests` | HTTP 요청 | 지니 서버 API와 통신 |
| `json` | JSON 처리 | API 응답 파싱 |
| `os` | OS 기능 | 폴더 생성, 파일 존재 확인 |
| `sys` | 시스템 | 프로그램 강제 종료 |
| `re` | 정규표현식 | URL에서 숫자 추출, 특수문자 제거 |
| `pathlib` | 경로 처리 | 스크립트 위치 확인 |
| `argparse` | CLI 인자 | 명령줄 옵션 파싱 |
| `platform` | OS 종류 | Windows/Mac 구분 |
| `pick` | 터미널 메뉴 | 화살표 키 선택 UI |
| `configparser` | INI 파일 | 설정 읽기/쓰기 |
| `questionary` | 입력 프롬프트 | 깔끔한 ID/PW 입력 |
| `download` | 파일 다운로드 | 진행바 포함 다운로드 |

### 4.2 명령줄 인자 파싱 (19~24행)

**개발자의 생각**: "사용자가 터미널에서 바로 원하는 작업을 지정할 수 있게 하자."

```
python genie-dl.py -c 1-50          # 차트 1~50위 다운로드
python genie-dl.py -i <지니URL>     # 특정 곡/앨범 다운로드
python genie-dl.py --reset          # 로그인 정보 초기화
python genie-dl.py -f flac          # FLAC(무손실) 포맷으로 다운로드
```

### 4.3 전역 변수 (26~43행)

**개발자의 생각**: "프로그램 전체에서 공통으로 사용하는 값들은 한 곳에서 관리하자."

- `BITRATE`: 음질 (320kbps MP3 또는 1000 FLAC)
- `EXTENSION`: 파일 확장자 (mp3 또는 flac)
- `DEVICE_ID`: 지니 서버가 기기를 식별하는 고유 ID
- `OUTPUT_PATH`: 다운로드 파일 저장 폴더 (`./downloads/`)

### 4.4 설정 관리 - read_config() (46~79행)

**개발자의 생각**: "처음 쓰는 사용자는 ID/PW를 입력하게 하고, 한 번 입력하면 파일로 저장해서 다음부터 자동으로 쓰자."

```
genie-dl-settings.ini 형식:
[DEFAULT]
genie_id = user@email.com
genie_password = mypassword
```

> ⚠️ **주의**: 비밀번호가 평문(plain text)으로 저장된다. 보안이 중요한 환경에서는 주의가 필요하다.

### 4.5 유틸리티 함수들 (82~114행)

| 함수 | 입력 | 출력 | 용도 |
|------|------|------|------|
| `is_win()` | 없음 | True/None | OS가 Windows인지 확인 |
| `rm_illegal_character(str)` | 문자열 | 정제된 문자열 | 파일명에 쓸 수 없는 문자 제거 |
| `divider()` | 없음 | 구분선 출력 | 시각적 구분 |
| `remove()` | 없음 | 이전 줄 삭제 | 터미널 UI 갱신 |
| `decode(str)` | URL인코딩 문자열 | 원본 문자열 | `%EC%95%84` → `아` |
| `encode(str)` | 일반 문자열 | URL인코딩 문자열 | `아` → `%EC%95%84` |
| `prettifyNUM(num)` | 숫자 | 2자리 문자열 | `1` → `"01"` |

### 4.6 서버 통신 - 핵심 영역 (131~252행)

#### login() - 인증의 시작

**개발자의 생각**: "지니 앱이 서버에 로그인하는 것과 똑같이 하면 된다."

```python
POST https://app.genie.co.kr/member/j_Member_Login.json
Body: { "uxd": "아이디", "uxx": "비밀번호" }

성공 응답:
{
  "Result": { "RetCode": "0" },
  "DATA0": {
    "MemUno": "사용자번호",
    "MemToken": "인증토큰",
    "STM_TOKEN": "스트리밍토큰"
  }
}
```

이 3개의 토큰이 이후 모든 API 호출의 열쇠가 된다.

#### parse_track_data() - 가장 핵심적인 함수

**개발자의 생각**: "결국 모든 다운로드는 이 함수를 거친다."

이 함수가 하는 일:
1. 곡 ID + 인증 토큰을 스트리밍 서버에 전송
2. 서버가 실제 음원 파일의 직접 다운로드 URL을 반환
3. 이 URL을 `DOWNLOAD_URL` 전역 변수에 저장

```
요청: GET https://stm.genie.co.kr/player/j_StmInfo.json?xgnm=곡ID&bitrate=320&unm=사용자번호&uxtk=토큰&stk=스트리밍토큰&udid=기기ID...

응답: { "DataSet": { "DATA": [{ "STREAMING_MP3_URL": "직접 다운로드 URL" }] } }
```

### 4.7 데이터 파싱 함수들 (152~268행)

이 함수들은 각각 다른 API 엔드포인트를 호출하여 메타데이터를 수집한다:

| 함수 | API 엔드포인트 | 수집하는 데이터 |
|------|--------------|--------------|
| `parse_playlist_data(seq)` | `/Iv3/playlist/infosong.json` | 플레이리스트 이름, 곡 목록 |
| `parse_album_data(axnm)` | `/info/album` | 앨범명, 아티스트, 발매일, 트랙 목록 |
| `parse_artist_data(xxnm)` | `/info/artist` | 아티스트 이름 |
| `get_artist_albums(xxnm)` | `/song/j_ArtistAlbumList.json` | 아티스트의 전체 앨범 목록 |

### 4.8 다운로드 실행 함수들 (270~370행)

| 함수 | 동작 | 저장 경로 |
|------|------|----------|
| `download_album(axnm)` | 앨범 전체 곡 다운로드 | `downloads/아티스트/[YYYY.MM] 앨범명/` |
| `download_playlist(seq)` | 플레이리스트 전체 다운로드 | `downloads/[Playlist] 플레이리스트명/` |
| `download_artist(xxnm)` | 아티스트 전체 앨범 다운로드 | `downloads/아티스트/[날짜] 앨범명/` (각 앨범) |
| `download_realtime_chart(start,end)` | 실시간 차트 다운로드 | `downloads/[Genie TOP 200] - YYMMDD_HH_00/` |

### 4.9 검색 기능 (373~518행)

**개발자의 생각**: "URL을 모를 수도 있으니, 이름으로 검색해서 선택하게 하자."

세 가지 검색 함수 모두 동일한 UX 패턴을 따른다:

```
1. 검색어 입력
2. 지니 검색 API 호출
3. 결과를 번호 목록으로 표시
4. 사용자가 번호 선택
5. 선택된 항목 다운로드
```

### 4.10 URL 파싱 - parse_user_input() (520~550행)

**개발자의 생각**: "URL 하나만 받으면 자동으로 유형을 판별하게 하자."

```
입력: https://genie.co.kr/detail/songInfo?xgnm=97835731
        │
        ├─ "plmSeq" 포함? → Playlist
        ├─ "axnm" 포함?   → Album
        ├─ "xxnm" 포함?   → Artist
        ├─ "xgnm" 포함?   → Track
        └─ 해당 없음?     → Error
```

### 4.11 메인 함수 및 진입점 (553~620행)

**개발자의 생각**: "두 가지 모드를 하나의 진입점에서 분기시키자."

```python
if __name__ == "__main__":
    if 옵션 없음:
        main()  # 대화형 메뉴 모드
    else:
        # 직접 실행 모드
        if -c 옵션: 차트 다운로드
        elif -i 옵션: URL 다운로드
```

---

## 5. 지니 API 통신 구조

### API 엔드포인트 정리

| 용도 | Method | URL | 주요 파라미터 |
|------|--------|-----|-------------|
| 로그인 | POST | `app.genie.co.kr/member/j_Member_Login.json` | uxd, uxx |
| 곡 스트리밍 | GET | `stm.genie.co.kr/player/j_StmInfo.json` | xgnm, bitrate, unm, uxtk, stk, udid |
| 앨범 정보 | GET | `info.genie.co.kr/info/album` | axnm |
| 아티스트 정보 | GET | `info.genie.co.kr/info/artist` | xxnm |
| 아티스트 앨범목록 | GET | `app.genie.co.kr/song/j_ArtistAlbumList.json` | xxnm, pg, pgsize |
| 플레이리스트 | GET | `app.genie.co.kr/Iv3/playlist/infosong.json` | seq |
| 실시간 차트 | GET | `app.genie.co.kr/chart/j_RealTimeRankSongList.json` | pg, pgsize |
| 곡 검색 | GET | `app.genie.co.kr/search/category/songs.json` | query, pagesize |
| 앨범 검색 | GET | `app.genie.co.kr/search/category/albums.json` | query, pagesize |
| 아티스트 검색 | GET | `app.genie.co.kr/search/category/artists.json` | query, pagesize |

### 인증 흐름

```
[사용자] → (ID/PW) → [로그인 API]
    ↓
[서버 응답] → MemUno(사용자번호) + MemToken(인증토큰) + STM_TOKEN(스트리밍토큰)
    ↓
[스트리밍 API] ← (곡ID + 3개 토큰 + 기기ID) ← [사용자]
    ↓
[서버 응답] → STREAMING_MP3_URL (실제 음원 파일 URL)
    ↓
[파일 다운로드] ← (URL) ← [사용자]
```

---

## 6. 전역 변수 사전

### 설정 변수 (프로그램 시작 시 결정)

| 변수명 | 타입 | 설명 | 예시값 |
|--------|------|------|--------|
| `BITRATE` | int/str | 음질 설정 | `320`, `1000`, `"24bit"` |
| `EXTENSION` | str | 파일 확장자 | `"mp3"`, `"flac"` |
| `INPUT_URL` | str/None | -i 옵션 URL | `None` 또는 URL 문자열 |
| `SEARCH_AMOUNT` | int | 검색 결과 최대 수 | `20` |
| `DOWNLOAD_CHART` | str/None | -c 옵션 범위 | `None` 또는 `"1-100"` |
| `RESET_P` | bool | --reset 사용 여부 | `True`/`False` |
| `DEVICE_ID` | str | 기기 고유 ID | UUID 형식 문자열 |
| `SCRIPT_PATH` | str | 스크립트 위치 | 절대 경로 |
| `OUTPUT_PATH` | str | 다운로드 폴더 | `"스크립트경로/downloads/"` |
| `ID` | str | 지니 아이디 | 이메일 형식 |
| `PW` | str | 지니 비밀번호 | 문자열 |

### 인증 변수 (로그인 후 설정)

| 변수명 | 타입 | 설명 | 설정 시점 |
|--------|------|------|----------|
| `user_num` | str | 사용자 고유 번호 | login() 성공 후 |
| `user_token` | str | 사용자 인증 토큰 | login() 성공 후 |
| `stm_token` | str | 스트리밍 인증 토큰 | login() 성공 후 |

### 데이터 변수 (API 호출 후 설정)

| 변수명 | 타입 | 설명 | 설정 함수 |
|--------|------|------|----------|
| `ARTIST_NAME` | str | 현재 곡의 아티스트 | parse_track_data() |
| `SONG_NAME` | str | 현재 곡 제목 | parse_track_data() |
| `DOWNLOAD_URL` | str | 스트리밍 직접 URL | parse_track_data() |
| `IS_VALID` | bool | 스트리밍 가능 여부 | parse_track_data() |
| `ARTIST_NAME_FIX` | str | 아티스트명 (덮어쓰기 방지) | parse_artist_data() |
| `ALBUM_NAME` | str | 앨범 제목 | parse_album_data() |
| `ALBUM_ARTIST` | str | 앨범 아티스트 | parse_album_data() |
| `ALBUM_DATE` | str | 발매일 "[YYYY.MM]" | parse_album_data() |
| `ALBUM_TRACK_COUNT` | int | 앨범 트랙 수 | parse_album_data() |
| `ALBUM_TRACK_CODES` | dict | {트랙번호: 곡ID} | parse_album_data() |
| `ALBUM_TRACK_TITLES` | dict | {트랙번호: 곡명} | parse_album_data() |
| `PLAYLIST_NAME` | str | 플레이리스트 제목 | parse_playlist_data() |
| `PLAYLIST_TRACK_COUNT` | int | 플레이리스트 곡 수 | parse_playlist_data() |
| `TOTAL_ALBUM_COUNT` | int | 아티스트 앨범 총 수 | get_artist_albums() |
| `ARTIST_ALBUMS` | list | 앨범 ID 리스트 | get_artist_albums() |

---

## 7. 함수 레퍼런스

### 유틸리티 함수

| 함수 | 입력 | 출력 | 한줄 설명 |
|------|------|------|----------|
| `read_config()` | 없음 | ID, PW 전역 설정 | INI 파일에서 로그인 정보 로드 |
| `is_win()` | 없음 | True/None | Windows OS 여부 확인 |
| `rm_illegal_character(str)` | 문자열 | 정제된 문자열 | 파일명 불가 문자 → _ 치환 |
| `divider()` | 없음 | 화면 출력 | 터미널 너비 구분선 출력 |
| `remove()` | 없음 | 화면 효과 | 이전 줄 지우기 |
| `decode(str)` | URL인코딩 문자열 | 원본 | URL 디코딩 |
| `encode(str)` | 일반 문자열 | URL인코딩 | URL 인코딩 |
| `prettifyNUM(num)` | 숫자 | 2자리 문자열 | 1 → "01" 포맷팅 |
| `parse_code(url, type)` | URL, 유형명 | 숫자코드 | URL에서 ID 숫자 추출 |

### 서버 통신 함수

| 함수 | 입력 | 출력 | 한줄 설명 |
|------|------|------|----------|
| `login(username, password)` | ID, PW | 토큰 3개 (전역) | 지니 서버 로그인 |
| `parse_track_data(xgnm, bitrate)` | 곡코드, 비트레이트 | 스트리밍 URL (전역) | 곡의 다운로드 URL 획득 |
| `parse_album_data(axnm)` | 앨범코드 | 앨범 정보 (전역) | 앨범 메타데이터 수집 |
| `parse_artist_data(xxnm)` | 아티스트코드 | 아티스트명 (전역) | 아티스트 정보 수집 |
| `parse_playlist_data(seq)` | 시퀀스번호 | 플리 정보 (전역) | 플레이리스트 정보 수집 |
| `get_artist_albums(xxnm)` | 아티스트코드 | 앨범 목록 (전역) | 아티스트 전체 앨범 수집 |

### 다운로드 실행 함수

| 함수 | 입력 | 동작 | 저장 위치 |
|------|------|------|----------|
| `download_track(url, filename, taskname)` | URL, 파일명, 표시명 | 단일 곡 다운로드 | 지정 경로 |
| `download_album(axnm)` | 앨범코드 | 앨범 전체 다운로드 | 아티스트/앨범/ |
| `download_playlist(seq)` | 시퀀스번호 | 플리 전체 다운로드 | [Playlist] 이름/ |
| `download_artist(xxnm)` | 아티스트코드 | 전체 디스코그래피 | 아티스트/각앨범/ |
| `download_realtime_chart(start, end)` | 시작순위, 끝순위 | 차트 곡 다운로드 | [Genie TOP 200] 날짜/ |

### 검색 함수

| 함수 | 입력 | 동작 |
|------|------|------|
| `search_track(keyword, amount)` | 검색어, 결과수 | 곡 검색 → 선택 → 다운로드 |
| `search_album(keyword, amount)` | 검색어, 결과수 | 앨범 검색 → 선택 → 앨범 다운로드 |
| `search_artist(keyword, amount)` | 검색어, 결과수 | 아티스트 검색 → 선택 → 전체 다운로드 |

### 라우팅 함수

| 함수 | 입력 | 동작 |
|------|------|------|
| `parse_user_input(url)` | 지니 URL | URL 분석 → 유형별 다운로드 함수 호출 |
| `main()` | 없음 | 대화형 메뉴 표시 → 선택 처리 |

---

## 8. 파일/폴더 구조

```
genie/
├── genie-dl.py              # 메인 프로그램 (이 파일)
├── genie-dl-settings.ini    # 자동 생성되는 로그인 설정 파일
├── genie-dl.md              # 이 문서
├── genie-dl.mmd             # Mermaid 플로우차트
├── LICENSE                  # 라이선스
├── README.md                # GitHub용 README
├── requirements.txt         # pip 의존성 목록
├── utils/                   # 유틸리티 모듈
│   └── download.py          # 진행바 포함 파일 다운로드 모듈
└── downloads/               # [자동 생성] 다운로드된 음원 저장 폴더
    ├── 아티스트명/
    │   ├── [2021.03] 앨범명/
    │   │   ├── 01. 아티스트 - 곡제목.mp3
    │   │   ├── 02. 아티스트 - 곡제목.mp3
    │   │   └── ...
    │   └── [2022.01] 다른앨범/
    ├── [Playlist] 플레이리스트명/
    │   ├── 01. 아티스트 - 곡제목.mp3
    │   └── ...
    └── [Genie TOP 200] - 240330_14_00/
        ├── 01. 아티스트 - 곡제목.mp3
        └── ...
```

---

## 9. 사용법

### 설치

```bash
pip install requests pick questionary configparser
```

### 실행 예시

```bash
# 대화형 메뉴 (초보자 추천)
python genie-dl.py

# 특정 곡 다운로드
python genie-dl.py -i "https://genie.co.kr/detail/songInfo?xgnm=97835731"

# 앨범 전체 다운로드
python genie-dl.py -i "https://genie.co.kr/detail/albumInfo?axnm=81234567"

# 실시간 차트 1~50위 다운로드
python genie-dl.py -c 1-50

# FLAC(무손실) 포맷으로 다운로드
python genie-dl.py -f flac -i "URL"

# 24bit 고해상도 FLAC
python genie-dl.py -f flac24 -i "URL"

# 로그인 정보 재설정
python genie-dl.py --reset
```

### 대화형 메뉴 설명

```
=> Download Song / Album / Artist / Playlist   ← URL 직접 입력
   Download Real-Time Chart                     ← 차트 1~200위 전체 다운로드
   View Real-Time Chart                         ← 차트만 보기 (다운로드 없이)
   Search and Download Song                     ← 곡 이름 검색
   Search and Download Album                    ← 앨범 이름 검색
   Search and Download Artist                   ← 아티스트 이름 검색
   Exit                                         ← 종료
```

---

## 10. 알려진 이슈 및 개선점

### 버그

1. **main() 함수의 중복 조건**: `if selected == 0`과 `elif selected == 0`이 중복되어 두 번째 블록이 절대 실행되지 않음
2. **SyntaxWarning**: 정규표현식과 ASCII 아트에 raw string(`r'...'`)을 사용하지 않아 `\d`, `\/` 등이 Python 3.12+에서 경고 발생
3. **CD 2 이상 미지원**: `parse_album_data()`에서 다중 CD 앨범의 CD 2 이상 트랙을 무시함

### 보안

- `genie-dl-settings.ini`에 비밀번호가 평문 저장됨
- DEVICE_ID가 하드코딩되어 있음 (모든 사용자가 동일 기기로 인식될 수 있음)

### 개선 가능 사항

- 전역 변수 → dataclass 또는 함수 반환값으로 리팩토링
- 에러 처리 강화 (네트워크 장애, API 변경 등)
- 다운로드 재시도(retry) 로직 추가
- 동시 다운로드(concurrent) 지원으로 속도 향상
- ID3 태그(MP3 메타데이터) 자동 입력 (eyed3 활성화)

---

*이 문서는 genie-dl.py v1.0.5 코드를 기반으로 작성되었습니다.*
