from dotenv import load_dotenv
import os 
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from slack_sdk import WebClient
import time
import requests
import json
import pymysql
import pandas as pd

# 환경변수 import 
load_dotenv()
host = os.getenv("keeper_host")
user = os.getenv("keeper_user")
password = os.getenv("keeper_password")
db = os.getenv("keeper_db")

appKey = os.getenv("nhn_appKey")
secretKey = os.getenv("nhn_secretKey")
senderKey = os.getenv("nhn_senderKey")

kcms_id = os.getenv("kcms_id")
kcms_pw = os.getenv("kcms_pw")

#전역변수 선언부
conn = None
cur = None
sql=""


#접속정보  -- 접속정보 변수 목적에 맞게 변경
conn = pymysql.connect(host=host, 
                       user=user, 
                       password=password, 
                       db=db, 
                       charset='utf8')

#커서생성
cur = conn.cursor()

#실행할 sql 구문 
sql= """
select 
	b.name AS br_name,
	mk.member_keeper_id,
	mk.name AS kp_name,
	mk.phone,
	mk.state_code,
	b.kakao_link,
	DATE_FORMAT(mk.insert_at, '%Y-%m-%d') AS insert_at
from member_keeper as mk 
LEFT JOIN branch b
	ON mk.cl_cd = b.cl_cd
	AND mk.branch_id = b.branch_id
where 
	mk.LEVEL = 30
	and (mk.memo IS NULL OR mk.memo IN (''))
	and DATE_FORMAT(mk.insert_at, '%Y-%m-%d') >= '2023-10-01'
	and b.branch_id IS NOT NULL
	and state_code = 'WAIT'
	and LEFT(b.kakao_link,1) = 'h'
    and b.cl_cd not in ('Z0001')
ORDER BY
	insert_at
;
"""  ## sql query 문 입력

# cursor 객체를 이용해서 수행
cur.execute(sql)

# select 된 결과 셋 얻어오기
result = cur.fetchall()  # tuple 이 들어있는 list

#sql 접속 종료
conn.commit()
conn.close()

#sql 결과 데이터프레임 및 변수 설정
df = pd.DataFrame(result)
last_row = len(df)
print(df)
print(f"총 {last_row}건")


### 알림톡 API 발송을 위한 변수 설정 ###
i = 0 
result_day = datetime.now().strftime("%d")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


### 슬랙 API 및 메시지 발송 변수 설정 ###
slack_token = os.getenv("normal_bot_token")
client = WebClient(token=slack_token)
success_cnt = 0 
error_cnt = 0 
error_code = []
error_message = []
error_keeper = []


### keeper WEB 로그인 ###

#크롬드라이브 옵션 설정
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('headless')
chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 1})
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

#크롬 페이지 열기
driver.get('https://kcms.11c.co.kr/')

# 로그인
search_box = driver.find_element(By.XPATH, "//*[@id='root']/section/div[2]/div[1]/div[2]/div[1]/input")
search_box.send_keys(kcms_id)
search_box = driver.find_element(By.XPATH, "//*[@id='root']/section/div[2]/div[1]/div[2]/div[2]/input")
search_box.send_keys(kcms_pw)

login_button = driver.find_element(By.XPATH, "//*[@id='root']/section/div[2]/div[1]/div[2]/button")
login_button.click()
time.sleep(2)


# API 발송 반복문 설정 
for i in range(0,last_row) :
    
    ###비즈알림톡 API 변수 설정
    app_key = appKey
    secret_key = secretKey
    sender_key = senderKey
    template_code = "keeper_callback"
    
    ### 비즈알림톡 발신내용 변수 설정
    recipient_no = df.loc[i,3]
    template_parameter = {
        "name": df.loc[i,2] , 
        "branch" : df.loc[i,0] ,
        "ch_url" : df.loc[i,5] ,
        "ytb_url" : "https://m.youtube.com/watch?v=MlMheHn0vJg",  
    }

    # API 엔드포인트 URL
    url = f"https://api-alimtalk.cloud.toast.com/alimtalk/v2.3/appkeys/{app_key}/messages"

    # 요청 헤더 설정
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-Secret-Key": secret_key
    }

    # 요청 본문 데이터 설정
    requestBody = {
        "senderKey": sender_key,
        "templateCode": template_code,
        "recipientList": [{
            "recipientNo": recipient_no,
            "templateParameter": template_parameter,
            "resendParameter": {
              "isResend" : True,
              "resendTitle" : "열한시 키퍼",
              "resendSendNo" : "resend_number"
            }
        }]
    }
    
    # POST 요청 보내기
    response = requests.post(url, headers=headers, json=requestBody)
    response_text = json.loads(response.text)
    response_Code = response_text['header']['resultCode']
    response_message = response_text['header']['resultMessage']


    ### 알림톡 발송 후 결과값 입력 ###   
    # 변수 설정
    keeper_id = df.loc[i,1]
    keeper_name = df.loc[i,2]
    
    ### 알림톡 발송 성공 시 ###
    if response_Code == 0 : 

        #계정상세페이지 접속
        driver.get(f'https://kcms.11c.co.kr/account-fulfillments-detail/{keeper_id}/')

        memo = driver.find_element(By.NAME, "targetMemo")
        memo.send_keys(f'{result_day}')

        convert = driver.find_element(By.XPATH, "//*[@id='root']/div/div[1]/div[5]/button[2]")
        convert.click()
        time.sleep(1)
        
        #성공건수 count
        success_cnt = success_cnt + 1
        

    ### 알림톡 발송 실패 시 ###
    else : 
          
        #계정상세페이지 접속
        driver.get(f'https://kcms.11c.co.kr/account-fulfillments-detail/{keeper_id}/')

        memo = driver.find_element(By.NAME, "targetMemo")
        memo.send_keys(f"발송실패 ({response_Code})")

        convert = driver.find_element(By.XPATH, "//*[@id='root']/div/div[1]/div[5]/button[2]")
        convert.click()
        time.sleep(1)

        # 에러건수 count 
        error_cnt = error_cnt + 1 
        error_message.append(response_message)
        error_code.append(response_Code)
        error_keeper.append(keeper_name)


#크롬 종료 
driver.quit()

### API 호출 결과 슬랙메시지 발송 ###
response_slack = client.chat_postMessage(
channel="C05PKAP3PK6",      # 채널 id를 입력합니다.
text=     f"💌 신규키퍼 알림톡 자동발송\n\n" 
        + f"   ● 실행일시 : {now}\n"
        + f"   ● 실행건수 : {last_row} 건\n"
        + f"   ● 결과 : 성공 {success_cnt} 건  / 실패 {error_cnt} 건\n"
        + f"         ○ error_code : {error_code}\n"
        + f"         ○ error_keeper : {error_keeper}"
        )


#터미널창 결과 입력
print("파이썬실행_알림톡발송")
print(now)
print(f"성공 {success_cnt} 건  / 실패 {error_cnt} 건")
print(f"{error_message}")