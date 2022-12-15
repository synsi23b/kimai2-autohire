from kimai_util import Angestellter
import db_util
#import argparse
import logging
from pathlib import Path
from datetime import date, timedelta, datetime



def update_breaktimes(employees:list[Angestellter], day:date):
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


if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    run_past_breaktimes_saldo_until(date(2022, 11, 22))
    #run_past_corrections_for_every_active_user()
    #run_past_breaktimes()
