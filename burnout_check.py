import yaml
from pathlib import Path
from db_util import sum_times_range, get_user_mail_alias
from datetime import datetime, timezone, timedelta
#from tabulate import tabulate
from mail import send_mail


def load_users():
    pf = Path(__file__).parent.parent / "burnout.yaml"
    with open(str(pf), "r") as infi:
        # yaml file example:
        # alert@mail.address: whatever! can specify multiple receipents
        # db_user_id: hours per week to trigger allert
        return yaml.load(infi, yaml.Loader)


def get_alert_mails():
    receipents = []
    for k, v in load_users().items():
        if type(k) == str and "@" in k:
            receipents.append(k)
    return receipents


def get_scan_users():
    users = []
    for k, v in load_users().items():
        if type(k) == int:
            users.append((k, v))
    return users


def get_week_by_idx(idx):
    monday = get_current_monday() + timedelta(days=idx * 7)
    sunday = monday + timedelta(days=6)
    return monday.date(), sunday.date()


def get_current_monday():
    dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    wd = dt.weekday()
    #timezone.
    return dt - timedelta(days=wd)


def generate_report_user(args):
    id, hourperweek = args
    email, alias = get_user_mail_alias(id)
    tbl = []
    alert = False
    for i in range(-5, 1):
        mon, sun = get_week_by_idx(i)
        seconds = sum_times_range(id, mon, sun)
        #print(f"Got {alias} for {mon} - {sun} -> {seconds} hours -> {seconds / 3600} hours")
        hours = seconds / 3600
        overtime = hours - hourperweek
        if overtime >= 10.0:
            overtime = f"!!! Overtime {overtime:.1f} !!!"
            if i == 0:
                alert = True
        elif overtime > 0.0:
            overtime = f" Overtime {overtime:.1f}"
        else:
            overtime = ""
        tbl.append((f"{mon} - {sun}", f"{hours:.1f}", overtime))
    return email, alias, alert, tbl


if __name__ == "__main__":
    users = get_scan_users()
    supervisor = get_alert_mails()
    print("Checking users: ", users)
    for email, alias, alert, table in map(generate_report_user, users):
        if alert:
            alert = " ALERT"
            receiver = supervisor.append(email)
            msg = f"Hi {alias} and {', '.join(supervisor)}!\n\n"
        else:
            alert = ""
            receiver = [email]
            msg = f"Hi {alias}!\n\n"
        msg += "Here is your worktime report for the last 5 weeks.\n\n"
        for dt, hr, ov in table:
            if ov:
                msg += f"{dt}\n  {hr}h -> {ov} hours\n\n "
            else:
                msg += f"{dt}\n  {hr}h\n\n"
        msg += "I hope you have a great week!"
        send_mail(receiver, "Worktime Report" + alert, msg)
        

