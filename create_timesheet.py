import datetime
import pytz
from pathlib import Path
from babel.dates import format_date
from openpyxl import load_workbook


def utc_unaware_to_tz(dt:datetime, tz) -> datetime:
    dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.timezone(tz))


def fill_hours_files(alias:str, sheets:list, outfolder:Path):
    fname = "Stundenzettel MM_JJ - Mitarbeiter_Lohn.xlsx"
    folder = Path(__file__).parent / "lohn"
    workbook = load_workbook(filename=str(folder / fname))
    wsheet = workbook.active

    wsheet["A11"] = alias
    wsheet["E11"] = format_date(sheets[0][-1], "MMMM", locale="de")
    wsheet["F11"] = sheets[0][-1].year
    wsheet["A14"] = str(sheets[0][-1].replace(day=1))

    for s in sheets:
        start = utc_unaware_to_tz(s[4], "Europe/Berlin")
        end = utc_unaware_to_tz(s[5], "Europe/Berlin")
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

    
    fname = fname.replace("MM_JJ", start.strftime("%m_%y")).replace("Mitarbeiter", alias.replace(" ", "_"))
    workbook.save(filename=str(outfolder / fname))