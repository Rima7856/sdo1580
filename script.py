import requests
import re
import time
import pickle
import os
from pathlib import Path
from html import unescape
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL")
LOGIN_URL = os.getenv("LOGIN_URL")
QUIZ_URL = os.getenv("QUIZ_URL")
COOKIE_FILE = os.getenv("COOKIE_FILE")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")


def save_session(session):
    try:
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(session.cookies, f)
        print("💾 save session")
        return True
    except Exception as e:
        print(f"❌ error session: {e}")
        return False

def load_session(session):
    try:
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'rb') as f:
                cookies = pickle.load(f)
                session.cookies.update(cookies)
            print("📂 session loaded from file.")
            return True
    except Exception as e:
        print(f"⚠️ error import session: {e}")

    return False

def clear_session():
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
            print("🗑️ old session has deleted.")
    except Exception as e:
        print(f"⚠️ error with deleting session: {e}")

def is_session_valid(session):
    try:
        response = session.get(QUIZ_URL, timeout=10, allow_redirects=True)
        if "login/index.php" in response.url or response.status_code == 403:
            print("⚠️ redirection on login has found!")
            return False
        if re.search(r'"sesskey":"([^"]+)"', response.text):
            return True
    except Exception as e:
        print(f"⚠️ Ошибка при проверке сессии: {e}")
    return False

def authenticate(session):
    try:
        print("🔍 base page...")
        res = session.get(LOGIN_URL, timeout=10)
        token_match = re.search(r'name="logintoken" value="([^"]+)"', res.text)
        if not token_match:
            print("❌ can't search logintoken!")
            return False
        token = token_match.group(1)

        print("🔐 send credentials...")
        login_res = session.post(LOGIN_URL, data={
            'logintoken': token,
            'username': USERNAME,
            'password': PASSWORD
        }, timeout=10)

        time.sleep(1)
        if is_session_valid(session):
            print("✅ good auth")
            return True
        else:
            print("❌ error auth")
            return False

    except Exception as e:
        print(f"❌ Ошибка при аутентификации: {e}")
        return False

def get_authenticated_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    if load_session(session):
        if is_session_valid(session):
            print("✅ using save session.")
            return session
        else:
            print("⚠️ this session has expired. deleting...")
            clear_session()
    print("🔐 creating new session...")
    if authenticate(session):
        save_session(session)
        return session
    print("❌ failed to establish session!")
    return None

def get_quiz_data(session):
    try:
        print("📡get status answer...")
        quiz_res = session.get(QUIZ_URL, timeout=10, allow_redirects=True)
        print(f"   URL: {quiz_res.url}")
        print(f"   status: {quiz_res.status_code}")
        sk_match = re.search(r'"sesskey":"([^"]+)"', quiz_res.text)
        if not sk_match:
            print("❌ sesskey not found on page!")
            print("check authorization or test URL")
            return None, None
        sk = sk_match.group(1)
        fn_match = re.search(r'name="(q\d+:\d+_answer)"', quiz_res.text)
        if not fn_match:
            print("❌ no fields found!")
            print("   the test may have already been completed or the URL may be incorrect..")
            return None, None
        fn = fn_match.group(1)
        print(f"✅ data has been gotten, field: {fn}")
        return sk, fn
    except Exception as e:
        print(f"❌ error with getting data: {e}")
        return None, None

def extract_test_results(html):
    try:
        rows = re.findall(r'<tr[^>]*>\s*<td[^>]*>.*?</td>(.*?)</tr>', html, re.DOTALL)
        results = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 3:
                input_text = clean_cell(cells[0])
                expected = clean_cell(cells[1])
                got = clean_cell(cells[2])

                results.append({
                    'input': input_text,
                    'expected': expected,
                    'got': got
                })
        return results
    except Exception as e:
        print(f"⚠️ error parsing: {e}")
        return []

def clean_cell(cell_html):
    cell_html = re.sub(r'<i\s+class="icon.*?</i>', '', cell_html, flags=re.DOTALL)
    cell_html = re.sub(r'<br\s*/?>', '\n', cell_html)
    cell_html = re.sub(r'</?pre[^>]*>', '', cell_html)
    cell_html = re.sub(r'<[^>]+>', '', cell_html)
    cell_html = unescape(cell_html)
    cell_html = cell_html.strip()
    return cell_html

def send_code(session, sesskey, field_name, code_payload):
    try:
        print("🔄 load page test...")
        quiz_res = session.get(QUIZ_URL, timeout=10)
        if "login/index.php" in quiz_res.url:
            print("❌ session expired while requesting test!")
            return False
        html = quiz_res.text
        attempt_id = re.search(r'attempt=(\d+)', QUIZ_URL).group(1)
        cmid_id = re.search(r'cmid=(\d+)', QUIZ_URL).group(1)
        prefix = field_name.replace('_answer', '')
        seq_match = re.search(r'name="([^"]*' + prefix + r'[^"]*:sequencecheck)" value="(\d+)"', html)
        if not seq_match:
            print("❌ Sequencecheck not found! The attempt may have been terminated")
            return False
        seq_name = seq_match.group(1)
        seq_val = seq_match.group(2)
        this_page = re.search(r'name="thispage" value="(\d+)"', html).group(1)
        payload = {
            'attempt': attempt_id,
            'cmid': cmid_id,
            'sesskey': sesskey,
            'thispage': this_page,
            'scrollpos': '0',
            field_name: code_payload,
            seq_name: seq_val,
            f'{prefix}_-submit': '1'
        }

        print(f"🚀 sending code (seq:{seq_val})...")
        session.headers.update({'Referer': QUIZ_URL})
        PROCESS_URL = f"{BASE_URL}/mod/quiz/processattempt.php"
        session.post(PROCESS_URL, data=payload, timeout=10)

        print("⏳ getting answer (2сек)...")
        time.sleep(2)

        confirm = session.get(QUIZ_URL, timeout=10).text

        if "coderunner-test-results" in confirm:
            results = extract_test_results(confirm)

            if results:
                print("-" * 50)
                print()
                print("-" * 50)
                hehe_num = 0
                for i, result in enumerate(results, 1):
                    if hehe_num != 0:
                        break

                    #print(f"\n🧪 test #{i}")
                    #print(f"   enter: {result['input']}")
                    #print(f"   waiting: {result['expected']}")
                    print('-' * 21, 'RECEIVED', '-' * 21, sep='')
                    print(f"{result['got']}")
                    #print(f"   status: {'✅ good' if result['expected'] == result['got'] else '❌ not good'}")
                    hehe_num += 1
                print("\n" + "-" * 50)
            else:
                print("⚠️ no results found in the table.")
        else:
            print("⚠️ results table not found. please check your code syntax.")

        return True

    except Exception as e:
        print(f"❌error with sending code: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_infiltrator():
    session = get_authenticated_session()
    if session is None:
        return
    sk, fn = get_quiz_data(session)
    if sk is None or fn is None:
        print("❌ unable to retrieve data to send code.")
        return

    print(f"✅ready to go. ression key: {sk[:10]}..., field: {fn}")

    try:
        with open('solution.py', 'r', encoding='utf-8') as f:
            my_code = f.read()
        print("📄 code downloaded from solution.py")
    except FileNotFoundError:
        my_code = 'print("Hello from script")'
        print("⚠️ solution.py not found, placeholder used")

    send_code(session, sk, fn, my_code)

if __name__ == "__main__":
    try:
        run_infiltrator()
    except KeyboardInterrupt:
        print("\n⏹️  the script was terminated by the user.")
    except Exception as e:
        print(f"\n❌ critical error: {e}")
        import traceback
        traceback.print_exc()
