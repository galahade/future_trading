# Import smtplib for the actual sending function
import smtplib

# Import the email modules we'll need
from email.message import EmailMessage

me = "173028718@qq.com"
pwd = "vuyiuqsnxuribgia"
you = "173028718@qq.com"
msg = EmailMessage()
msg.set_content("this is a test email")
msg["Subject"] = "The contents of email"
msg["From"] = me
msg["To"] = you

# Send the message via our own SMTP server.
s = smtplib.SMTP_SSL("smtp.qq.com", 465)
s.login(me, pwd)
s.send_message(msg)
s.quit()
