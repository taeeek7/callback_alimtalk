from dotenv import load_dotenv
from SqlUtils import SqlUtils
from AlimtalkUtils import AlimtalkUtils
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from slack_sdk import WebClient
import time, os

# 환경변수 import 
load_dotenv()
host = os.getenv("keeper_host")
user = os.getenv("keeper_user")
password = os.getenv("keeper_password")
db = os.getenv("keeper_db")

kcms_id = os.getenv("kcms_id")
kcms_pw = os.getenv("kcms_pw")

slack_token = os.getenv("normal_bot_token")
client = WebClient(token=slack_token)

def get_data() : 
    df = SqlUtils(host, user, password, db, 
    f"""
    select 
        b.name AS br_name,
        mk.member_keeper_id,
        mk.name AS kp_name,
        mk.phone,
        mk.state_code,
        REPLACE(b.kakao_link,'http://','') AS kakao_link,
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
    """
    ).extract_db()

    return df

#sql 결과 데이터프레임 및 변수 설정
df = get_data()
last_row = len(df)


def callback_send_main() : 
    ### 알림톡 API 발송을 위한 변수 설정 ###
    i = 0 
    result_day = datetime.now().strftime("%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    ### 발송 변수 설정 ###
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
        access_key = os.getenv("ALIMTALK_ACCESS_KEY")
        secret_key = os.getenv("ALIMTALK_SECRET_KEY")
        alimtalk_client = AlimtalkUtils(access_key, secret_key)
        
        ### 비즈알림톡 발신내용 변수 설정
        recipient_no = df.loc[i,3]
        name = df.loc[i,2]
        branch = df.loc[i,0]
        ch_url = df.loc[i,5]
        ytb_url = "m.youtube.com/watch?v=MlMheHn0vJg"

        body = {
            "plusFriendId": "@열한시키퍼",
            "templateCode": "CallbackMessage",
            "messages": [
                {
                    "to": f"{recipient_no}",
                    "title": "안녕하세요 키퍼님",
                    "content": f"안녕하세요 {name} 키퍼님, 열한시 클리닝 {branch}에 지원해 주셔서 감사합니다!\n\n업무 상담과 궁금하신 내용 문의는 [열한시클리닝_{branch}] 채널을 통해 진행됩니다.\n\n상담 시 성함과 연락처를 함께 남겨주시면 빠르고 정확한 답변이 가능하며, 이후 지점 담당자가 확인하여 답변드리도록 하겠습니다.\n\n답변을 기다리시는 동안 교육 영상 시청을 부탁드립니다.\n\n감사합니다.",
                    "buttons": [
                        {
                            "type": "WL",
                            "name": "교육 영상 시청하기",
                            "linkMobile": f"https://{ytb_url}",
                            "linkPc": f"https://{ytb_url}"
                        },
                        {
                            "type": "WL",
                            "name": "지점 채널로 이동하기",
                            "linkMobile": f"https://{ch_url}",
                            "linkPc": f"https://{ch_url}"
                        },
                    ],
                    "useSmsFailover": False,
                }
            ],
        }

        response_text = alimtalk_client.send_alimtalk(body= body)
        response_Code = response_text['statusCode']
        response_message = response_text['messages'][0]['requestStatusDesc']

        print(response_text)
        ### 알림톡 발송 후 결과값 입력 ###   
        # 변수 설정
        keeper_id = df.loc[i,1]
        keeper_name = df.loc[i,2]
        
        ### 알림톡 발송 성공 시 ###
        if response_Code == 202 : 

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
    client.chat_postMessage(
    channel="C05PKAP3PK6",      # 채널 id를 입력합니다.
    text=     f"💌 신규키퍼 알림톡 자동발송\n\n" 
            + f"   ● 실행일시 : {now}\n"
            + f"   ● 실행건수 : {last_row} 건\n"
            + f"   ● 결과 : 성공 {success_cnt} 건  / 실패 {error_cnt} 건\n"
            + f"         ○ error_code : {error_code}\n"
            + f"         ○ error_keeper : {error_keeper}"
    )


    #터미널창 결과 입력
    print(f"{now}_파이썬실행_알림톡발송_성공 {success_cnt} 건  / 실패 {error_cnt} 건")
    print(f"{error_message}")

    return 



if __name__ == "__main__" : 
    try :
        callback_send_main()
    except Exception as e :
        client.chat_postMessage(
            channel="C06FQURRGCS",
            text=  f"*🤬 callback alimtalk 오류 알림*\n\n ● 오류내용 : {e}\n"
        )