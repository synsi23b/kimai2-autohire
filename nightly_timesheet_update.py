from kimai_util import Angestellter
import db_util
#import argparse
import logging
from pathlib import Path
from datetime import date, timedelta, datetime


def insert_public_holidays(employees:list[Angestellter], day:date):
    holidays = db_util.get_holidays(day, day)
    for hol in holidays:
        logging.info(f"Checking inserts for public holiday: {hol}")
        for ma in employees:
            ma.import_holiday_on_day(hol)


def check_not_worked(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.fill_missing_workday(day)


def insert_auto_worktime(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.insert_auto_worktime(day)


def stop_overrun_timesheets():
    mail_queue = []
    for ma in Angestellter.get_all_active("ANGESTELLTER"):
        for overrun in db_util.get_open_overrun_sheets(ma._id):
            print(f"Overrun {overrun} for user {ma._email} -> stop and put into mail Queue")
            mail_queue.append((overrun, ma._alias))
    if mail_queue:
        # create mail message and send to admins
        msg = "Guten morgen!\n\nFolgende Timesheets waren heute morgen laenger als erlaubt und wurden automatisch gestoppt.\n\n"
        for sm in mail_queue:
            msg += f"{sm[1]}: Gestartet um {sm[0][1]}"
        admins_mails = [x._email for x in Angestellter.get_all_active("ROLE_ADMIN") if x.receive_admin_mails()]
            

def run_corrections_for_yesterday():
    day = (datetime.utcnow() - timedelta(days=1)).date()
    logging.info(f"Running nightly corrections {day}")
    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    schueler = Angestellter.get_all_active("SCHUELERAUSHILFE")
    insert_public_holidays(empl + stud + schueler, day)
    insert_auto_worktime(empl + stud + schueler, day)
    check_not_worked(empl, day)


def run_past_corrections_for_every_active_user():
    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    schueler = Angestellter.get_all_active("SCHUELERAUSHILFE")
    for ma in empl + stud + schueler:
        # get user registering date
        day = ma.get_registration_date()
        # make fake user list for reuisng functions
        mal = [ ma ]
        # get today for range checking in the loop
        today = datetime.utcnow().date()
        while day < today:
            insert_public_holidays(mal, day)
            if day > date(2022, 11, 22):
                insert_auto_worktime(mal, day)
            if ma._role == "ANGESTELLTER":
                check_not_worked(mal, day)
            day = day + timedelta(days=1)


if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    #run_past_corrections_for_every_active_user()
    run_corrections_for_yesterday()
