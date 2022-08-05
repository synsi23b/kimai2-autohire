import email, smtplib, ssl
from kimai_util import get_email_credentials
from pathlib import Path

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_mail(receiver:list, subject:str, plain:str, attachments=[], html=""):
    sender, passw, server, port = get_email_credentials()
    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender
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
            print("Error: Attempt to attach none existing file: ", fname)
            continue
        part = None
        with open(str(fname), "rb") as infile:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            part.set_payload(infile.read())
            # Encode file in ASCII characters to send by email    
        encoders.encode_base64(part)
        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {fname.name}",
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


if __name__ == "__main__":
    subj = "Test Email"
    receiver = "mail@himitsu.dev"
    plain = "Hello There!"
    html = html_header(2, "Hello There!") \
      + html_para("This is a test email.") \
      + html_link("Go To KIMAI", "kimai.org")
    html = encapsulate_html_with_body(html)
    send_mail(receiver, subj, plain, html, ["./requirements.txt", "README.md"])