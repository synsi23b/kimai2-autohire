from db_util import get_user_by_role
import logging
from pathlib import Path
from datetime import date
from kimai_util import export_monthly_journal_student, get_kimai_datafolder
from shutil import copy


THIS_LOCATION = Path(__file__).parent.resolve()


def main():
    outfolder = Path(get_kimai_datafolder()) / "export"
    gen_start = date(2022, 10, 25)
    gen_end =  date.today()
    for st in get_user_by_role("WERKSTUDENT"):
        user = st[1]
        #opath = outfolder / f"journal_{gen_start}_{gen_end}_{st[4]}.pdf".replace(" ", "_")
        export_monthly_journal_student(user, gen_start, gen_end, outfolder)
        outfile = THIS_LOCATION.parent / f"export/journal_{gen_start}_{gen_end}_{st[4]}.pdf".replace(" ", "_") 
        copy("/var/www/kimai2/var/data/export/221122-Leap_in_Time.pdf", str(outfile) )


if __name__ == "__main__":
    thisfile = Path(__file__).resolve()
    logging.basicConfig(filename=str(thisfile.parent.parent / f"kimai2_autohire_{thisfile.stem}.log"), 
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    main()