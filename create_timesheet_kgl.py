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


THIS_LOCATION = Path(__file__).parent.resolve()


def utc_unaware_to_tz(dt:datetime, tz) -> datetime:
    dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.timezone(tz))


def fill_hours_files(alias:str, sheets:list, outfolder:Path, fileprefix:str = ""):
    company_data = {}
    #print(THIS_LOCATION.parent)
    with open(str(THIS_LOCATION.parent / "kgl_info.yaml")) as inf:
        company_data = yaml.load(inf, yaml.Loader)
    fname = "Stundenzettel MM_JJ - Mitarbeiter_Lohn.xlsx"
    folder = THIS_LOCATION / "files"
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
    maxday = calendar.monthrange(sheets[0][-1].year, sheets[0][-1].month)[1]
    for d in range(1, maxday+1):
        wsheet[f"A{13+d}"] = str(sheets[0][-1].replace(day=d))

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
        duration = datetime.timedelta(seconds=sum([s[6] for s in sl]))
        end = start + duration
        # create description for all entries
        work_contents = [s[7] for s in sl if s[7] != None]
        if work_contents == []:
            work_contents = "Arbeit"
        else:
            work_contents = "; ".join(work_contents)

        if start.date() == end.date():
            row = 13 + start.day
            if wsheet[f"C{row}"] == "start gestern; ":
                # cells already written by 24h roll over -> adjust start and end time for today
                start = datetime.datetime.strptime(wsheet[f"E{row}"], "%H:%M:%S")
                end = start + duration
                wsheet[f"C{row}"] = "start gestern; " + work_contents
            else:
                wsheet[f"C{row}"] = work_contents
            wsheet[f"D{row}"] = start.strftime("%H:%M:00")
            wsheet[f"E{row}"] = end.strftime("%H:%M:00")
        else:
            # midnight roll over
            row = 13 + start.day
            wsheet[f"C{row}"] = work_contents
            wsheet[f"D{row}"] = start.strftime("%H:%M:00")
            wsheet[f"E{row}"] = "24:00:00"
            row += 1
            wsheet[f"C{row}"] = "start gestern; "
            wsheet[f"D{row}"] = "00:00:00"
            wsheet[f"E{row}"] = end.strftime("%H:%M:00")

    fname = fileprefix + fname.replace("MM_JJ", start.strftime("%m_%y")).replace("Mitarbeiter", alias.replace(" ", "_"))
    outf = outfolder / fname
    workbook.save(filename=str(outf))
    if fileprefix == "":
        # libreoffice --headless --convert-to pdf reports_kgl/mycoolfile.xlsx
        logging.info(f"Converting to pdf {outf}")
        result = convertapi.convert('pdf', { 'File': str(outf) })
        outf = outf.with_suffix(".pdf")
        result.file.save(str(outf))
        user_info = convertapi.user()
        logging.info(f"Convertapi conversion done. Cost: {result.conversion_cost} Seconds left: {user_info['SecondsLeft']}")
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

The final report will be generated on the 7th of the following month.
"""
    else:
        bmsg += """
This report was exported and can't be changed anymore. It will be used to calculate your salary.
"""

    if preliminary:
        prefix = "Preliminary-"
        subject = f"Preliminary worktime report {month}-{year}. Please check it before 7th."
    else:
        prefix = ""
        subject = f"Exported worktime report {month}-{year}."

    projects = get_gen_projects()
    owrk = []
    missing = []
    timenow = datetime.datetime.utcnow()
    for proj in projects:
        logging.info(f"Working on project {proj._name}")
        workers = proj.get_workers(year, month)
        missing += get_workers_missing_timesheet(year, month, proj._id, workers)
        for wrk in workers:
            open_sheets_warn = 0
            open_sheets = wrk.get_open_sheets(year, month)
            if open_sheets:
                osheet_msg = ""
                for tid, st, tz in open_sheets:
                    if (timenow - st) > datetime.timedelta(hours=12) and db_util.open_warning_older_than_hours(tid, 13):
                        subject = f"Warning: running timesheets for {month}-{year} detect. Please check it before 7th."
                        open_sheets_warn = tid
                        osheet_msg += utc_unaware_to_tz(st, tz).strftime('\n%Y %B %d\n')
                if open_sheets_warn != 0:
                    bmsg = f"{bmsg}\n\nYou got running timesheets started at:\n\n{osheet_msg}\n\nTimesheets need to be stopped to be included in the salary calculation.\n\n\n"
            if not wrk.was_changed_since_last_gen() and preliminary and open_sheets_warn == 0:
#                logging.info(f"Skipping generation for {wrk._alias}: not changed")
                continue
            if not wrk.last_change_older_than_minutes(15) and open_sheets_warn == 0:
                logging.info(f"Skipping generation for {wrk._alias}: last changed recently")
                continue
            logging.info(f"Generating worker {wrk._alias} open_sheet: {open_sheets_warn}")
            month_ok, month_msg = proj.is_worker_month_ok(wrk)
            weeks_ok, weeks = proj.is_worker_weeks_ok(wrk)
            days_ok, days_msg = proj.is_days_ok(wrk)
            msg = bmsg + month_msg
            if not weeks_ok:
                msg += "\n\n!! You worked to many hours in one of the weeks !!\n"
            for week in weeks:
                msg += f"\n{week[1]}\n"
            if not days_ok:
                msg += days_msg
            repofile = fill_hours_files(wrk._alias, wrk._sheets, reportfolder, prefix)
            owrk.append((wrk, subject, msg, repofile, open_sheets_warn))
    return owrk, missing


def get_workers_missing_timesheet(year:int, month:int, proj_id:int, workers:list):
    all_wrk = db_util.get_team_worker_by_project(proj_id)
    sheet_workers = [wrk._id for wrk in workers]
    no_sheet = [w for w in all_wrk if w[0] not in sheet_workers]
    owrk = []
    for wrk in no_sheet:
        gen = db_util.get_generation_cycle_id_dt(wrk[0])
        if (gen[1].year, gen[1].month) != (year, month):
            owrk.append(wrk)
    return owrk


def send_missing_sheets_msg(year, month, worker):
    msg=f"""
Dear {worker[2]},

When generating preliminary reports for the upcoming salary calculation, we noticed you have not submitted any worktimes, yet.

If you have not worked at all this month, you can ignore this message.

If you have worked, you need to submit your timesheets at https://worktime.leap-in-time.de in order to get paid for this month.

Thank you!
"""
    logging.info(f"Sending missing timesheet warning to {worker[1]}")
    send_mail(worker[1], f"{month}-{year} No timesheet found!", msg)
    db_util.set_missing_sheet_reminder_send(worker[0], year, month)


def main(kgl_cred):
    convertapi.api_secret = kgl_cred["convertapi"]
    parser = argparse.ArgumentParser(description="export timesheets for users of projects with *generate_sheets* in project description")
    #parser.add_argument("--today", action="store_true", help="use today as a time base to generate monthly report rather than last month")
    #parser.add_argument("--lastmonth", action="store_true", help="whether or not this generation is preliminary, e.g. not a real export")
    parser.add_argument("--preliminary", action="store_true", help="whether or not this generation is preliminary, e.g. not a real export")

    args = parser.parse_args()

    outf = thisfile.parent.parent / "reports_kgl"
    if not outf.is_dir():
        logging.info("report folder not found, creating it")
        outf.mkdir()
    
    dt = datetime.datetime.utcnow()
    day = dt.day
    month = dt.month
    year = dt.year
    if day < 15:
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    preliminary = args.preliminary
    workers, missing = create_reports(year, month, preliminary, outf)

    report_to_kgl = []
    for w in workers:
        # address, subject, txt-msg, attachments
        send_mail(w[0]._mail, w[1], w[2], [w[3]])
        # check for warning based on open sheets
        if w[4] != 0:
            db_util.set_open_timesheet_warning_send(w[4])
        else:
            w[0].set_last_generation_sheet()
        if not preliminary:
            w[0].mark_sheets_exported()
            report_to_kgl.append(str(w[3]))
    for m in missing:
        send_missing_sheets_msg(year, month, m)
    if report_to_kgl:
        # open kgl webprotal and send message with attachments
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