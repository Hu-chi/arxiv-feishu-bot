# encoding: utf-8
# based on https://github.com/kobiso/get-daily-arxiv-noti
import base64
import hashlib
import hmac
import sqlite3
import urllib.request
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import NEW_SUB_URL, KEYWORD_LIST, WEBHOOK_SECRET, WEBHOOK_URL

timestamp = int(datetime.now().timestamp())


def gen_sign(secret: str):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign


def send_to_bot(content: dict):
    sign = gen_sign(WEBHOOK_SECRET)

    params = {
        "timestamp": timestamp,
        "msg_type": "interactive",
        "sign": sign,
        "card": content
    }

    resp = requests.post(WEBHOOK_URL, json=params)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") and result.get("code") != 0:
        print(f"Message Send Error For: %s" % result['msg'])
        return False
    return True


def filter_paper(paper, keyword_list):
    for keyword in keyword_list:
        if keyword.lower() in paper["abstract"].lower() \
                or keyword.lower() in paper["title"].lower():
            return False
    return True


def main():
    page = urllib.request.urlopen(NEW_SUB_URL)
    soup = BeautifulSoup(page, 'html.parser')
    content = soup.body.find("div", {'id': 'content'})

    issue_title = content.find("h3").text
    dt_list = content.dl.find_all("dt")
    dd_list = content.dl.find_all("dd")
    arxiv_base = "https://arxiv.org/abs/"

    assert len(dt_list) == len(dd_list)

    keyword_list = KEYWORD_LIST
    paper_list = []

    conn = sqlite3.connect('paper.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE PAPER(NAME  TEXT    NOT NULL);''')
        conn.commit()
    except Exception:
        pass

    def check_in_sql(paper):
        cursor = c.execute(
            "SELECT NAME FROM PAPER WHERE NAME = '{}'".format(paper['title'])
        )
        return len(cursor.fetchall()) > 0

    for i in range(len(dt_list)):
        paper = {}
        paper_number = dt_list[i].text.strip().split(" ")[2].split(":")[-1]
        paper['main_page'] = arxiv_base + paper_number
        paper['pdf'] = arxiv_base.replace('abs', 'pdf') + paper_number

        paper['title'] = dd_list[i].find(
            "div", {"class": "list-title mathjax"}
        ).text.replace("Title: ", "").strip()

        paper['authors'] = dd_list[i].find(
            "div", {"class": "list-authors"}
        ).text.replace("Authors:\n", "").replace("\n", "").strip()

        paper['subjects'] = dd_list[i].find(
            "div", {"class": "list-subjects"}
        ).text.replace("Subjects: ", "").strip()

        paper['abstract'] = dd_list[i].find(
            "p", {"class": "mathjax"}
        ).text.replace("\n", " ").strip()

        if not filter_paper(paper, keyword_list) and not check_in_sql(paper):
            paper_list.append(paper)

    card_content = {
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True
        },
        "elements": [],
        "header": {
            "template": "blue",
            "title": {
                "content": "今日论文推荐",
                "tag": "plain_text"
            }
        }
    }

    for idx, paper in enumerate(paper_list):
        card_content["elements"].append({
            "tag": "div",
            "text": {
                "content":
                    "[{}] [{}]({})\n - **Authors:** {}\n - **Subjects:** {}\n ".format(
                        idx, paper['title'], paper['main_page'],
                        paper['authors'], paper['subjects']),
                "tag": "lark_md"
            }
        })
        if idx != len(paper_list) - 1:
            card_content["elements"].append({
                "tag": "hr"
            })
        c.execute(
            "INSERT INTO PAPER (NAME) VALUES ('{}')".format(paper['title'])
        )

    conn.commit()
    conn.close()

    if len(paper_list) == 0:
        card_content["elements"].append({
            "tag": "div",
            "text": {
                "content": "No papers to follow today.",
                "tag": "lark_md"
            }
        })
    card_content["elements"].append({
        "actions": [
            {
                "tag": "button",
                "text": {
                    "content": "查看今日全部论文",
                    "tag": "plain_text"
                },
                "type": "primary",
                "url": NEW_SUB_URL
            }
        ],
        "tag": "action"
    })

    send_to_bot(card_content)


if __name__ == '__main__':
    main()
