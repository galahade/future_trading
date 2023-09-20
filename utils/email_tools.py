import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

import dao.trade.trade_service as t_service
from dao.odm.future_trade import BottomOpenVolumeTip
from utils import global_var as gvar


def rende_tip(tip: BottomOpenVolumeTip):
    tip.direction = "买" if tip.direction == 1 else "卖"
    tip.dkline_time = tip.dkline_time.strftime("%Y-%m-%d")
    return tip


def send_bottom_email():
    today = datetime.now().strftime("%Y-%m-%d")
    environment = Environment(loader=FileSystemLoader("templates/"))
    results_template = environment.get_template("last_bottom_tips.html")
    tips = t_service.get_last_bottom_tips()
    context = {
        "today": today,
        "tips": map(rende_tip, tips),
        "env_name": gvar.ENV_NAME,
    }

    me = "173028718@qq.com"
    pwd = "vuyiuqsnxuribgia"

    msg = MIMEMultipart()

    msg["Subject"] = f"摸底策略-{today}-{gvar.ENV_NAME}"
    msg["From"] = me
    msg["To"] = "471176315@qq.com,86077076@qq.com,173028718@qq.com"
    # msg["To"] = "173028718@qq.com"
    msg.attach(MIMEText(results_template.render(context), "html"))

    s = smtplib.SMTP_SSL("smtp.qq.com", 465)
    s.login(me, pwd)
    s.send_message(msg)
    s.quit()
