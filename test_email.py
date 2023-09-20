import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader
from mongoengine import connect

import dao.trade.trade_service as t_service
from dao.odm.future_trade import BottomOpenVolumeTip
from utils.common_tools import tz_utc_8


def rende_tip(tip: BottomOpenVolumeTip):
    tip.direction = "买" if tip.direction == 1 else "卖"
    tip.dkline_time = tip.dkline_time.strftime("%Y-%m-%d")
    return tip


today = datetime.now().strftime("%Y-%m-%d")
environment = Environment(loader=FileSystemLoader("templates/"))
results_template = environment.get_template("last_bottom_tips.html")
results_filename = "students_results.html"
db_url = "mongodb://host.docker.internal:27017/future_trade?authSource=admin"
connect(host=db_url, tz_aware=True, tzinfo=tz_utc_8)
tips = t_service.get_last_bottom_tips()
context = {"today": today, "tips": map(rende_tip, tips)}
# with open(results_filename, mode="w", encoding="utf-8") as results:
#     results.write(results_template.render(context))
#     print(f"... wrote {results_filename}")


me = "173028718@qq.com"
pwd = "vuyiuqsnxuribgia"
you = "173028718@qq.com"


msg = MIMEMultipart()

msg["Subject"] = f"摸底策略-{today}"
msg["From"] = me
# msg["To"] = (
#     Address("me", "173028718", "qq.com"),
#     Address("shanshan", "471176315", "qq.com"),
# )
# msg["To"] = ["471176315@qq.com", "173028718@qq.com"]
msg["To"] = "471176315@qq.com,173028718@qq.com"
msg.attach(MIMEText(results_template.render(context), "html"))

# Send the message via our own SMTP server.
s = smtplib.SMTP_SSL("smtp.qq.com", 465)
s.login(me, pwd)
s.send_message(msg)
s.quit()
