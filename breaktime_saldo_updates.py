from kimai_util import Angestellter
#import db_util
import argparse
import logging
from pathlib import Path
from datetime import date, timedelta



def update_breaktimes_on_day(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.update_breaktime(day)


def update_saldo(employees:list[Angestellter], day:date):
    for ma in employees:
        ma.update_saldo(day)


def run_past_breaktimes_saldo_until(day:date):
    empl = Angestellter.get_all_active("ANGESTELLTER")
    for ma in empl:
        # get user registering date
        corday = ma.get_first_record_date()
        while corday < day:
            ma.update_breaktime(corday)
            corday += timedelta(days=1)
    update_saldo(empl, day)


def run_breaktime_update_90_days():
    # run the check for the past 90 days
    today = date.today()
    minus90 = today - timedelta(days=90)
    plus1 = timedelta(days=1)
    for ma in Angestellter.get_all_active("ANGESTELLTER"):
        firstday = ma.get_first_record_date()
        calcday = max(minus90, firstday)
        while calcday <= today:
            ma.update_breaktime(calcday)
            calcday += plus1


if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    #parser = argparse.ArgumentParser(
    #                prog = 'BreakTime & Saldo Calculator',
    #                description = 'Go through the daily records and adjust the minium break times of employees. Also calculate their Overtime.')
    #parser.add_argument()

    #run_past_breaktimes_saldo_until(date(2022, 11, 23))
    #run_past_corrections_for_every_active_user()
    #run_past_breaktimes()
    run_breaktime_update_90_days()
