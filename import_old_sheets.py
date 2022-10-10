import PyPDF2
from pathlib import Path
from datetime import datetime
import pytz
import re
from db_util import get_user_id, get_private_project_activity_for_user, get_project_rate, insert_timesheet

NAME_STRINGS = [
    "Adriana Postaru",
    "Adrian Bohnstedt",
    "Aaron Wickert",
    "Christian Eyring",
    "Daniel Homburg",
    "Kaj Schmidt",
    "Nagehan Durmuskaya",
    "Ozan Özgün",
]


def get_lines_file(path:Path):
    lines = None
    print(f"Running file: {path}")
    with open(str(path), "rb") as inf:
        pdf = PyPDF2.PdfFileReader(inf)
        text = ""
        for p in pdf.pages:
            text += f"{p.extract_text()}\n"
        lines = text.split("\n")
    return lines



NAME_PAT = [ re.compile(f".+({s}).*") for s in NAME_STRINGS ]

TASK_EMPTY = re.compile("(\d{2}\.\d{2}\.\d{2,4}\s?\w{2}\s?0,00)")

TASK_PAT = re.compile("(\d{2}\.\d{2}\.\d{2,4})\s?\w{2}\s?(.+?)(\d{2}:\d{2}:\d{2})\s?(\d{2}:\d{2}:\d{2})")

TZ = pytz.timezone("Europe/Berlin")

def extract_name_times(filename, lines):
    oneline = "".join(lines)
    name = None
    for p in NAME_PAT:
        mc = p.search(oneline)
        if mc:
            name = mc.group(1)
            break
    if name is None:
        names = "\n".join([f"{i} - {n}" for i,n in enumerate(NAME_STRINGS)])
        inp = input(f"No name found in file {filename}. Manually enter or abort? Enter 'x' to abort or a number to pick a name:\n{names}")
        if inp == "x":
            raise ValueError("Name not found")
        name = NAME_STRINGS[int(inp)]
    # delete empty dates
    for empty in TASK_EMPTY.findall(oneline):
        oneline = oneline.replace(empty, "")
    times = []
    for m in TASK_PAT.findall(oneline):
        date, topic, start, end = m
        try:
            start = datetime.strptime(f"{date} {start}", "%d.%m.%Y %H:%M:%S")
            end = datetime.strptime(f"{date} {end}", "%d.%m.%Y %H:%M:%S")
        except ValueError:
            start = datetime.strptime(f"{date} {start}", "%d.%m.%y %H:%M:%S")
            end = datetime.strptime(f"{date} {end}", "%d.%m.%y %H:%M:%S")
        times.append((start.replace(tzinfo=TZ), end.replace(tzinfo=TZ), filename, topic))
    if not times:
        raise ValueError("No times found in file")
    return (name, times)


def group_users(entries):
    users = {}
    for e in entries:
        if e[0] in users:
            users[e[0]] += e[1]
        else:
            users[e[0]] = e[1]
    return users


def get_files():
    pa = Path(__file__).resolve().parent / "oldtimesheets"
    return pa.glob("**/*.pdf")


def create_sheets(user:str, sheets:list):
    user_id = get_user_id(user, True)
    proj, acti = get_private_project_activity_for_user(user_id)
    rate = get_project_rate(proj)
    exported = True
    for start, end, filename, description in sheets:
        insert_timesheet(user_id, acti, proj, start, end, description, exported, rate)


if __name__ == "__main__":
    entries = []
    for f in get_files():
        lines = get_lines_file(f)
        entries.append(extract_name_times(f.name, lines))
    users = group_users(entries)
    approved = {}
    for k, v in users.items():
        print(f"{k} -> {len(v)}")
        v.sort()
        for line in v:
            print(line)
        apr = input("Approve? [y] to commit")
        if apr == "y":
            create_sheets(k, v)
            print("*commit finished*")
        else:
            print("ignored")
        print("#"*20)

    #print(users)
        