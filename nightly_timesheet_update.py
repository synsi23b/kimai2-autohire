from kimai_util import Angestellter
import db_util
#import argparse
import logging
from pathlib import Path
from datetime import date, timedelta, datetime
from mail import send_mail
import calendar


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


def update_breaktimes(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.update_breaktime(day)


def insert_free_days_students(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.fill_missing_freeday(day)


def stop_overnight_timesheets(employees:list[Angestellter], day:date):
    mail_queue = []
    for ma in employees:
        if db_util.stop_open_sheets(ma._id, day):
            logging.warning(f"Stopped open sheet for {ma._alias}")
            mail_queue.append(ma)
    if mail_queue:
        # create mail message and send to admins
        admins_mails = [x._email for x in Angestellter.get_all_active("ROLE_ADMIN") if x.receive_admin_mails()] + [ "hr-admin@leap-in-time.com" ]
        for ma in mail_queue:
            msg = f"Guten morgen!\n\nHeute morgen wurde ein Timesheet von\n\n{ma._alias}\n\nautomatisch gestoppt.\nHier ein Admin-link zu allen Autostop Zeiten: https://worktime.leap-in-time.de/de/team/timesheet/?tags=Autostop \n\nBeim korrigieren das Schlagwort >Autostop< am besten entfernen, dann verschwindet der Eintrag auch aus dieser Zussammenfassung."
            send_mail(set(admins_mails + [ma._email]), "Automatisch gestopptes Timesheet", msg)


def run_corrections_for_yesterday(day=None):
    if day is None:
        day = (datetime.utcnow() - timedelta(days=1)).date()
    logging.info(f"Running nightly corrections {day}")
    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    schueler = Angestellter.get_all_active("SCHUELERAUSHILFE")
    insert_public_holidays(empl + stud + schueler, day)
    insert_auto_worktime(empl + stud + schueler, day)
    stop_overnight_timesheets(empl + stud + schueler, day)
    insert_free_days_students(stud + schueler, day)
    check_not_worked(empl, day)
    update_breaktimes(empl + stud + schueler, day)
    update_flextime(empl, day)


def run_corrections_for_range(startday:date, endday:date=None):
    if endday is None:
        endday = (datetime.utcnow() - timedelta(days=1)).date()
    while startday <= endday:
        run_corrections_for_yesterday(startday)
        startday += timedelta(days=1)


def run_past_breaktimes():
    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    schueler = Angestellter.get_all_active("SCHUELERAUSHILFE")
    for ma in empl:
        # get user registering date
        day = ma.get_first_record_date()
        # get today for range checking in the loop
        today = datetime.utcnow().date()
        while day < today:
            ma.update_breaktime(day)
            day = day + timedelta(days=1)
    for st in stud + schueler:
        # get user registering date
        first = st.get_first_record_date()
        cal = date(2022, 11, 23)
        day = max(first, cal)
        # get today for range checking in the loop
        today = datetime.utcnow().date()
        while day < today:
            st.update_breaktime(day)
            day = day + timedelta(days=1)


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


def run_past_student_free_days_until(day:date):
    empl = Angestellter.get_all_active("WERKSTUDENT")
    empl += Angestellter.get_all_active("SCHUELERAUSHILFE")
    for ma in empl:
        # get user registering date
        corday = ma.get_first_record_date()
        while corday < day:
            ma.fill_missing_freeday(corday)
            corday += timedelta(days=1)


def update_flextime(employees:list[Angestellter], day:date):
    # if the day for the input date is 19, it means we have the 20th, since its yesterdays date
    if day.day == 19:
        # create the checkpoint 1 month earlier on the 20th for range 20 .. 19 on the exports
        day = day - timedelta(days=30)
        day = day.replace(day=20)
        logging.info(f"Running flextime checkpoint for day: {day}")
        for ma in employees:
            ma.update_flextime(day)


if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    #run_past_corrections_for_every_active_user()
    #run_past_breaktimes()
    #run_past_student_free_days_until(date(2023,1,28))
    ret = -1
    try:
        run_corrections_for_yesterday()
        #run_corrections_for_range(date(2023, 2, 6))
        ret = 0
    except:
        logging.exception("Exception during nightly run!")
    exit(ret)
