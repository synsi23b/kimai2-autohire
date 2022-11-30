from kimai_util import Angestellter
import db_util
#import argparse
import logging
from pathlib import Path
from datetime import date, timedelta, datetime


def insert_public_holidays(employees:list, students:list, day:date):
    holidays = db_util.get_holidays(day, day)
    holiconfig = db_util.get_configuration("vacation", False)
    for idx, day in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        holiconfig[f"holiday_{idx}"] = holiconfig[f"vacation.daily_working_time_meta_name_{day}"]

    for hol in holidays:
        for ma in employees + students:
            ma.import_holiday_on_day(hol, holiconfig)


if __name__ == "__main__":
    thisfile = Path(__file__)
    logging.basicConfig(filename=str(thisfile.parent.parent.resolve() / f"kimai2_autohire_{thisfile.stem}.log"),
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    yesterday = (datetime.utcnow() - timedelta(days=1)).date()
    yesterday = date(2022, 12, 25)
    insert_public_holidays(empl, stud, yesterday)