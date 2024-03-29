import email, smtplib, ssl
from kimai_util import get_email_credentials
from pathlib import Path

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import logging
from datetime import datetime


def send_mail(receiver:list, subject:str, plain:str, attachments=[], html=""):
    try:
        _send_mail(receiver, subject, plain, attachments, html)
    except Exception as e:
        logging.exception(e)

def _send_mail(receiver:list, subject:str, plain:str, attachments=[], html=""):
    logging.info(f"Sending mail to {receiver}")
    sender, passw, server, port = get_email_credentials()

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender
    if type(receiver) is str:
        message["To"] = receiver
    else:
        message["To"] = ", ".join(receiver)
    message["Subject"] = subject

    # Add body to email
    if plain:
        message.attach(MIMEText(plain, "plain"))
    if html:
        message.attach(MIMEText(html, "html"))

    # Add attachments
    for fname in attachments:
        fname = Path(fname)
        if not fname.is_file():
            logging.error(f"Error: Attempt to attach none existing file: {fname}")
            continue
        part = None
        with open(str(fname), "rb") as infile:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            if fname.suffix == ".xlsx":
                part = MIMEBase("application", 'vnd.ms-excel') 
            part.set_payload(infile.read())
            # Encode file in ASCII characters to send by email    
        encoders.encode_base64(part)
        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=fname.name,
        )
        # Add attachment to message
        message.attach(part)
    # convert to string and send message
    msg = message.as_string()
    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(server, port, context=context) as server:
            server.login(sender, passw)
            server.sendmail(sender, receiver, msg)
    elif port == 587:
        with smtplib.SMTP(server, port) as server:
            server.ehlo()  # Can be omitted
            server.starttls(context=context)
            server.ehlo()  # Can be omitted
            server.login(sender, passw)
            server.sendmail(sender, receiver, msg)
    report = f"TO: {receiver}\nATT: {[a.name for a in attachments]}\n\n{plain}\n\n{html}"
    mailf = Path(__file__).resolve().parent / "mails"
    ofname = f"{datetime.now().replace(microsecond=0)}  {receiver}"
    with open(str(mailf / ofname), "w") as outf:
        outf.write(report)


def get_absolute_path(filename:str) -> Path:
    thisf = Path(__file__).resolve()
    filesfold = thisf.parent / "files"
    filep = filesfold / filename
    return filep


def encapsulate_html_with_body(contents):
    return f"""\
<html>
    <body>
        {contents}
    </body>
</html>
"""


def html_header(size, text):
    return f"<h{size}>{text}</h{size}>\n"


def html_para(text):
    return f"<p>{text}</p>\n"


def html_link(text, dest):
    return f"<a href=\"{dest}\">{text}</a>\n"


def make_onboarding_msg(first:str, last:str, type:str, user:str, password:str) -> str:
    msg = f"""
Hallo {first} {last},

herzlich willkommen im Team von leap in time!

Die Arbeitszeiterfassung funktioniert bei uns digital über die Webseite:

https://worktime.leap-in-time.de

Um bezahlt zu werden, müssen Sie dort Ihre Arbeitszeiten korrekt angeben.
Eine Kurzanleitung wie das genau funktioniert und was dabei zu beachten ist finden Sie hier:

https://wiki.leap-in-time.de/en/public/onboarding/worktime

Ihre Login-Daten:
  Username: {user}
  Passwort: {password}

Aus Sicherheitsgründen sollten Sie das Passwort ändern, können es aber auch einfach so weiterverwenden.
Wenn Sie das Passwort vergessen haben, können Sie sich einen Wiederherstellungslink per E-Mail auf der Startseite zusenden lassen.

Ihre Einteilung ist in der Gruppe {type}.

Viel Spass!

#####################################################

Hello {first} {last},

Welcome to the leap in time team!

We use this website to record working hours digitally:

https://worktime.leap-in-time.de

In order to get paid you have to correctly submit your working hours there.
You will find short instructions on how this works and what you need to bear in mind here:

https://wiki.leap-in-time.de/en/public/onboarding/worktime

Your login data:
  Username: {user}
  Password: {password}

For security reasons you should change the password, but you can also continue to use it as it is.
If you forget the password, you can have a recovery link sent to you by email on the home page.

Your allocation is in the group {type}.

Have fun!

"""
    return msg


if __name__ == "__main__":
    subj = "Test Email"
    receiver = "mail@himitsu.dev"
    plain = "Hello There!"
    html = html_header(2, "Hello There!") \
      + html_para("This is a test email.") \
      + html_link("Go To KIMAI", "kimai.org")
    html = encapsulate_html_with_body(html)
    send_mail(receiver, subj, plain, html, ["./requirements.txt", "README.md"])

