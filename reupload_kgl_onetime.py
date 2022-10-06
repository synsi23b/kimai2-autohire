import datetime
import yaml
import pytz
from pathlib import Path
from babel.dates import format_date
from openpyxl import load_workbook
from kimai_util import get_gen_projects
import db_util
import logging
from mail import send_mail
import argparse
import calendar
import convertapi
from kgl_online import WebPortal
import shutil


THIS_LOCATION = Path(__file__).parent.resolve()

def main(kgl_cred):

    month = "09"
    year = "22"

    reportfolder = thisfile.parent.parent / "reports_kgl"
    if not reportfolder.is_dir():
        logging.info("report folder not found, creating it")
        reportfolder.mkdir()
    
    report_to_kgl = [str(x) for x in reportfolder.glob(f"./Stundenzettel*{month}_{year}*.pdf")]

    if report_to_kgl:
        with WebPortal(kgl_cred) as kgl:
            kgl.login()
            kgl.upload_timesheets(report_to_kgl, year, month)
    return 0

if __name__ == "__main__":
    thisfile = Path(__file__).resolve()
    logging.basicConfig(filename=str(thisfile.parent.parent / f"kimai2_autohire_{thisfile.stem}.log"), 
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    try:
        with open(str(THIS_LOCATION.parent / "kgl_cred.yaml")) as inf:
            kgl_cred = yaml.load(inf, yaml.Loader)
        ret = main(kgl_cred)
    except Exception as e:
        logging.exception(f"Uncaught exception in from main! {e}")
        ret = -1
    exit(ret)