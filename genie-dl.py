# ============================================================================
# GENIE-DL v1.0.5 - 지니뮤직 음원 다운로더
# ============================================================================
# 제작자: vank0n (SJJeon)
# 목적: 지니뮤직(genie.co.kr) 스트리밍 서비스에서 음원을 다운로드하는 CLI 도구
# 사용법: python genie-dl.py (대화형 메뉴) 또는 python genie-dl.py -i <URL> (직접 지정)
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# [1단계] 라이브러리 임포트 (Import)
# ──────────────────────────────────────────────────────────────────────────────
# 이 프로그램이 동작하기 위해 필요한 외부/내장 라이브러리들을 불러온다.
# 파이썬에서 import는 "다른 사람이 만든 도구를 빌려오는 것"과 같다.

import requests       # HTTP 요청을 보내는 라이브러리 (지니 서버 API 호출에 사용)
import json           # JSON(데이터 교환 형식) 처리 라이브러리 (API 응답 파싱)
import os             # 운영체제 관련 기능 (폴더 생성, 파일 존재 확인 등)
#import eyed3         # [비활성화] MP3 태그 편집 라이브러리 (ID3 태그 수정용, 현재 미사용)
import sys            # 시스템 관련 기능 (프로그램 강제 종료 sys.exit() 등)
import shutil         # 터미널 크기 확인 등 고급 파일 유틸리티
import re             # 정규표현식(Regular Expression) - 텍스트 패턴 매칭에 사용
import pathlib        # 파일 경로를 객체로 다루는 라이브러리 (경로 조합, 존재 확인)
import argparse       # 명령줄 인자(argument) 파싱 - 터미널에서 옵션을 받을 때 사용
import platform       # 운영체제 종류 확인 (Windows/Mac/Linux 구분)
import signal         # 시그널 처리 (Ctrl+C 같은 인터럽트 처리)
from datetime import datetime  # 현재 날짜/시간 가져오기
from datetime import date      # 오늘 날짜 가져오기
from pick import pick          # 터미널에서 화살표 키로 메뉴를 선택할 수 있게 해주는 라이브러리
import configparser            # INI 설정 파일을 읽고 쓰는 라이브러리
import questionary             # 터미널에서 예쁜 입력 프롬프트를 제공하는 라이브러리
from utils import download     # 로컬 utils 폴더의 download 모듈 (실제 파일 다운로드 담당)

# ──────────────────────────────────────────────────────────────────────────────
# [2단계] 명령줄 인자(Argument) 파서 설정
# ──────────────────────────────────────────────────────────────────────────────
# 사용자가 터미널에서 프로그램을 실행할 때 옵션을 붙여서 사용할 수 있게 한다.
# 예시:
#   python genie-dl.py -c 1-50         → 실시간 차트 1~50위 다운로드
#   python genie-dl.py -i <지니URL>    → 특정 곡/앨범/플레이리스트 다운로드
#   python genie-dl.py --reset         → 저장된 로그인 정보 초기화
#   python genie-dl.py -f flac         → FLAC(무손실) 포맷으로 다운로드

parser = argparse.ArgumentParser(description='\033[93mGENIE-DL by vank0n © 2021 vank0n (SJJeon) - All Rights Reserved.\033[0m',epilog="https://github.com/WHTJEON/genie-music-downloader")
parser.add_argument('-c', '--download-chart',default=None,help = "Download Genie TOP 200 Chart",metavar="RANGE")
# -c 옵션: 차트 범위 지정 (예: "1-100"이면 1위부터 100위까지 다운로드)
parser.add_argument('-i','--input',default=None,required=False,help = "Download Genie Song/Album/Playlist",metavar="URL")
# -i 옵션: 지니뮤직 URL을 직접 입력하여 다운로드
parser.add_argument('--reset',action='store_true',help="Reset Credentials")
# --reset 옵션: 저장된 아이디/비밀번호를 새로 입력받아 덮어쓰기
parser.add_argument('-f','--format',choices=["mp3", "flac", "flac24"],default='mp3')
# -f 옵션: 다운로드 포맷 선택 (mp3=320kbps, flac=무손실, flac24=24bit 무손실)
args = parser.parse_args()  # 위에서 정의한 옵션들을 실제로 파싱(해석)한다

# ──────────────────────────────────────────────────────────────────────────────
# [3단계] 전역 변수(Global Variables) 설정
# ──────────────────────────────────────────────────────────────────────────────
# 프로그램 전체에서 공통으로 사용하는 설정값들을 여기서 정의한다.
# 전역 변수는 어떤 함수에서든 읽을 수 있어서, 설정을 한 곳에서 관리할 수 있다.

# 포맷에 따른 비트레이트(음질)와 확장자 결정
if args.format == "mp3":
	BITRATE = 320       # MP3는 320kbps (가장 높은 MP3 음질)
	EXTENSION = "mp3"   # 저장 파일 확장자: .mp3
	
else:
	EXTENSION = "flac"  # FLAC은 무손실 압축 포맷, 확장자: .flac
	# flac이면 1000(CD급 무손실), flac24면 "24bit"(고해상도 무손실)
	BITRATE = 1000 if args.format == "flac" else "24bit"

INPUT_URL = args.input           # 사용자가 -i 옵션으로 입력한 URL (없으면 None)
SEARCH_AMOUNT = 20               # 검색 결과를 최대 20개까지 표시
DOWNLOAD_CHART = args.download_chart  # 사용자가 -c 옵션으로 입력한 차트 범위 (예: "1-100")
RESET_P = args.reset             # --reset 옵션 사용 여부 (True/False)
DEVICE_ID = "002ebf12-a125-5ddf-a739-67c3c5d20177"  # 지니 API 인증에 필요한 고유 기기 ID
# ↑ 지니뮤직 서버는 어떤 기기에서 요청하는지 확인한다. 이 값이 없으면 API 호출이 거부된다.

SCRIPT_PATH = str(pathlib.Path(__file__).parent.absolute())  # 이 스크립트(.py)가 위치한 폴더의 절대 경로
#SCRIPT_PATH = str(pathlib.Path.home())  # [대안] 사용자 홈 디렉토리를 기본 경로로 사용 (현재 비활성화)
OUTPUT_PATH = SCRIPT_PATH + "/downloads/"  # 다운로드된 음원이 저장될 폴더 경로


# ──────────────────────────────────────────────────────────────────────────────
# [4단계] 설정 파일 읽기/생성 함수
# ──────────────────────────────────────────────────────────────────────────────
def read_config():
	"""
	[함수] read_config() - 로그인 설정 파일을 읽거나 새로 생성한다.
	
	동작 흐름:
	  1. genie-dl-settings.ini 파일이 존재하면 → 저장된 ID/PW를 읽어온다
	  2. 파일이 없으면 → 사용자에게 ID/PW를 물어보고 파일을 새로 생성한다
	  3. --reset 옵션이 켜져있으면 → 무조건 ID/PW를 새로 입력받아 덮어쓴다
	
	결과:
	  - 전역 변수 ID, PW에 지니뮤직 로그인 정보가 저장된다
	  - genie-dl-settings.ini 파일이 생성/갱신된다
	"""
	global ID, PW  # 이 함수 안에서 설정한 ID, PW를 다른 함수에서도 쓸 수 있게 전역으로 선언
	config = configparser.ConfigParser()  # INI 파일을 읽고 쓸 수 있는 파서 객체 생성
	config_file = "%s/genie-dl-settings.ini"%SCRIPT_PATH  # 설정 파일의 전체 경로
	
	if RESET_P != True:  # --reset 옵션이 꺼져있는 경우 (일반 실행)
		if pathlib.Path(config_file).is_file():  # 설정 파일이 이미 존재하는지 확인
			# 기존 설정 파일에서 ID와 비밀번호를 읽어온다
			config.read(SCRIPT_PATH+'/genie-dl-settings.ini')
			ID = config['DEFAULT']['genie_id']        # 저장된 지니 아이디
			PW = config['DEFAULT']['genie_password']   # 저장된 지니 비밀번호
			
		else:
			# 설정 파일이 없으면: 처음 실행하는 사용자에게 로그인 정보를 요청한다
			print("No config file is found. Creating a new one...")
			ID = questionary.text("Enter your Genie ID: ",qmark=">").ask()      # 아이디 입력 프롬프트
			PW = questionary.password("Enter Genie Password: ",qmark=">").ask()  # 비밀번호 입력 (***로 가려짐)
			
			# 입력받은 정보를 config에 저장
			config['DEFAULT']['genie_id'] = ID
			config['DEFAULT']['genie_password'] = PW
	
			# INI 파일로 저장하여 다음 실행 때 다시 입력하지 않아도 되게 한다
			with open(config_file, 'w') as configfile:
				config.write(configfile)
			print("Successfully created config file!")
	else:
		# --reset 옵션이 켜져있으면: 기존 설정을 무시하고 새로 입력받는다
		print("Resetting Config File..")
		ID = questionary.text("Enter your Genie ID: ",qmark=">").ask()
		PW = questionary.password("Enter Genie Password: ",qmark=">").ask()
		config['DEFAULT']['genie_id'] = ID
		config['DEFAULT']['genie_password'] = PW
		
		with open(config_file, 'w') as configfile:
			config.write(configfile)
		print("Successfully resetted config file!")
		
		
# ──────────────────────────────────────────────────────────────────────────────
# [5단계] 유틸리티 함수들 (Utility Functions)
# ──────────────────────────────────────────────────────────────────────────────
# 프로그램 곳곳에서 반복적으로 사용되는 작은 도우미 함수들이다.
# 이런 함수들을 미리 만들어두면 코드가 깔끔해지고 유지보수가 쉬워진다.

def is_win():
	"""
	[함수] is_win() - 현재 운영체제가 Windows인지 확인한다.
	
	입력: 없음
	결과: Windows면 True 반환, 그 외(Mac/Linux)면 None 반환
	용도: Windows에서는 파일 이름에 쓸 수 없는 특수문자가 더 많아서 구분이 필요하다.
	"""
	if platform.system() == 'Windows':
		return True

def rm_illegal_character(str):
	"""
	[함수] rm_illegal_character(str) - 파일 이름에 사용할 수 없는 특수문자를 제거한다.
	
	입력: str (문자열) - 예: '아이유 - Love wins all / Remix'
	결과: 특수문자가 밑줄(_)로 바뀐 문자열 반환 - 예: '아이유 - Love wins all _ Remix'
	
	이유: 운영체제마다 파일 이름에 쓸 수 없는 문자가 다르다.
	  - Windows: \ / : * ? " > < | 사용 불가
	  - Mac/Linux: : / 사용 불가
	이 문자들이 포함된 곡 제목으로 파일을 저장하면 오류가 나므로, 밑줄로 치환한다.
	"""
	if is_win():
		return re.sub('[\/:*?"><|]','_',str)  # Windows: 8개 특수문자를 _로 치환
	else:
		return re.sub('[:/]', '_', str)        # Mac/Linux: 2개 특수문자만 _로 치환

def divider():
	"""
	[함수] divider() - 터미널 화면 너비에 맞는 구분선(--------)을 출력한다.
	
	입력: 없음
	결과: 터미널에 "-" 문자로 이루어진 수평선이 출력된다
	용도: 메뉴나 정보 출력 사이에 시각적 구분을 주기 위해 사용한다.
	"""
	count = int(shutil.get_terminal_size().columns)  # 터미널의 가로 폭(열 수)을 가져온다
	count = count - 1  # 가로 폭보다 1칸 적게 (줄 바꿈 시 깨짐 방지)
	print ('-' * count)  # '-'를 터미널 너비만큼 반복 출력
	
def remove(): 
	"""
	[함수] remove() - 터미널에서 이전 줄을 빈 칸으로 덮어써서 지우는 효과를 낸다.
	
	입력: 없음
	결과: 터미널의 이전 줄이 공백으로 덮어씌워진다
	용도: 다운로드 진행률 표시 등에서 이전 출력을 지울 때 사용한다.
	참고: \033[A는 ANSI 이스케이프 코드로 "커서를 한 줄 위로 이동"하라는 명령이다.
	"""
	count = int(shutil.get_terminal_size().columns)
	count = count - 1
	blank =' ' * count  # 터미널 너비만큼의 공백 문자열 생성
	print ("\033[A%s\033[A"%blank)  # 커서를 위로 올리고 → 공백으로 덮고 → 다시 위로 올린다

def decode(str):
	"""
	[함수] decode(str) - URL 인코딩된 문자열을 원래 한글/특수문자로 되돌린다.
	
	입력: str - URL 인코딩된 문자열 (예: '%EC%95%84%EC%9D%B4%EC%9C%A0')
	결과: 디코딩된 원본 문자열 (예: '아이유')
	용도: 지니 API가 한글을 URL 인코딩 형태로 반환할 때 원래 문자로 복원하기 위해 사용한다.
	"""
	return requests.utils.unquote(str)

def encode(str):
	"""
	[함수] encode(str) - 한글/특수문자를 URL에 안전한 형태로 인코딩한다.
	
	입력: str - 일반 문자열 (예: '아이유')
	결과: URL 인코딩된 문자열 (예: '%EC%95%84%EC%9D%B4%EC%9C%A0')
	용도: 검색어를 API URL에 포함시킬 때 사용한다. (한글은 URL에 직접 넣을 수 없음)
	"""
	return requests.utils.quote(str)

def prettifyNUM(num):
	"""
	[함수] prettifyNUM(num) - 한 자리 숫자를 두 자리로 포맷한다.
	
	입력: num (숫자) - 예: 1, 5, 12
	결과: 한 자리면 앞에 0을 붙임 (예: 1→"01", 5→"05"), 두 자리 이상이면 그대로
	용도: 파일 이름에 트랙 번호를 넣을 때 정렬이 잘 되도록 사용한다.
	      "01. 노래.mp3"처럼 만들어야 파일 탐색기에서 순서가 맞다.
	"""
	if len(str(num)) == 1:    # 숫자를 문자열로 바꿔서 길이가 1이면 (한 자리 수)
		num = "%02d"%num	  # %02d = 최소 2자리, 빈 자리는 0으로 채움
	return num

# [비활성화된 함수] rename() - MP3 파일의 ID3 태그를 읽어서 파일명을 자동 변경하는 기능
# eyed3 라이브러리가 필요하지만 현재 import도 주석처리되어 있음
#def rename(file):
#	f = eyed3.load(file)
#	fnew = "%s. %s - %s.%s"%(prettifyNUM(f.tag.track_num[0]),f.tag.artist, f.tag.title,EXTENSION)
#	os.rename(file,fnew)
	
# ──────────────────────────────────────────────────────────────────────────────
# [6단계] URL 파싱 및 다운로드 실행 함수
# ──────────────────────────────────────────────────────────────────────────────

def parse_code(url,type):
	"""
	[함수] parse_code(url, type) - URL에서 숫자 코드(ID)를 추출한다.
	
	입력:
	  - url (문자열): 지니뮤직 URL (예: "https://genie.co.kr/detail/songInfo?xgnm=12345678")
	  - type (문자열): URL 종류 설명 (예: "Track", "Album", "Artist", "Playlist")
	결과: URL에서 추출한 숫자 코드 문자열 반환 (예: "12345678")
	실패 시: 숫자가 없으면 에러 메시지 출력 후 프로그램 종료
	
	원리: 지니 URL에는 항상 고유 숫자 ID가 포함되어 있다.
	      정규표현식 \d+로 연속된 숫자를 모두 찾아서 첫 번째 것을 사용한다.
	"""
	match = re.findall('\d+',url)  # URL에서 연속된 숫자를 모두 찾는다 (리스트로 반환)
	try:
		CODE = match[0]  # 찾은 숫자 중 첫 번째를 사용 (이것이 지니의 고유 ID)
		print("[info] URL Type: %s"%type)  # 어떤 유형의 URL인지 사용자에게 알려준다
		return CODE
	
	except IndexError:  # 숫자가 하나도 없으면 IndexError가 발생
		print("[error] Invalid URL: %s"%url)
		divider()
		sys.exit(1)  # 프로그램 강제 종료 (에러 코드 1)
		
def download_track(url,filename,taskname):
	"""
	[함수] download_track(url, filename, taskname) - 실제 음원 파일을 다운로드한다.
	
	입력:
	  - url (문자열): 음원 스트리밍 URL (지니 서버에서 받아온 직접 링크)
	  - filename (문자열): 저장할 파일 경로+이름 (확장자 제외)
	  - taskname (문자열): 다운로드 진행바에 표시할 곡 이름
	결과: 음원 파일이 filename.mp3 (또는 .flac)으로 저장된다
	
	참고: block_size=512는 한 번에 512바이트씩 다운로드한다는 의미 (작은 단위로 나눠 받음)
	"""
	download.download(url,file_name="%s.%s"%(filename,EXTENSION),name=taskname,block_size=512)
		
# ──────────────────────────────────────────────────────────────────────────────
# [7단계] 서버 통신 함수들 (Server Communication)
# ──────────────────────────────────────────────────────────────────────────────
# 지니뮤직 서버 API와 통신하는 핵심 함수들이다.
# 모든 기능의 시작점은 로그인이며, 로그인 후 받는 토큰으로 데이터를 가져온다.

def login(username,password):
	"""
	[함수] login(username, password) - 지니뮤직 서버에 로그인한다.
	
	입력:
	  - username (문자열): 지니뮤직 아이디
	  - password (문자열): 지니뮤직 비밀번호
	결과:
	  - 성공 시: 전역 변수 user_num, user_token, stm_token에 인증 토큰이 저장된다
	  - 실패 시: 에러 메시지 출력 후 프로그램 종료
	
	동작 흐름:
	  1. 아이디/비밀번호를 POST 방식으로 지니 로그인 API에 전송
	  2. 서버가 JSON 응답을 반환 (성공=RetCode "0", 실패=그 외)
	  3. 성공하면 응답에서 사용자 번호(MemUno), 인증 토큰(MemToken),
	     스트리밍 토큰(STM_TOKEN)을 추출하여 전역 변수에 저장
	
	이 토큰들은 이후 음원 스트리밍 URL을 받아올 때 인증 수단으로 사용된다.
	(지니 유료 회원만 고음질 스트리밍이 가능하므로 로그인이 필수)
	"""
	global user_num,user_token,stm_token  # 토큰을 전역으로 저장 (다른 함수에서 사용하기 위해)
	
	# 로그인에 필요한 자격 증명(credentials) 데이터 구성
	credentials = {
		"uxd": username,  # 아이디 (uxd는 지니 API가 사용하는 파라미터 이름)
		"uxx": password   # 비밀번호 (uxx는 지니 API가 사용하는 파라미터 이름)
	}
	
	# POST 요청으로 로그인 API를 호출하고, JSON 응답을 파싱한다
	response = requests.post("https://app.genie.co.kr/member/j_Member_Login.json",data=credentials).json()
	
	if response['Result']['RetCode'] != "0":  # RetCode가 "0"이 아니면 로그인 실패
		LOGIN = False
		divider()
		print("[error] Authentication failed. Check your credentials.")
		divider()
		sys.exit(1)
	else:
		LOGIN = True  # 로그인 성공
	
	# 로그인 성공 시 응답에서 필요한 토큰 3개를 추출하여 전역 변수에 저장
	user_num = response['DATA0']['MemUno']       # 사용자 고유 번호 (회원 식별용)
	user_token = response['DATA0']['MemToken']   # 사용자 인증 토큰 (API 호출 시 신분증 역할)
	stm_token = response['DATA0']['STM_TOKEN']   # 스트리밍 토큰 (음원 URL 요청 시 필요)
	
# ──────────────────────────────────────────────────────────────────────────────
# [8단계] 데이터 파싱 함수들 (API 응답 → 데이터 추출)
# ──────────────────────────────────────────────────────────────────────────────
# 지니 API에서 받은 JSON 응답을 파싱하여 필요한 정보를 추출한다.
# 각 함수는 플레이리스트, 앨범, 아티스트, 개별 곡 정보를 각각 담당한다.

def parse_playlist_data (seq):
	"""
	[함수] parse_playlist_data(seq) - 플레이리스트 정보를 지니 API에서 가져온다.
	
	입력: seq (문자열) - 플레이리스트의 고유 시퀀스 번호 (예: "12345")
	결과: 전역 변수에 저장된다:
	  - PLAYLIST_NAME: 플레이리스트 제목 (예: "임상이 선별한 봄 노래")
	  - PLAYLIST_TRACK_COUNT: 플레이리스트에 포함된 총 곡 수
	  - PLAYLIST_TRACK_CODES: {인덱스: 곡ID} 딕셔너리
	  - PLAYLIST_TRACK_TITLES: {인덱스: 곡명} 딕셔너리
	"""
	global PLAYLIST_NAME, PLAYLIST_TRACK_COUNT, PLAYLIST_TRACK_CODES, PLAYLIST_TRACK_TITLES
	
	# 플레이리스트 정보 API 호출 (seq 번호로 특정 플레이리스트를 지정)
	api_url = "https://app.genie.co.kr/Iv3/playlist/infosong.json?seq={}".format(seq)
	response = requests.get(api_url).json()  # GET 요청 후 JSON 파싱
	
	try:
		# 응답 JSON에서 플레이리스트 제목과 곡 수를 추출
		PLAYLIST_NAME = decode(response['DATASET']['DATA_INFO']['DATA']['PLM_TITLE'])
		PLAYLIST_TRACK_COUNT = int(decode(response['DATASET']['DATA_INFO']['DATA']['SONG_CNT']))
		
		# 각 곡의 ID와 제목을 저장할 딕셔너리 초기화
		PLAYLIST_TRACK_CODES = {}   # {순번: 곡ID}
		PLAYLIST_TRACK_TITLES = {}  # {순번: 곡명}
		
		# 플레이리스트의 모든 곡을 순회하며 ID와 제목 수집
		for i in range (0,PLAYLIST_TRACK_COUNT,1):
			PLAYLIST_TRACK_CODES [i] = int(decode(response['DATASET']['DATA_SONG']['DATA'][i]['SONG_ID']))
			PLAYLIST_TRACK_TITLES [i] = decode(response['DATASET']['DATA_SONG']['DATA'][i]['SONG_NAME'])
	
	except KeyError:  # JSON 구조가 예상과 다를 때 (잘못된 URL 또는 비공개 플레이리스트)
		print("[error] Unable to fetch playlist data. Check your URL")
		divider()
		sys.exit(1)
		
def parse_album_data(axnm):
	"""
	[함수] parse_album_data(axnm) - 앨범 정보를 지니 API에서 가져온다.
	
	입력: axnm (문자열) - 앨범 고유 코드 (예: "81234567")
	결과: 전역 변수에 저장된다:
	  - ALBUM_NAME: 앨범명 (예: "LILAC")
	  - ALBUM_ARTIST: 아티스트명 (예: "아이유")
	  - ALBUM_DATE: 날짜 문자열 (예: "[2021.03]")
	  - ALBUM_TYPE: 앨범 유형 (예: "정규", "미니", "싱글")
	  - ALBUM_TRACK_COUNT: 앨범의 총 트랙 수
	  - ALBUM_TRACK_CODES: {트랙번호: 곡ID} 딕셔너리
	  - ALBUM_TRACK_TITLES: {트랙번호: 곡명} 딕셔너리
	
	특이사항: CD가 여러 장인 앨범의 경우, 현재 CD 1의 곡만 처리한다
	           (CD 2 이상의 곡은 무시됨 → 개선 필요)
	"""
	global ALBUM_TRACK_CODES,ALBUM_TRACK_TITLES,ALBUM_NAME,ALBUM_TRACK_COUNT, ALBUM_DATE, ALBUM_TYPE, ALBUM_ARTIST
	
	# 앨범 정보 API 호출
	response = requests.get("https://info.genie.co.kr/info/album?axnm={}".format(axnm)).json()
	
	try:
		# 앨범 기본 정보 추출
		ALBUM_NAME = response['album_info']['album_name']       # 앨범 제목
		ALBUM_ARTIST = response['album_info']['artist_name']    # 앨범 아티스트
		
		# 발매일을 "[YYYY.MM]" 포맷으로 변환 (폴더명에 사용)
		ALBUM_DATE_RAW = str(response['album_info']['album_release_dt'])  # 예: "20210325"
		year = ALBUM_DATE_RAW[0:4]    # 앞 4자리 = 년도 (예: "2021")
		month = ALBUM_DATE_RAW[4:6]   # 5~6번째 = 월 (예: "03")
		ALBUM_DATE = "[%s.%s]"%(year,month)  # 예: "[2021.03]"
		
		ALBUM_TYPE = decode(response['album_info']['album_type'])  # 앨범 유형
		ALBUM_TRACK_COUNT = len(response['album_song_list'])       # 앨범의 전체 곡 수
		
		# 각 트랙의 코드와 제목을 저장할 딕셔너리
		ALBUM_TRACK_CODES = {}   # {트랙번호: 곡ID}
		ALBUM_TRACK_TITLES = {}  # {트랙번호: 곡명}
		
		# 모든 트랙을 순회
		for i in range (0,ALBUM_TRACK_COUNT,1):
			ALBUM_CD = int(response['album_song_list'][i]['album_cd_no'])  # 이 곡이 CD 몇 번에 속하는지
			
			if ALBUM_CD == 1:  # CD 1의 곡만 처리 (CD가 나눠져있는 경우 임시 처리.. 개선필요)
				# 트랙 번호를 key로, 곡 ID와 제목을 각각 저장
				ALBUM_TRACK_CODES[int(response['album_song_list'][i]['album_track_no'])]=response['album_song_list'][i]['song_id']
				ALBUM_TRACK_TITLES[int(response['album_song_list'][i]['album_track_no'])]=response['album_song_list'][i]['song_name']
			else: 
				# CD 2 이상의 곡은 무시하고, 현재까지 수집된 곡 수를 전체 개수로 설정
				current_count = len(ALBUM_TRACK_CODES)
#				ALBUM_TRACK_CODES[i+1]=response['album_song_list'][i]['song_id']
#				ALBUM_TRACK_TITLES[i+1]=response['album_song_list'][i]['song_name']
				ALBUM_TRACK_COUNT = current_count  # CD 1의 곡 수만으로 갱신
		
		print("[info] Found Album: %s (%s) (%s tracks)"%(ALBUM_NAME,ALBUM_ARTIST,ALBUM_TRACK_COUNT))
		
	except KeyError:
		print("[error] Unable to fetch album data. Check your URL")
		divider()
		sys.exit(1)

def parse_artist_data(xxnm):
	"""
	[함수] parse_artist_data(xxnm) - 아티스트 정보를 지니 API에서 가져온다.
	
	입력: xxnm (문자열) - 아티스트 고유 코드 (예: "20001234")
	결과:
	  - 전역 변수 ARTIST_NAME_FIX에 아티스트명 저장
	  - 반환값으로도 아티스트명을 돌려준다
	
	_FIX가 붙은 이유: parse_track_data()에서도 ARTIST_NAME을 설정하는데,
	앨범 단위 다운로드 시 아티스트명이 덮어쓰여지지 않도록 별도 변수를 사용한다.
	"""
	global ARTIST_NAME_FIX
	try:
		# 아티스트 정보 API 호출
		response = requests.get("https://info.genie.co.kr/info/artist?xxnm={}".format(xxnm)).json()
		ARTIST_NAME_FIX = response['artist_info']['artist_name']  # 아티스트명 추출
		print("[info] Found Artist: %s"%(ARTIST_NAME_FIX))
		return ARTIST_NAME_FIX
	
	except KeyError:
		print("[error] Unable to fetch artist data. Check your URL")
		divider()
		sys.exit(1)
		
def parse_track_data(xgnm,bitrate):
	"""
	[함수] parse_track_data(xgnm, bitrate) - 개별 곡의 스트리밍 정보를 가져온다.
	
	*** 코드의 핵심 함수 - 실제 다운로드 URL을 획득하는 가장 중요한 함수! ***
	
	입력:
	  - xgnm (문자열): 곡 고유 코드 (예: "97835731")
	  - bitrate (숫자 또는 문자열): 음질 설정
	    - 320 = MP3 320kbps
	    - 1000 = FLAC 무손실
	    - "24bit" = FLAC 24bit 고해상도
	결과:
	  - 성공 시: 전역 변수에 저장된다:
	    - ARTIST_NAME: 아티스트명
	    - SONG_NAME: 곡 제목
	    - DOWNLOAD_URL: 실제 음원 스트리밍 URL (이것으로 파일을 다운로드!)
	    - IS_VALID = True
	  - 실패 시: IS_VALID = False (이용 불가 곡)
	
	동작: 로그인으로 얻은 user_num, user_token, stm_token을 넣어서
	       스트리밍 서버에 요청하면, 서버가 실제 음원 파일의 URL을 반환해준다.
	"""
	global ARTIST_NAME,SONG_NAME,DOWNLOAD_URL,IS_VALID
	
	# 스트리밍 정보 API 호출 - 모든 인증 정보를 파라미터로 전달
	# xgnm=곡ID, bitrate=음질, unm=사용자번호, uxtk=토큰, stk=스트리밍토큰, udid=기기ID
	response = requests.get("https://stm.genie.co.kr/player/j_StmInfo.json?xgnm={}&bitrate={}&app_stm_type=normal&unm={}&uxtk={}&vmd=A&svc=DI&stk={}&udid={}&itn=Y&mts=Y&apvn=50101".format(xgnm,bitrate,user_num,user_token,stm_token,DEVICE_ID)).json()
	SUCCESS = response['Result']['RetMsg']  # 응답 메시지 (성공/실패 여부)

	try:
		# 응답 데이터에서 곡 정보와 다운로드 URL 추출
		DATA = response['DataSet']['DATA'][0]  # 첫 번째 데이터 항목
		SONG_NAME = decode(DATA['SONG_NAME'])            # 곡 제목 (디코딩)
		ARTIST_NAME = decode(DATA['ARTIST_NAME'])        # 아티스트명 (디코딩)
		DOWNLOAD_URL = decode(DATA['STREAMING_MP3_URL']) # 실제 음원 스트리밍 URL!
		IS_VALID = True  # 다운로드 가능한 곡임을 표시
		return DOWNLOAD_URL
	
	except IndexError:
		# DATA 배열이 비어있음 = 이 곡은 스트리밍 제공이 되지 않는 곡 (저작권 등)
		IS_VALID = False
		
	except KeyError:
		print("[error] Unable to fetch track data. Check your URL")
		divider()
		sys.exit(1)
	
	except:  # 그 외 예상치 못한 에러가 나면 응답 전체를 출력하여 디버깅에 도움을 준다
		print(response)
		
# ──────────────────────────────────────────────────────────────────────────────
# [9단계] 다운로드 실행 함수들 (Download Executors)
# ──────────────────────────────────────────────────────────────────────────────
# 위의 파싱 함수들로 수집한 데이터를 사용하여 실제 파일 다운로드를 실행하는 함수들이다.
# 각 함수는 폴더 생성 → 곡 순회 → 개별 다운로드 순으로 동작한다.

def get_artist_albums(xxnm):
	"""
	[함수] get_artist_albums(xxnm) - 특정 아티스트의 전체 앨범 목록을 가져온다.
	
	입력: xxnm (문자열) - 아티스트 고유 코드
	결과: 전역 변수에 저장된다:
	  - TOTAL_ALBUM_COUNT: 전체 앨범 수
	  - ARTIST_ALBUMS: 앨범 ID 리스트 [앨범ID1, 앨범ID2, ...]
	
	파라미터 pgsize=500: 최대 500개 앨범까지 한 번에 가져온다
	(500개 이상의 앨범을 가진 아티스트는 극히 드문)
	"""
	global TOTAL_ALBUM_COUNT,ARTIST_ALBUMS
	api_url = "https://app.genie.co.kr/song/j_ArtistAlbumList.json?pg=1&pgsize=500&xxnm={}&otype=newest&atype=all&mts=Y".format(xxnm)
	response = requests.get(api_url).json()
	try:
		TOTAL_ALBUM_COUNT = int(response['PageInfo']['TotCount'])  # 전체 앨범 수
		ARTIST_ALBUMS = []  # 앨범 ID들을 담을 리스트
		for i in range (0,TOTAL_ALBUM_COUNT,1):
			ALBUM_CODE = response['DataSet']['DATA'][i]['ALBUM_ID']  # 각 앨범의 고유 ID
			ARTIST_ALBUMS.append(ALBUM_CODE)  # 리스트에 추가
	except KeyError:
		print("The following artist is unavailable to fetch albums")
		sys.exit(1)
			
def download_album(axnm):
	"""
	[함수] download_album(axnm) - 앨범 전체 곡을 다운로드한다.
	
	입력: axnm (문자열) - 앨범 고유 코드
	동작 흐름:
	  1. parse_album_data()로 앨범 정보를 찾고
	  2. "아티스트/[날짜] 앨범명/" 폴더 구조로 저장 경로 생성
	  3. 각 트랙의 스트리밍 URL을 받아서 다운로드
	결과: downloads/아티스트/[날짜] 앨범명/ 폴더에 음원 파일 저장
	
	파일명 형식: "01. 아티스트 - 곡제목.mp3"
	"""
	parse_album_data(axnm)  # 먼저 앨범 정보를 API에서 가져온다
	k = 0  # 다운로드 진행 카운터
	
	# 다운로드 경로 생성: downloads/아티스트/[2021.03] LILAC/
	DOWNLOAD_PATH = OUTPUT_PATH+"%s/%s %s/"%(rm_illegal_character(ALBUM_ARTIST),ALBUM_DATE,rm_illegal_character(ALBUM_NAME))
	if not os.path.exists(DOWNLOAD_PATH):  # 폴더가 없으면 생성
		os.makedirs(DOWNLOAD_PATH)
	
	print("[info] Downloading Tracks of [%s]\n"%ALBUM_NAME)
	
	# 트랙 1번부터 마지막까지 순회하며 다운로드
	for i in range (1,ALBUM_TRACK_COUNT+1,1):
		k = k + 1
		try:
			parse_track_data(ALBUM_TRACK_CODES[i], BITRATE)  # 이 곡의 스트리밍 URL 받아오기
			if IS_VALID == False:
				# 스트리밍 제공이 되지 않는 곡은 건너ᄐ다
				print("%s. Track Unavailable. Skipping Download"%i)
			else:
				# 파일명: "01. 아티스트 - 곡제목" (특수문자 제거)
				f = rm_illegal_character("%s. %s - %s"%(prettifyNUM(i),ARTIST_NAME,str(ALBUM_TRACK_TITLES[i])))
				filename = DOWNLOAD_PATH+f
				taskname = "%s. %s"%(i,ALBUM_TRACK_TITLES[i])  # 진행바에 표시할 이름
				download_track(DOWNLOAD_URL,filename,taskname)  # 실제 다운로드 실행!
		except KeyError:
			pass  # 트랙 번호가 누락된 경우 건너ᄐ다

def download_playlist(seq):
	"""
	[함수] download_playlist(seq) - 플레이리스트 전체 곡을 다운로드한다.
	
	입력: seq (문자열) - 플레이리스트 고유 시퀀스 번호
	동작 흐름:
	  1. parse_playlist_data()로 플레이리스트 정보를 찾고
	  2. "[Playlist] 플레이리스트명/" 폴더 생성
	  3. 각 곡의 스트리밍 URL을 받아서 다운로드
	결과: downloads/[Playlist] 플레이리스트명/ 폴더에 음원 파일 저장
	"""
	parse_playlist_data(seq)
	print("[info] Downloading Playlist: %s (%s tracks)\n"%(PLAYLIST_NAME,PLAYLIST_TRACK_COUNT))
	
	# 다운로드 경로 생성: downloads/[Playlist] 플레이리스트명/
	DOWNLOAD_PATH = OUTPUT_PATH+"[Playlist] %s/"%PLAYLIST_NAME.replace(":","-")
	if not os.path.exists(DOWNLOAD_PATH):
		os.makedirs(DOWNLOAD_PATH)
	
	# 플레이리스트의 모든 곡을 순서대로 다운로드
	for i in range (0, PLAYLIST_TRACK_COUNT,1):
		parse_track_data (PLAYLIST_TRACK_CODES[i], BITRATE)
		if IS_VALID == False:
			print("%s. Track Unavailable. Skipping Download"%i)
		else:
			# 파일명: "01. 아티스트 - 곡제목"
			f = "%s. %s - %s"%(prettifyNUM(i+1),ARTIST_NAME,rm_illegal_character(str(PLAYLIST_TRACK_TITLES[i])))
			filename = DOWNLOAD_PATH+f
			taskname = "%s. %s"%(i+1,PLAYLIST_TRACK_TITLES[i])
			download_track(DOWNLOAD_URL,filename,taskname)

	
def download_artist(xxnm):
	"""
	[함수] download_artist(xxnm) - 아티스트의 전체 디스코그래피(모든 앨범)를 다운로드한다.
	
	입력: xxnm (문자열) - 아티스트 고유 코드
	동작 흐름:
	  1. get_artist_albums()로 아티스트의 모든 앨범 ID를 수집
	  2. parse_artist_data()로 아티스트 이름을 확인
	  3. 각 앨범에 대해 download_album()을 내부적으로 호출하여 다운로드
	결과: downloads/아티스트/ 하위에 모든 앨범 폴더가 생성됨
	
	예시: download_artist("아이유") → 아이유의 모든 앨범을 한 번에 다운로드
	"""
	get_artist_albums(xxnm)    # 앨범 목록 수집
	parse_artist_data(xxnm)     # 아티스트 이름 확인
	k = 0  # 앨범 순번 카운터
	
	# 앨범 목록을 순회하며 하나씩 다운로드
	for ALBUM in ARTIST_ALBUMS:
		k = k + 1
		print("[info] Downloading %s's Albums (%s/%s)"%(ARTIST_NAME_FIX,k,TOTAL_ALBUM_COUNT))
		download_album(ALBUM)  # 앨범 단위 다운로드 실행
		if k != TOTAL_ALBUM_COUNT:  # 마지막 앨범이 아니면 구분선 출력
			divider()
		
# ──────────────────────────────────────────────────────────────────────────────
# [10단계] 실시간 차트 기능 (Real-Time Chart)
# ──────────────────────────────────────────────────────────────────────────────
# 지니뮤직 실시간 TOP 200 차트를 조회하거나 다운로드하는 기능이다.
		
def print_realtime_chart (start,end):
	"""
	[함수] print_realtime_chart(start, end) - 실시간 차트를 터미널에 출력한다 (다운로드 없이 보기만).
	
	입력:
	  - start (숫자): 시작 순위 (예: 1)
	  - end (숫자): 끝 순위 (예: 200)
	결과: 터미널에 "순위. 아티스트 - 곡명" 형식으로 차트 출력
	
	예시 출력:
	  [Genie Realtime Chart for 2024.03.30 14:00]
	  1. 아이유 - Love wins all
	  2. 뉴진스 - Supernatural
	  ...
	"""
	api_url = "https://app.genie.co.kr/chart/j_RealTimeRankSongList.json?pg=1&pgsize=200"
	response = requests.get(api_url).json()
	
	# 현재 날짜와 시간을 차트 제목에 포함
	now = datetime.now()
	today = date.today()
	d1 = today.strftime("%Y.%m.%d")     # 예: "2024.03.30"
	current_hour = now.strftime("%H")    # 예: "14"
	CHART_NAME = "[Genie Realtime Chart for %s %s:00]\n"%(d1,current_hour)
	CHART = {}  # {순위: "순위. 아티스트 - 곡명"} 형식으로 저장할 딕셔너리
	print(CHART_NAME)
	
	# 지정된 범위의 차트 데이터를 수집
	for i in range (start-1,end,1):  # start-1인 이유: 파이썬 인덱스는 0부터, 차트는 1부터
		TRACK_NAME = decode(response["DataSet"]['DATA'][i]['SONG_NAME'])
		ARTIST_NAME = decode(response["DataSet"]['DATA'][i]['ARTIST_NAME'])
		string = "%s. %s - %s"%(i+1,ARTIST_NAME,TRACK_NAME)
		CHART [i+1] = string
		
	# 수집한 차트 데이터를 순서대로 출력
	for i in range (start,end+1,1):	
		print(CHART[i])
		

def download_realtime_chart(start,end):
	"""
	[함수] download_realtime_chart(start, end) - 실시간 차트의 곡들을 다운로드한다.
	
	입력:
	  - start (숫자): 시작 순위 (예: 1)
	  - end (숫자): 끝 순위 (예: 200)
	동작 흐름:
	  1. 실시간 차트 API에서 지정 범위의 곡 ID들을 수집
	  2. "[Genie TOP 200] - YYMMDD_HH_00/" 폴더 생성
	  3. 각 곡을 순번대로 다운로드
	결과: downloads/[Genie TOP 200] - 240330_14_00/ 폴더에 음원 파일 저장
	
	예: python genie-dl.py -c 1-50 → 1위~50위까지 다운로드
	"""
	api_url = "https://app.genie.co.kr/chart/j_RealTimeRankSongList.json?pg=1&pgsize=200"
	response = requests.get(api_url).json()
	CHART_TRACK_CODES = []  # 다운로드할 곡 ID들의 리스트
	
	# 지정된 범위의 곡 ID를 수집
	for i in range (start-1,end,1):
		TRACK_CODE = response["DataSet"]['DATA'][i]['SONG_ID']
		CHART_TRACK_CODES.append(TRACK_CODE)
	
	# 폴더명용 시간 정보 생성
	now = datetime.now()
	today = date.today()
	d1 = today.strftime("%y%m%d")      # 예: "240330"
	current_hour = now.strftime("%H")   # 예: "14"
	
	CHART_NAME = "%s %s:00"%(d1,current_hour)
	print("[info] Downloading Real-Time Chart for %s (%s~%s)\n"%(CHART_NAME,start,end))
	
	k = 0  # 다운로드 순번 카운터
	# 다운로드 경로: downloads/[Genie TOP 200] - 240330_14_00/
	DOWNLOAD_PATH = OUTPUT_PATH+"[Genie TOP 200] - %s/"%CHART_NAME.replace(":","_").replace(" ","_")
	if not os.path.exists(DOWNLOAD_PATH):
		os.makedirs(DOWNLOAD_PATH)
	
	# 수집한 모든 곡을 순번대로 다운로드
	for tracks in CHART_TRACK_CODES:
		k = k + 1
		parse_track_data(tracks, BITRATE)  # 스트리밍 URL 획득
		if IS_VALID == False:
			print("%s. Track Unavailable. Skipping Download"%i)
		else:
			f = "%s. %s - %s"%(prettifyNUM(k),ARTIST_NAME,SONG_NAME)
			filename = DOWNLOAD_PATH+rm_illegal_character(f)
			taskname = "%s. %s"%(k,SONG_NAME)
			download_track(DOWNLOAD_URL,filename,taskname)
			
			
# ══════════════════════════════════════════════════════════════════════════════
# [11단계] 검색 기능 (Search & Download)
# ══════════════════════════════════════════════════════════════════════════════
# URL을 모를 때 키워드로 검색하여 곡/앨범/아티스트를 찾아 다운로드하는 기능이다.
# 검색 결과를 번호로 보여주고, 사용자가 번호를 입력하면 해당 곡/앨범/아티스트를 다운로드한다.

def search_track(keyword,amount):
	"""
	[함수] search_track(keyword, amount) - 키워드로 곡을 검색하고 선택하여 다운로드한다.
	
	입력:
	  - keyword (문자열): 검색어 (예: "아이유")
	  - amount (숫자): 최대 검색 결과 수 (기본값: 20)
	동작 흐름:
	  1. 지니 음원 검색 API를 호출하여 검색 결과를 받아온다
	  2. 결과를 "1. 아티스트 - 곡명" 형식으로 터미널에 출력
	  3. 사용자가 번호를 입력하면 해당 곡을 다운로드
	  4. 0을 입력하면 취소
	결과: 선택된 곡이 downloads/ 폴더에 저장된다
	"""
	# 검색어를 URL 인코딩하여 음원 검색 API 호출
	api_url = "https://app.genie.co.kr/search/category/songs.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = requests.get(api_url).json()
	
	# 검색 결과를 저장할 3개의 딕셔너리
	SONG_SEARCH_RESULTS_NAME = {}    # {인덱스: 곡명}
	SONG_SEARCH_RESULTS_ARTIST = {}  # {인덱스: 아티스트명}
	SONG_SEARCH_RESULTS_CODE = {}    # {인덱스: 곡ID}
	SONG_SEARCH_COUNT = int(response['searchResult']['result']['songs']['total'])  # 전체 검색 결과 수
	
	# 실제 결과가 요청량보다 적으면 실제 수로 조정
	if SONG_SEARCH_COUNT < amount:
		amount = SONG_SEARCH_COUNT
	
	# 검색 결과에서 곡명, 아티스트명, 곡ID를 추출하여 딕셔너리에 저장
	for i in range (0,amount,1):
		try:
			SONG_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['songs']['items'][i]['song_name']['original'])
			SONG_SEARCH_RESULTS_ARTIST [i] = decode(response['searchResult']['result']['songs']['items'][i]['artist_name']['original'])
			SONG_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['songs']['items'][i]['song_id'])
		except IndexError:
			print("d")  # 인덱스 범위 초과 시 (디버그용 코드, 사실상 무시)
	
	# 검색 결과를 터미널에 번호별로 출력
	print("Here are the search results for %s:\n"%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s - %s"%(i+1,SONG_SEARCH_RESULTS_ARTIST[i],SONG_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
	
	divider()
	
	# 사용자에게 다운로드할 곡 번호를 입력받는 루프 (0 입력 시 취소)
	while True:
		try:
			choice = int(input("Enter Choice: \n> "))
			divider()
			if choice == 0:        # 0 입력 = 취소
				cnt = False
				break
			elif 1 <= choice <= amount:  # 유효한 번호 입력
				SELECTED_TRACK_CODE = SONG_SEARCH_RESULTS_CODE [choice-1]  # 0-based 인덱스로 변환
				cnt = True
				break
			else:
				print("[error] Enter a valid number from 1~%s"%amount)
				divider()
				continue
		except:  # 숫자가 아닌 입력 등 예외 처리
			print("[error] Enter a valid number from 1~%s"%amount)
			divider()
			continue
		
	if cnt == False:
		sys.exit(1)  # 취소 시 프로그램 종료
	else:
		# 선택된 곡의 스트리밍 URL을 받아와서 다운로드 실행
		parse_track_data(SELECTED_TRACK_CODE, BITRATE)
		print("[info] Downloading %s - %s\n"%(ARTIST_NAME,SONG_NAME))
		filename = OUTPUT_PATH+"%s - %s"%(ARTIST_NAME,SONG_NAME)
		taskname = "%s. %s"%(1,SONG_NAME)
		download_track(DOWNLOAD_URL,filename,taskname)
	
def search_album(keyword,amount):
	"""
	[함수] search_album(keyword, amount) - 키워드로 앨범을 검색하고 선택하여 다운로드한다.
	
	입력:
	  - keyword (문자열): 검색어 (예: "아이유 LILAC")
	  - amount (숫자): 최대 검색 결과 수
	동작: search_track()과 동일한 흐름이지만,
	       선택 후 download_album()을 호출하여 앨범 전체를 다운로드한다.
	"""
	# 앨범 검색 API 호출
	api_url = "https://app.genie.co.kr/search/category/albums.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = requests.get(api_url).json()
	
	# 검색 결과 저장용 딕셔너리
	ALBUM_SEARCH_RESULTS_NAME = {}    # {인덱스: 앨범명}
	ALBUM_SEARCH_RESULTS_ARTIST = {}  # {인덱스: 아티스트명}
	ALBUM_SEARCH_RESULTS_CODE = {}    # {인덱스: 앨범ID}
	ALBUM_SEARCH_COUNT = int(response['searchResult']['result']['albums']['total'])
	
	if ALBUM_SEARCH_COUNT < amount:
		amount = ALBUM_SEARCH_COUNT

	# 검색 결과에서 앨범명, 아티스트명, 앨범ID 추출
	for i in range (0,amount,1):
		try:
			ALBUM_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['albums']['items'][i]['album_name']['original'])
			ALBUM_SEARCH_RESULTS_ARTIST [i] = decode(response['searchResult']['result']['albums']['items'][i]['artist_name']['original'])
			ALBUM_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['albums']['items'][i]['album_id'])
		except IndexError:
			print("d")
	
	# 검색 결과 출력
	print('Here are the album search results for "%s":\n'%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s - %s"%(i+1,ALBUM_SEARCH_RESULTS_ARTIST[i],ALBUM_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
		
	divider()
	
	# 사용자 선택 루프 (search_track과 동일한 패턴)
	while True:
		try:
			choice = int(input("Enter Choice: \n> "))
			divider()
			if choice == 0:
				cnt = False
				break
			elif 1 <= choice <= amount:
				SELECTED_ALBUM_CODE = ALBUM_SEARCH_RESULTS_CODE [choice-1]
				cnt = True
				break
			else:
				print("[error] Enter a valid number from 1~%s"%amount)
				divider()
				continue
		except:
			print("[error] Enter a valid number from 1~%s"%amount)
			divider()
			continue
		
	if cnt == False:
		sys.exit(1)
	else:
		download_album(SELECTED_ALBUM_CODE)  # 선택된 앨범 전체 다운로드
		

def search_artist(keyword,amount):
	"""
	[함수] search_artist(keyword, amount) - 키워드로 아티스트를 검색하고 선택하여 전체 디스코그래피를 다운로드한다.
	
	입력:
	  - keyword (문자열): 검색어 (예: "아이유")
	  - amount (숫자): 최대 검색 결과 수
	동작: 검색 -> 선택 -> download_artist() 호출
	       (선택된 아티스트의 모든 앨범의 모든 곡을 다운로드!)
	주의: 앨범이 많은 아티스트는 시간이 매우 오래 걸릴 수 있다!
	"""
	# 아티스트 검색 API 호출
	api_url = "https://app.genie.co.kr/search/category/artists.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = requests.get(api_url).json()
	
	# 검색 결과 저장용 딕셔너리
	ARTIST_SEARCH_RESULTS_NAME = {}    # {인덱스: 아티스트명}
	ARTIST_SEARCH_RESULTS_ARTIST = {}  # (미사용)
	ARTIST_SEARCH_RESULTS_CODE = {}    # {인덱스: 아티스트ID}
	ARTIST_SEARCH_COUNT = int(response['searchResult']['result']['artists']['total'])
	
	if ARTIST_SEARCH_COUNT < amount:
		amount = ARTIST_SEARCH_COUNT
		
	# 검색 결과에서 아티스트명과 ID 추출
	for i in range (0,amount,1):
		try:
			ARTIST_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['artists']['items'][i]['artist_name']['original'])
			ARTIST_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['artists']['items'][i]['artist_id'])
		except IndexError:
			sys.exit(1)
	
	# 검색 결과 출력 (아티스트는 이름만 표시)
	print("Here are the search results for %s:\n"%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s"%(i+1,ARTIST_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
		
	divider()
	
	# 사용자 선택 루프
	while True:
		try:
			choice = int(input("Enter Choice: \n> "))
			divider()
			if choice == 0:
				cnt = False
				break
			elif 1 <= choice <= amount:
				SELECTED_ARTIST_CODE = ARTIST_SEARCH_RESULTS_CODE [choice-1]
				cnt = True
				break
			else:
				print("[error] Enter a valid number from 1~%s"%amount)
				divider()
				continue
		except:
			print("[error] Enter a valid number from 1~%s"%amount)
			divider()
			continue
		
	if cnt == False:
		sys.exit(1)
	else:
		download_artist(SELECTED_ARTIST_CODE)  # 선택된 아티스트 전체 다운로드
		

# ══════════════════════════════════════════════════════════════════════════════
# [12단계] URL 파싱 함수 (URL -> 액션 라우팅)
# ══════════════════════════════════════════════════════════════════════════════
# 사용자가 입력한 URL을 분석하여 적절한 다운로드 함수를 호출한다.

def parse_user_input(url):
	"""
	[함수] parse_user_input(url) - 지니뮤직 URL을 분석하여 적절한 다운로드 액션을 실행한다.
	
	입력: url (문자열) - 지니뮤직 URL
	동작: URL 안의 특정 파라미터 이름으로 유형을 판별한다:
	  - "plmSeq" 포함 -> 플레이리스트 다운로드
	  - "axnm" 포함   -> 앨범 다운로드
	  - "xxnm" 포함   -> 아티스트 전체 다운로드
	  - "xgnm" 포함   -> 개별 곡 다운로드
	  - 어느 것도 없으면 -> 에러
	
	예시 URL 패턴:
	  곡: https://genie.co.kr/detail/songInfo?xgnm=97835731
	  앨범: https://genie.co.kr/detail/albumInfo?axnm=81234567
	  아티스트: https://genie.co.kr/detail/artistInfo?xxnm=20001234
	  플레이리스트: https://genie.co.kr/playlist/plmSeq=12345
	"""
	global TYPE,CODE
	
	# URL 안에 어떤 키워드가 있는지 검사하여 유형을 판별
	if "plmSeq" in url:  # 플레이리스트 URL
		TYPE = "Playlist"
		CODE = parse_code(url,TYPE)  # URL에서 숫자 코드 추출
		download_playlist(CODE)      # 플레이리스트 다운로드 실행
		
	elif "axnm" in url:  # 앨범 URL
		TYPE = "Album"
		CODE = parse_code(url,TYPE)
		download_album(CODE)
		
	elif "xxnm" in url:  # 아티스트 URL
		TYPE = "Artist"
		CODE = parse_code(url,TYPE)
		download_artist(CODE)
		
	elif "xgnm" in url:  # 개별 곡 URL
		TYPE = "Track"
		CODE = parse_code(url,TYPE)
		parse_track_data(CODE,BITRATE)  # 스트리밍 URL 획득
		print("[info] Downloading %s - %s\n"%(ARTIST_NAME,SONG_NAME))
		filename = OUTPUT_PATH+"%s - %s"%(ARTIST_NAME,SONG_NAME)
		taskname = "%s. %s"%(1,SONG_NAME)
		download_track(DOWNLOAD_URL,filename,taskname)
		
	else:
		# 지니뮤직 URL이 아닌 경우 에러 출력
		print("[error] Invalid URL: %s"%url)
		divider()
		sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# [13단계] 메인 함수 (Main - 대화형 메뉴 모드)
# ══════════════════════════════════════════════════════════════════════════════
# 명령줄 옵션 없이 실행하면 이 함수가 호출되어 대화형 메뉴를 보여준다.

def main():
	"""
	[함수] main() - 프로그램의 대화형 모드 진입점.
	
	동작 흐름:
	  1. 설정 파일에서 ID/PW를 읽고 로그인한다
	  2. GENIE-DL ASCII 아트 로고를 표시한다
	  3. 7가지 메뉴 옵션을 보여주고 사용자가 화살표 키로 선택:
	     0: URL로 곡/앨범/아티스트/플레이리스트 다운로드
	     1: 실시간 차트 다운로드 (TOP 200)
	     2: 실시간 차트 보기 (다운로드 없이)
	     3: 곡 검색 후 다운로드
	     4: 앨범 검색 후 다운로드
	     5: 아티스트 검색 후 다운로드
	     6: 종료
	"""
	read_config()     # 설정 파일에서 ID/PW 읽기
	login(ID,PW)      # 지니 서버에 로그인
	divider()

	# GENIE-DL 로고를 ASCII 아트로 표시
	text='''===================================================
|     _____________   ____________     ____  __   |
|    / ____/ ____/ | / /  _/ ____/    / __ \/ /   |
|   / / __/ __/ /  |/ // // __/______/ / / / /    |
|  / /_/ / /___/ /|  // // /__/_____/ /_/ / /___  |
|  \____/_____/_/ |_/___/_____/    /_____/_____/  |
|                                                 |
===================================================
	 GENIE-DL v.1.0.5 by vank0n (SJJeon)
	'''
	
	# pick 라이브러리로 터미널 선택 메뉴 표시 (화살표 키로 선택, Enter로 확인)
	options = ['Download Song / Album / Artist / Playlist', 'Download Real-Time Chart', 'View Real-Time Chart', 'Search and Download Song','Search and Download Album','Search and Download Artist','Exit']
	selected = pick(options, text, multiselect=False, min_selection_count=1,indicator="=>")[1]
	# selected는 선택된 항목의 인덱스 (0~6)
	
	if selected == 0:  # URL 입력으로 다운로드
		CODE = parse_user_input(input("Enter URL: "))
		parse_track_data(CODE,BITRATE)
		print("[info] Downloading %s - %s\n"%(ARTIST_NAME,SONG_NAME))
		filename = OUTPUT_PATH+"%s - %s"%(ARTIST_NAME,SONG_NAME)
		taskname = "%s. %s"%(1,SONG_NAME)
		download_track(DOWNLOAD_URL,filename,taskname)
	elif selected == 0:  # [NOTE] 중복된 조건 - 원본 코드의 버그로 보임 (2번째 elif == 0은 절대 실행되지 않음)
		parse_user_input(input("Enter Song / Album / Playlist URL: "))
	elif selected == 1:  # 실시간 차트 TOP 200 다운로드
		download_realtime_chart(1,200)
	elif selected == 2:  # 실시간 차트 보기 (다운로드 없이 출력만)
		print_realtime_chart(1,200)
	elif selected == 3:  # 곡 검색 후 다운로드
		search_track(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 4:  # 앨범 검색 후 다운로드
		search_album(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 5:  # 아티스트 검색 후 다운로드
		search_artist(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 6:  # 프로그램 종료
		sys.exit(1)
	
	divider()

# ══════════════════════════════════════════════════════════════════════════════
# [14단계] 프로그램 시작점 (Entry Point)
# ══════════════════════════════════════════════════════════════════════════════
# 파이썬에서 .py 파일을 직접 실행할 때 가장 먼저 실행되는 부분이다.
# __name__ == "__main__"은 "이 파일이 직접 실행되었는가?"를 확인한다.
# (import로 불러온 경우와 구분하기 위해 사용하는 파이썬 관용구)

if __name__ == "__main__":
	try:
		# 명령줄 옵션이 없으면 -> 대화형 메뉴 모드(main() 호출)
		if DOWNLOAD_CHART == None and INPUT_URL == None:
			main()
		
		else:
			# 명령줄 옵션이 있으면 -> 직접 실행 모드 (메뉴 없이 바로 실행)
			read_config()
			login(ID,PW)
			divider()
			
			if DOWNLOAD_CHART != None:
				# -c "1-100" 같은 형식을 파싱하여 시작/끝 순위 추출
				c = DOWNLOAD_CHART.split("-")   # "1-100" -> ["1", "100"]
				CHART_START = int(c[0])         # 시작 순위: 1
				
				CHART_END = int(c[1])           # 끝 순위: 100
				if CHART_END >= 200:            # 최대 200위까지 제한
					CHART_END = 200
				download_realtime_chart(CHART_START,CHART_END)
			
			elif INPUT_URL != None:
				# -i <URL> 옵션으로 URL이 주어진 경우
				parse_user_input(INPUT_URL)  # URL 파싱 후 적절한 다운로드 실행
			
			divider()
	
	except KeyboardInterrupt:  # Ctrl+C로 중단하면 깨끗하게 종료
		sys.exit(128 + signal.SIGINT)