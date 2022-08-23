import datetime
import yaml
import pytz
from pathlib import Path
from babel.dates import format_date
from openpyxl import load_workbook
from kimai_util import get_gen_projects
import logging
from mail import send_mail
import argparse


def utc_unaware_to_tz(dt:datetime, tz) -> datetime:
    dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.timezone(tz))


def fill_hours_files(alias:str, sheets:list, outfolder:Path, fileprefix:str = ""):
    company_data = {}
    this_location = Path(__file__).parent.resolve()
    print(this_location.parent)
    with open(str(this_location.parent / "kgl_info.yaml")) as inf:
        company_data = yaml.load(inf, yaml.Loader)
    fname = "Stundenzettel MM_JJ - Mitarbeiter_Lohn.xlsx"
    folder = this_location / "files"
    workbook = load_workbook(filename=str(folder / fname))
    wsheet = workbook.active

    # fill in company information
    wsheet["C1"] = company_data["name"]
    wsheet["C2"] = company_data["adr1"]
    wsheet["C3"] = company_data["adr2"]
    wsheet["C6"] = company_data["mail"]

    # basic time and user information
    wsheet["A11"] = alias
    wsheet["E11"] = format_date(sheets[0][-1], "MMMM", locale="de")
    wsheet["F11"] = sheets[0][-1].year
    wsheet["A14"] = str(sheets[0][-1].replace(day=1))

    # group sheets generated for the same day in the users TZ
    same_day = {}
    for s in sheets:
        date_tz = s[-1]
        if date_tz in same_day:
            same_day[date_tz].append(s)
        else:
            same_day[date_tz] = [s]

    timezone = sheets[0][12]
    for sl in same_day.values():
        # use first entry of the day as start time
        start = utc_unaware_to_tz(sl[0][4], timezone)
        #end = utc_unaware_to_tz(s[5], timezone)
        # get the sum of the duration of all timesheets of that day
        end = start + datetime.timedelta(seconds=sum([s[6] for s in sl]))
        if start.date() == end.date():
            row = 13 + start.day
            wsheet[f"C{row}"] = "Arbeit"
            wsheet[f"D{row}"] = start.strftime("%H:%M:00")
            wsheet[f"E{row}"] = end.strftime("%H:%M:00")
        else:
            # midnight roll over
            row = 13 + start.day
            wsheet[f"C{row}"] = "Arbeit"
            wsheet[f"D{row}"] = start.strftime("%H:%M:00")
            wsheet[f"E{row}"] = "24:00:00"
            row += 1
            wsheet[f"D{row}"] = "00:00:00"
            wsheet[f"E{row}"] = end.strftime("%H:%M:00")

    fname = fileprefix + fname.replace("MM_JJ", start.strftime("%m_%y")).replace("Mitarbeiter", alias.replace(" ", "_"))
    outf = outfolder / fname
    workbook.save(filename=str(outf))
    return outf


def create_reports(year:int, month:int, preliminary:bool, reportfolder:Path):
    logging.info(f"create reports for {month} {year} preliminary: {preliminary}")
    bmsg = f"""
Hello there!

This is your worktime report for {month}-{year}.
"""
    if preliminary:
        bmsg += """
This report is not the final report used for salary calculations, so please check it for any errors.

The final report will be generated on the 3rd of the following month.
"""
    else:
        bmsg += """
This report was exported and can't be changed anymore. It will be used to calculate your salary.
"""

    if preliminary:
        prefix = "Preliminary-"
    else:
        prefix = ""
    projects = get_gen_projects()
    owrk = []
    for proj in projects:
        logging.info(f"Working on project {proj._name}")
        workers = proj.get_workers(year, month)
        for wrk in workers:
            logging.info(f"Generating worker {wrk._alias}")
            month_ok, month_msg = proj.is_worker_month_ok(wrk)
            weeks_ok, weeks = proj.is_worker_weeks_ok(wrk)
            msg = bmsg + month_msg
            if not weeks_ok:
                msg += "\n\n!! You worked to many hours in one of the weeks !!\n"
            for week in weeks:
                msg += f"\n{week[1]}\n"
            repofile = fill_hours_files(wrk._alias, wrk._sheets, reportfolder, prefix)
            owrk.append((wrk, msg, repofile))
    return owrk


if __name__ == "__main__":
    thisfile = Path(__file__).resolve()
    logging.basicConfig(filename=str(thisfile.parent.parent / f"kimai2_autohire_{thisfile.stem}.log"), 
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

    parser = argparse.ArgumentParser(description="export timesheets for users of projects with *generate_sheets* in project description")
    parser.add_argument("--today", action="store_true", help="use today as a time base to generate monthly report rather than last month")
    #parser.add_argument("--lastmonth", action="store_true", help="wether or not this generation is preliminary, e.g. not a real export")
    parser.add_argument("--preliminary", action="store_true", help="wether or not this generation is preliminary, e.g. not a real export")

    args = parser.parse_args()

    outf = thisfile.parent.parent / "reports_kgl"
    if not outf.is_dir():
        logging.info("report folder not found, creating it")
        outf.mkdir()
    
    dt = datetime.datetime.utcnow()
    month = dt.month
    year = dt.year
    if not args.today:
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    preliminary = args.preliminary
    workers = create_reports(year, month, preliminary, outf)

    if preliminary:
        subject = f"Preliminary worktime report {month}-{year}. Please check it before the deadline."
    else:
        subject = f"Exported worktime report {month}-{year}."

    for w in workers:
        send_mail(w[0]._mail, subject, w[1], [w[2]])
        if not preliminary:
            w[0].mark_sheets_exported()