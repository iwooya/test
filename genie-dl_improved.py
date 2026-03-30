# ============================================================================
# GENIE-DL v1.1.0 (Improved) - 지니뮤직 음원 다운로더
# ============================================================================
# 원본 제작자: vank0n (SJJeon)
# 개선 사항 (v1.1.0):
#   [개선1] 모바일 앱 환경 위장 - requests.Session + 모바일 UA/헤더 적용
#          원본은 app.genie.co.kr (모바일 앱 전용 API)를 사용하면서
#          User-Agent가 "python-requests/x.x.x"로 전송되어
#          서버에서 자동화 도구임이 즉시 식별 가능했음
#   [개선2] 서버 탐지 최소화 - 곡 간 랜덤 딜레이 삽입
#          원본은 for 루프로 곡을 쉼 없이 연속 요청하여
#          비정상적인 burst 트래픽 패턴이 생겼음
#   [개선3] 로그인 응답 JSON 파싱 에러 핸들링 추가
#   [개선4] SyntaxWarning 수정 (정규표현식 raw string)
#   [개선5] main() 메뉴에서 중복 elif == 0 버그 수정
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# [1단계] 라이브러리 임포트 (Import)
# ──────────────────────────────────────────────────────────────────────────────
import requests
import json
import os
#import eyed3
import sys
import shutil
import re
import pathlib
import argparse
import platform
import signal
import time            # [개선2] 요청 간 딜레이를 위해 추가
import random          # [개선2] 랜덤 딜레이를 위해 추가
import uuid            # [개선6] 요청마다 랜덤 UUID 생성을 위해 추가
from datetime import datetime
from datetime import date
from pick import pick
import configparser
import questionary
from utils import download

# ──────────────────────────────────────────────────────────────────────────────
# [2단계] 명령줄 인자(Argument) 파서 설정
# ──────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='\033[93mGENIE-DL by vank0n © 2021 vank0n (SJJeon) - All Rights Reserved.\033[0m',epilog="https://github.com/WHTJEON/genie-music-downloader")
parser.add_argument('-c', '--download-chart',default=None,help = "Download Genie TOP 200 Chart",metavar="RANGE")
parser.add_argument('-i','--input',default=None,required=False,help = "Download Genie Song/Album/Playlist",metavar="URL")
parser.add_argument('--reset',action='store_true',help="Reset Credentials")
parser.add_argument('-f','--format',choices=["mp3", "flac", "flac24"],default='mp3')
args = parser.parse_args()

# ──────────────────────────────────────────────────────────────────────────────
# [3단계] 전역 변수(Global Variables) 설정
# ──────────────────────────────────────────────────────────────────────────────
if args.format == "mp3":
	BITRATE = 320
	EXTENSION = "mp3"
else:
	EXTENSION = "flac"
	BITRATE = 1000 if args.format == "flac" else "24bit"

INPUT_URL = args.input
SEARCH_AMOUNT = 20
DOWNLOAD_CHART = args.download_chart
RESET_P = args.reset
# [개선6] 고정 DEVICE_ID 제거 → 매 실행시 랜덤 UUID 생성
# 실제 안드로이드 앱은 요청마다 랜덤 UUID를 사용함 (트래픽 캡처 확인)
DEVICE_ID = str(uuid.uuid4())

SCRIPT_PATH = str(pathlib.Path(__file__).parent.absolute())
OUTPUT_PATH = SCRIPT_PATH + "/downloads/"

# ──────────────────────────────────────────────────────────────────────────────
# [개선1+6] 모바일 앱 환경 위장 - HTTP 세션 및 헤더 설정
# ──────────────────────────────────────────────────────────────────────────────
# [개선6] 실제 안드로이드 앱 트래픽 캡처 결과를 반영하여 헤더를 수정함
#   실제 User-Agent 형식: "genie/ANDROID/{앱버전}/{랜덤UUID}"
#   실제 앱 버전: 60008 (기존 50101은 구버전)
#   실제 Accept-Encoding: identity (CDN 다운로드 시)
# ──────────────────────────────────────────────────────────────────────────────

APP_VERSION = "60008"  # [개선6] 실제 앱 버전 (트래픽 캡처 확인)

session = requests.Session()

# [개선6] 실제 안드로이드 앱이 보내는 헤더와 동일하게 구성
session.headers.update({
	# User-Agent: 실제 앱 형식 "genie/ANDROID/{버전}/{UUID}"
	"User-Agent": "genie/ANDROID/%s/%s" % (APP_VERSION, DEVICE_ID),
	"Accept-Encoding": "identity",
	"Connection": "Keep-Alive",
})


# ──────────────────────────────────────────────────────────────────────────────
# [개선2] 요청 간 랜덤 딜레이 함수
# ──────────────────────────────────────────────────────────────────────────────
# 원본 코드의 문제점:
#   for 루프 안에서 곡 200개를 0.0초 간격으로 연속 요청함
#   → 서버 입장에서 "1초에 API 50번 호출" = 명백한 자동화 도구 패턴
#
# 개선 방법:
#   각 곡 다운로드 사이에 1~3초의 랜덤 대기를 넣음
#   → 사람이 곡을 하나씩 고르는 것처럼 보이는 자연스러운 패턴
#
# 왜 "랜덤"인가?
#   고정 간격(예: 정확히 2초)은 오히려 기계적이라 탐지됨
#   사람은 1.2초, 2.7초, 1.8초처럼 불규칙하게 행동하므로 랜덤이 더 자연스러움
# ──────────────────────────────────────────────────────────────────────────────

# 딜레이 범위 설정 (초 단위)
DELAY_MIN = 1.0   # 최소 대기 시간
DELAY_MAX = 3.0   # 최대 대기 시간

def human_delay():
	"""
	[함수] human_delay() - 사람처럼 보이는 랜덤 대기 시간을 적용한다.
	
	동작: DELAY_MIN ~ DELAY_MAX 사이의 랜덤 시간만큼 대기
	용도: 곡 다운로드 사이에 호출하여 burst 패턴을 방지
	"""
	delay = random.uniform(DELAY_MIN, DELAY_MAX)
	time.sleep(delay)


# ──────────────────────────────────────────────────────────────────────────────
# [4단계] 설정 파일 읽기/생성 함수
# ──────────────────────────────────────────────────────────────────────────────
def read_config():
	"""
	[함수] read_config() - 로그인 설정 파일을 읽거나 새로 생성한다.
	"""
	global ID, PW
	config = configparser.ConfigParser()
	config_file = "%s/genie-dl-settings.ini"%SCRIPT_PATH
	
	if RESET_P != True:
		if pathlib.Path(config_file).is_file():
			config.read(SCRIPT_PATH+'/genie-dl-settings.ini')
			ID = config['DEFAULT']['genie_id']
			PW = config['DEFAULT']['genie_password']
		else:
			print("No config file is found. Creating a new one...")
			ID = questionary.text("Enter your Genie ID: ",qmark=">").ask()
			PW = questionary.password("Enter Genie Password: ",qmark=">").ask()
			config['DEFAULT']['genie_id'] = ID
			config['DEFAULT']['genie_password'] = PW
			with open(config_file, 'w') as configfile:
				config.write(configfile)
			print("Successfully created config file!")
	else:
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

def is_win():
	if platform.system() == 'Windows':
		return True

def rm_illegal_character(str):
	if is_win():
		# [개선4] raw string으로 변경: '[\/:*?"><|]' → r'[\/:*?"><|]'
		# Python 3.12+에서 SyntaxWarning 발생하던 것을 수정
		return re.sub(r'[\/:*?"><|]','_',str)
	else:
		return re.sub('[:/]', '_', str)

def divider():
	count = int(shutil.get_terminal_size().columns)
	count = count - 1
	print ('-' * count)
	
def remove(): 
	count = int(shutil.get_terminal_size().columns)
	count = count - 1
	blank =' ' * count
	print ("\033[A%s\033[A"%blank)

def decode(str):
	return requests.utils.unquote(str)

def encode(str):
	return requests.utils.quote(str)

def prettifyNUM(num):
	if len(str(num)) == 1:
		num = "%02d"%num
	return num

	
# ──────────────────────────────────────────────────────────────────────────────
# [6단계] URL 파싱 및 다운로드 실행 함수
# ──────────────────────────────────────────────────────────────────────────────

def parse_code(url,type):
	# [개선4] raw string: '\d+' → r'\d+'
	match = re.findall(r'\d+',url)
	try:
		CODE = match[0]
		print("[info] URL Type: %s"%type)
		return CODE
	except IndexError:
		print("[error] Invalid URL: %s"%url)
		divider()
		sys.exit(1)
		
def download_track(url,filename,taskname):
	download.download(url,file_name="%s.%s"%(filename,EXTENSION),name=taskname,block_size=512)
		
# ──────────────────────────────────────────────────────────────────────────────
# [7단계] 서버 통신 함수들 (Server Communication)
# ──────────────────────────────────────────────────────────────────────────────
# [개선1] 모든 requests.get/post를 session.get/post로 변경하여
#         매 요청마다 모바일 앱 헤더가 자동으로 포함되게 함

def login(username,password):
	"""
	[함수] login(username, password) - 지니뮤직 서버에 로그인한다.
	
	[개선1] session.post 사용 → 모바일 앱 User-Agent 자동 포함
	[개선3] .json() 파싱 실패 시 try/except로 안전하게 처리
	        (서버가 JSON 대신 HTML을 반환하는 경우 등 대비)
	"""
	global user_num,user_token,stm_token
	
	credentials = {
		"uxd": username,
		"uxx": password
	}
	
	# [개선1] requests.post → session.post (모바일 앱 헤더 자동 포함)
	# [개선3] .json() 파싱을 try/except로 감싸서 JSONDecodeError 방지
	try:
		response = session.post(
			"https://app.genie.co.kr/member/j_Member_Login.json",
			data=credentials
		).json()
	except (json.JSONDecodeError, requests.exceptions.RequestException) as e:
		divider()
		print("[error] Login request failed: %s" % e)
		print("[info] Server may have returned non-JSON response (maintenance, IP block, etc.)")
		divider()
		sys.exit(1)
	
	if response['Result']['RetCode'] != "0":
		LOGIN = False
		divider()
		print("[error] Authentication failed. Check your credentials.")
		divider()
		sys.exit(1)
	else:
		LOGIN = True
	
	user_num = response['DATA0']['MemUno']
	user_token = response['DATA0']['MemToken']
	stm_token = response['DATA0']['STM_TOKEN']
	
# ──────────────────────────────────────────────────────────────────────────────
# [8단계] 데이터 파싱 함수들 (API 응답 → 데이터 추출)
# ──────────────────────────────────────────────────────────────────────────────
# [개선1] 모든 requests.get을 session.get으로 변경

def parse_playlist_data (seq):
	global PLAYLIST_NAME, PLAYLIST_TRACK_COUNT, PLAYLIST_TRACK_CODES, PLAYLIST_TRACK_TITLES
	
	api_url = "https://app.genie.co.kr/Iv3/playlist/infosong.json?seq={}".format(seq)
	response = session.get(api_url).json()  # [개선1] session.get
	
	try:
		PLAYLIST_NAME = decode(response['DATASET']['DATA_INFO']['DATA']['PLM_TITLE'])
		PLAYLIST_TRACK_COUNT = int(decode(response['DATASET']['DATA_INFO']['DATA']['SONG_CNT']))
		PLAYLIST_TRACK_CODES = {}
		PLAYLIST_TRACK_TITLES = {}
		
		for i in range (0,PLAYLIST_TRACK_COUNT,1):
			PLAYLIST_TRACK_CODES [i] = int(decode(response['DATASET']['DATA_SONG']['DATA'][i]['SONG_ID']))
			PLAYLIST_TRACK_TITLES [i] = decode(response['DATASET']['DATA_SONG']['DATA'][i]['SONG_NAME'])
	
	except KeyError:
		print("[error] Unable to fetch playlist data. Check your URL")
		divider()
		sys.exit(1)
		
def parse_album_data(axnm):
	global ALBUM_TRACK_CODES,ALBUM_TRACK_TITLES,ALBUM_NAME,ALBUM_TRACK_COUNT, ALBUM_DATE, ALBUM_TYPE, ALBUM_ARTIST
	
	response = session.get("https://info.genie.co.kr/info/album?axnm={}".format(axnm)).json()  # [개선1]
	
	try:
		ALBUM_NAME = response['album_info']['album_name']
		ALBUM_ARTIST = response['album_info']['artist_name']
		ALBUM_DATE_RAW = str(response['album_info']['album_release_dt'])
		year = ALBUM_DATE_RAW[0:4]
		month = ALBUM_DATE_RAW[4:6]
		ALBUM_DATE = "[%s.%s]"%(year,month)
		ALBUM_TYPE = decode(response['album_info']['album_type'])
		ALBUM_TRACK_COUNT = len(response['album_song_list'])
		ALBUM_TRACK_CODES = {}
		ALBUM_TRACK_TITLES = {}
		
		for i in range (0,ALBUM_TRACK_COUNT,1):
			ALBUM_CD = int(response['album_song_list'][i]['album_cd_no'])
			if ALBUM_CD == 1:
				ALBUM_TRACK_CODES[int(response['album_song_list'][i]['album_track_no'])]=response['album_song_list'][i]['song_id']
				ALBUM_TRACK_TITLES[int(response['album_song_list'][i]['album_track_no'])]=response['album_song_list'][i]['song_name']
			else: 
				current_count = len(ALBUM_TRACK_CODES)
				ALBUM_TRACK_COUNT = current_count
		
		print("[info] Found Album: %s (%s) (%s tracks)"%(ALBUM_NAME,ALBUM_ARTIST,ALBUM_TRACK_COUNT))
		
	except KeyError:
		print("[error] Unable to fetch album data. Check your URL")
		divider()
		sys.exit(1)

def parse_artist_data(xxnm):
	global ARTIST_NAME_FIX
	try:
		response = session.get("https://info.genie.co.kr/info/artist?xxnm={}".format(xxnm)).json()  # [개선1]
		ARTIST_NAME_FIX = response['artist_info']['artist_name']
		print("[info] Found Artist: %s"%(ARTIST_NAME_FIX))
		return ARTIST_NAME_FIX
	except KeyError:
		print("[error] Unable to fetch artist data. Check your URL")
		divider()
		sys.exit(1)
		
def parse_track_data(xgnm,bitrate):
	"""
	[개선1] session.get 사용 → 모바일 앱 헤더 자동 포함
	        스트리밍 서버(stm.genie.co.kr)에도 동일한 UA가 전송됨
	"""
	global ARTIST_NAME,SONG_NAME,DOWNLOAD_URL,IS_VALID
	
	# 요청 파라미터를 딕셔너리로 구성하여 가독성 있게 출력
	request_params = {
		"xgnm": xgnm,
		"bitrate": bitrate,
		"app_stm_type": "normal",
		"unm": user_num,
		"uxtk": user_token,
		"vmd": "AN",
		"svc": "IV",
		"stk": stm_token,
		"udid": DEVICE_ID,
		"itn": "Y",
		"mts": "Y",
		"apvn": APP_VERSION,
	}
	
	# [요청 파라미터 출력] 서버에 어떤 값을 보내는지 확인용
	print("[request] ── 스트리밍 API 호출 파라미터 ──")
	print("  곡 ID (xgnm)    : %s" % xgnm)
	print("  음질 (bitrate)   : %s" % bitrate)
	print("  사용자 번호 (unm): %s" % user_num)
	print("  기기 ID (udid)   : %s" % DEVICE_ID)
	print("  앱 버전 (apvn)   : %s" % APP_VERSION)
	
	api_url = "https://stm.genie.co.kr/player/j_StmInfo.json?xgnm={}&bitrate={}&app_stm_type=normal&unm={}&uxtk={}&vmd=AN&svc=IV&stk={}&udid={}&itn=Y&mts=Y&apvn={}".format(xgnm,bitrate,user_num,user_token,stm_token,DEVICE_ID,APP_VERSION)
	response = session.get(api_url).json()  # [개선1]
	SUCCESS = response['Result']['RetMsg']

	try:
		DATA = response['DataSet']['DATA'][0]
		SONG_NAME = decode(DATA['SONG_NAME'])
		ARTIST_NAME = decode(DATA['ARTIST_NAME'])
		DOWNLOAD_URL = decode(DATA['STREAMING_MP3_URL'])
		IS_VALID = True
		
		# [결과 URL 출력] 디코딩된 스트리밍 URL 확인용
		print("[response] ── 스트리밍 결과 ──")
		print("  아티스트 : %s" % ARTIST_NAME)
		print("  곡 제목  : %s" % SONG_NAME)
		print("  결과 상태: %s" % SUCCESS)
		print("  스트리밍 URL (decoded): %s" % DOWNLOAD_URL)
		print("")
		
		return DOWNLOAD_URL
	
	except IndexError:
		IS_VALID = False
		print("[response] 스트리밍 불가 (데이터 없음) - 곡 ID: %s" % xgnm)
		print("")
		
	except KeyError:
		print("[error] Unable to fetch track data. Check your URL")
		divider()
		sys.exit(1)
	
	except:
		print(response)
		
# ──────────────────────────────────────────────────────────────────────────────
# [9단계] 다운로드 실행 함수들 (Download Executors)
# ──────────────────────────────────────────────────────────────────────────────
# [개선2] 각 곡 다운로드 사이에 human_delay()를 삽입하여
#         연속 요청 패턴을 완화하고 서버 부하를 줄임

def get_artist_albums(xxnm):
	global TOTAL_ALBUM_COUNT,ARTIST_ALBUMS
	api_url = "https://app.genie.co.kr/song/j_ArtistAlbumList.json?pg=1&pgsize=500&xxnm={}&otype=newest&atype=all&mts=Y".format(xxnm)
	response = session.get(api_url).json()  # [개선1]
	try:
		TOTAL_ALBUM_COUNT = int(response['PageInfo']['TotCount'])
		ARTIST_ALBUMS = []
		for i in range (0,TOTAL_ALBUM_COUNT,1):
			ALBUM_CODE = response['DataSet']['DATA'][i]['ALBUM_ID']
			ARTIST_ALBUMS.append(ALBUM_CODE)
	except KeyError:
		print("The following artist is unavailable to fetch albums")
		sys.exit(1)
			
def download_album(axnm):
	parse_album_data(axnm)
	k = 0
	
	DOWNLOAD_PATH = OUTPUT_PATH+"%s/%s %s/"%(rm_illegal_character(ALBUM_ARTIST),ALBUM_DATE,rm_illegal_character(ALBUM_NAME))
	if not os.path.exists(DOWNLOAD_PATH):
		os.makedirs(DOWNLOAD_PATH)
	
	print("[info] Downloading Tracks of [%s]\n"%ALBUM_NAME)
	
	for i in range (1,ALBUM_TRACK_COUNT+1,1):
		k = k + 1
		try:
			parse_track_data(ALBUM_TRACK_CODES[i], BITRATE)
			if IS_VALID == False:
				print("%s. Track Unavailable. Skipping Download"%i)
			else:
				f = rm_illegal_character("%s. %s - %s"%(prettifyNUM(i),ARTIST_NAME,str(ALBUM_TRACK_TITLES[i])))
				filename = DOWNLOAD_PATH+f
				taskname = "%s. %s"%(i,ALBUM_TRACK_TITLES[i])
				download_track(DOWNLOAD_URL,filename,taskname)
			# [개선2] 곡 다운로드 후 랜덤 대기 (마지막 곡 제외)
			if k < ALBUM_TRACK_COUNT:
				human_delay()
		except KeyError:
			pass

def download_playlist(seq):
	parse_playlist_data(seq)
	print("[info] Downloading Playlist: %s (%s tracks)\n"%(PLAYLIST_NAME,PLAYLIST_TRACK_COUNT))
	
	DOWNLOAD_PATH = OUTPUT_PATH+"[Playlist] %s/"%PLAYLIST_NAME.replace(":","-")
	if not os.path.exists(DOWNLOAD_PATH):
		os.makedirs(DOWNLOAD_PATH)
	
	for i in range (0, PLAYLIST_TRACK_COUNT,1):
		parse_track_data (PLAYLIST_TRACK_CODES[i], BITRATE)
		if IS_VALID == False:
			print("%s. Track Unavailable. Skipping Download"%i)
		else:
			f = "%s. %s - %s"%(prettifyNUM(i+1),ARTIST_NAME,rm_illegal_character(str(PLAYLIST_TRACK_TITLES[i])))
			filename = DOWNLOAD_PATH+f
			taskname = "%s. %s"%(i+1,PLAYLIST_TRACK_TITLES[i])
			download_track(DOWNLOAD_URL,filename,taskname)
		# [개선2] 곡 다운로드 후 랜덤 대기 (마지막 곡 제외)
		if i < PLAYLIST_TRACK_COUNT - 1:
			human_delay()

	
def download_artist(xxnm):
	get_artist_albums(xxnm)
	parse_artist_data(xxnm)
	k = 0
	
	for ALBUM in ARTIST_ALBUMS:
		k = k + 1
		print("[info] Downloading %s's Albums (%s/%s)"%(ARTIST_NAME_FIX,k,TOTAL_ALBUM_COUNT))
		download_album(ALBUM)
		if k != TOTAL_ALBUM_COUNT:
			divider()
			# [개선2] 앨범 간에도 딜레이 적용 (앨범 내 곡은 이미 딜레이가 있으므로 짧게)
			human_delay()
		
# ──────────────────────────────────────────────────────────────────────────────
# [10단계] 실시간 차트 기능 (Real-Time Chart)
# ──────────────────────────────────────────────────────────────────────────────
		
def print_realtime_chart (start,end):
	api_url = "https://app.genie.co.kr/chart/j_RealTimeRankSongList.json?pg=1&pgsize=200"
	response = session.get(api_url).json()  # [개선1]
	
	now = datetime.now()
	today = date.today()
	d1 = today.strftime("%Y.%m.%d")
	current_hour = now.strftime("%H")
	CHART_NAME = "[Genie Realtime Chart for %s %s:00]\n"%(d1,current_hour)
	CHART = {}
	print(CHART_NAME)
	
	for i in range (start-1,end,1):
		TRACK_NAME = decode(response["DataSet"]['DATA'][i]['SONG_NAME'])
		ARTIST_NAME = decode(response["DataSet"]['DATA'][i]['ARTIST_NAME'])
		string = "%s. %s - %s"%(i+1,ARTIST_NAME,TRACK_NAME)
		CHART [i+1] = string
		
	for i in range (start,end+1,1):	
		print(CHART[i])
		

def download_realtime_chart(start,end):
	api_url = "https://app.genie.co.kr/chart/j_RealTimeRankSongList.json?pg=1&pgsize=200"
	response = session.get(api_url).json()  # [개선1]
	CHART_TRACK_CODES = []
	
	for i in range (start-1,end,1):
		TRACK_CODE = response["DataSet"]['DATA'][i]['SONG_ID']
		CHART_TRACK_CODES.append(TRACK_CODE)
	
	now = datetime.now()
	today = date.today()
	d1 = today.strftime("%y%m%d")
	current_hour = now.strftime("%H")
	
	CHART_NAME = "%s %s:00"%(d1,current_hour)
	print("[info] Downloading Real-Time Chart for %s (%s~%s)\n"%(CHART_NAME,start,end))
	
	k = 0
	DOWNLOAD_PATH = OUTPUT_PATH+"[Genie TOP 200] - %s/"%CHART_NAME.replace(":","_").replace(" ","_")
	if not os.path.exists(DOWNLOAD_PATH):
		os.makedirs(DOWNLOAD_PATH)
	
	total = len(CHART_TRACK_CODES)
	for tracks in CHART_TRACK_CODES:
		k = k + 1
		parse_track_data(tracks, BITRATE)
		if IS_VALID == False:
			print("%s. Track Unavailable. Skipping Download"%k)
		else:
			f = "%s. %s - %s"%(prettifyNUM(k),ARTIST_NAME,SONG_NAME)
			filename = DOWNLOAD_PATH+rm_illegal_character(f)
			taskname = "%s. %s"%(k,SONG_NAME)
			download_track(DOWNLOAD_URL,filename,taskname)
		# [개선2] 곡 다운로드 후 랜덤 대기 (마지막 곡 제외)
		if k < total:
			human_delay()
			
			
# ══════════════════════════════════════════════════════════════════════════════
# [11단계] 검색 기능 (Search & Download)
# ══════════════════════════════════════════════════════════════════════════════

def search_track(keyword,amount):
	api_url = "https://app.genie.co.kr/search/category/songs.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = session.get(api_url).json()  # [개선1]
	
	SONG_SEARCH_RESULTS_NAME = {}
	SONG_SEARCH_RESULTS_ARTIST = {}
	SONG_SEARCH_RESULTS_CODE = {}
	SONG_SEARCH_COUNT = int(response['searchResult']['result']['songs']['total'])
	
	if SONG_SEARCH_COUNT < amount:
		amount = SONG_SEARCH_COUNT
	
	for i in range (0,amount,1):
		try:
			SONG_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['songs']['items'][i]['song_name']['original'])
			SONG_SEARCH_RESULTS_ARTIST [i] = decode(response['searchResult']['result']['songs']['items'][i]['artist_name']['original'])
			SONG_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['songs']['items'][i]['song_id'])
		except IndexError:
			print("d")
	
	print("Here are the search results for %s:\n"%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s - %s"%(i+1,SONG_SEARCH_RESULTS_ARTIST[i],SONG_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
	
	divider()
	
	while True:
		try:
			choice = int(input("Enter Choice: \n> "))
			divider()
			if choice == 0:
				cnt = False
				break
			elif 1 <= choice <= amount:
				SELECTED_TRACK_CODE = SONG_SEARCH_RESULTS_CODE [choice-1]
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
		parse_track_data(SELECTED_TRACK_CODE, BITRATE)
		print("[info] Downloading %s - %s\n"%(ARTIST_NAME,SONG_NAME))
		filename = OUTPUT_PATH+"%s - %s"%(ARTIST_NAME,SONG_NAME)
		taskname = "%s. %s"%(1,SONG_NAME)
		download_track(DOWNLOAD_URL,filename,taskname)
	
def search_album(keyword,amount):
	api_url = "https://app.genie.co.kr/search/category/albums.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = session.get(api_url).json()  # [개선1]
	
	ALBUM_SEARCH_RESULTS_NAME = {}
	ALBUM_SEARCH_RESULTS_ARTIST = {}
	ALBUM_SEARCH_RESULTS_CODE = {}
	ALBUM_SEARCH_COUNT = int(response['searchResult']['result']['albums']['total'])
	
	if ALBUM_SEARCH_COUNT < amount:
		amount = ALBUM_SEARCH_COUNT

	for i in range (0,amount,1):
		try:
			ALBUM_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['albums']['items'][i]['album_name']['original'])
			ALBUM_SEARCH_RESULTS_ARTIST [i] = decode(response['searchResult']['result']['albums']['items'][i]['artist_name']['original'])
			ALBUM_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['albums']['items'][i]['album_id'])
		except IndexError:
			print("d")
	
	print('Here are the album search results for "%s":\n'%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s - %s"%(i+1,ALBUM_SEARCH_RESULTS_ARTIST[i],ALBUM_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
		
	divider()
	
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
		download_album(SELECTED_ALBUM_CODE)
		

def search_artist(keyword,amount):
	api_url = "https://app.genie.co.kr/search/category/artists.json?query={}&hl=false&pagesize={}&order=false&of=POPULAR&page=1".format(encode(keyword),amount)
	response = session.get(api_url).json()  # [개선1]
	
	ARTIST_SEARCH_RESULTS_NAME = {}
	ARTIST_SEARCH_RESULTS_ARTIST = {}
	ARTIST_SEARCH_RESULTS_CODE = {}
	ARTIST_SEARCH_COUNT = int(response['searchResult']['result']['artists']['total'])
	
	if ARTIST_SEARCH_COUNT < amount:
		amount = ARTIST_SEARCH_COUNT
		
	for i in range (0,amount,1):
		try:
			ARTIST_SEARCH_RESULTS_NAME [i] = decode(response['searchResult']['result']['artists']['items'][i]['artist_name']['original'])
			ARTIST_SEARCH_RESULTS_CODE [i] = int(response['searchResult']['result']['artists']['items'][i]['artist_id'])
		except IndexError:
			sys.exit(1)
	
	print("Here are the search results for %s:\n"%keyword)
	for i in range(0,amount,1):
		RESULT_STRING = "%s. %s"%(i+1,ARTIST_SEARCH_RESULTS_NAME[i])
		print(RESULT_STRING)
		
	divider()
	
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
		download_artist(SELECTED_ARTIST_CODE)
		

# ══════════════════════════════════════════════════════════════════════════════
# [12단계] URL 파싱 함수 (URL -> 액션 라우팅)
# ══════════════════════════════════════════════════════════════════════════════

def parse_user_input(url):
	global TYPE,CODE
	
	if "plmSeq" in url:
		TYPE = "Playlist"
		CODE = parse_code(url,TYPE)
		download_playlist(CODE)
		
	elif "axnm" in url:
		TYPE = "Album"
		CODE = parse_code(url,TYPE)
		download_album(CODE)
		
	elif "xxnm" in url:
		TYPE = "Artist"
		CODE = parse_code(url,TYPE)
		download_artist(CODE)
		
	elif "xgnm" in url:
		TYPE = "Track"
		CODE = parse_code(url,TYPE)
		parse_track_data(CODE,BITRATE)
		print("[info] Downloading %s - %s\n"%(ARTIST_NAME,SONG_NAME))
		filename = OUTPUT_PATH+"%s - %s"%(ARTIST_NAME,SONG_NAME)
		taskname = "%s. %s"%(1,SONG_NAME)
		download_track(DOWNLOAD_URL,filename,taskname)
		
	else:
		print("[error] Invalid URL: %s"%url)
		divider()
		sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# [13단계] 메인 함수 (Main - 대화형 메뉴 모드)
# ══════════════════════════════════════════════════════════════════════════════

def main():
	read_config()
	login(ID,PW)
	divider()

	# [개선4] raw string으로 변경: text=''' → text=r'''
	# ASCII 아트 안의 \____ 같은 패턴이 Python 3.12+에서 SyntaxWarning을 일으킴
	text=r'''===================================================
|     _____________   ____________     ____  __   |
|    / ____/ ____/ | / /  _/ ____/    / __ \/ /   |
|   / / __/ __/ /  |/ // // __/______/ / / / /    |
|  / /_/ / /___/ /|  // // /__/_____/ /_/ / /___  |
|  \____/_____/_/ |_/___/_____/    /_____/_____/  |
|                                                 |
===================================================
	 GENIE-DL v.1.1.0 (Improved) by vank0n (SJJeon)
	'''
	
	options = ['Download Song / Album / Artist / Playlist', 'Download Real-Time Chart', 'View Real-Time Chart', 'Search and Download Song','Search and Download Album','Search and Download Artist','Exit']
	selected = pick(options, text, multiselect=False, min_selection_count=1,indicator="=>")[1]
	
	if selected == 0:
		# [개선5] 원본에서 selected == 0이 2번 있는 버그 수정
		# parse_user_input()이 내부에서 다운로드까지 처리하므로
		# 그 아래에서 다시 parse_track_data를 호출하면 안 됨
		parse_user_input(input("Enter Song / Album / Playlist URL: "))
	elif selected == 1:
		download_realtime_chart(1,200)
	elif selected == 2:
		print_realtime_chart(1,200)
	elif selected == 3:
		search_track(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 4:
		search_album(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 5:
		search_artist(input("Enter Search Keyword: "),SEARCH_AMOUNT)
	elif selected == 6:
		sys.exit(1)
	
	divider()

# ══════════════════════════════════════════════════════════════════════════════
# [14단계] 프로그램 시작점 (Entry Point)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
	try:
		if DOWNLOAD_CHART == None and INPUT_URL == None:
			main()
		else:
			read_config()
			login(ID,PW)
			divider()
			
			if DOWNLOAD_CHART != None:
				c = DOWNLOAD_CHART.split("-")
				CHART_START = int(c[0])
				CHART_END = int(c[1])
				if CHART_END >= 200:
					CHART_END = 200
				download_realtime_chart(CHART_START,CHART_END)
			
			elif INPUT_URL != None:
				parse_user_input(INPUT_URL)
			
			divider()
	
	except KeyboardInterrupt:
		sys.exit(128 + signal.SIGINT)
