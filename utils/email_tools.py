import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

import dao.trade.trade_service as t_service
from dao.odm.future_trade import BottomOpenVolumeTip, MainDailyConditionTip
from utils import global_var as gvar


def render_tip(tip: BottomOpenVolumeTip):
    tip.direction = "做多" if tip.direction == 1 else "做空"
    tip.dkline_time = tip.dkline_time.strftime("%Y-%m-%d")
    return tip


def render_dctips(tip: MainDailyConditionTip):
    tip.direction = "做多" if tip.direction == 1 else "做空"
    tip.kline_time = tip.kline_time.strftime("%Y-%m-%d")
    return tip


def _send_email(subject: str, text: str):
    me = "173028718@qq.com"
    pwd = "vuyiuqsnxuribgia"

    msg = MIMEMultipart()

    msg["Subject"] = subject
    msg["From"] = me
    msg["To"] = "471176315@qq.com,86077076@qq.com,173028718@qq.com"
    msg.attach(MIMEText(text, "html"))

    s = smtplib.SMTP_SSL("smtp.qq.com", 465)
    s.login(me, pwd)
    s.send_message(msg)
    s.quit()


def send_before_trading_message():
    """盘前提示操作完成后，将生成的相关信息发送给相关人员"""
    today = datetime.now().strftime("%Y-%m-%d")
    template = Environment(loader=FileSystemLoader("templates/")).get_template(
        "before_trading_tips.html"
    )
    context = {
        "today": today,
        "daily_condition_tips": map(
            render_dctips, t_service.get_last_daily_condition_tips()
        ),
        "b_tips": map(render_tip, t_service.get_last_bottom_tips()),
        "env_name": gvar.ENV_NAME,
    }
    _send_email(f"盘前提示-{today}-{gvar.ENV_NAME}", template.render(context))


def send_trade_message(context: dict):
    template = Environment(loader=FileSystemLoader("templates/")).get_template(
        "trade_pos_message.html"
    )
    _send_email(
        f"开仓提示-{context['today']}-{context['env_name']}",
        template.render(context),
    )
