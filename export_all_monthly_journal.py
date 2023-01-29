from db_util import get_user_by_role
import logging
from pathlib import Path
from datetime import date, timedelta
from kimai_util import get_kimai_datafolder
from shutil import copy
from kimai_util import Angestellter


THIS_LOCATION = Path(__file__).parent.resolve()


def main():
    outfolder = Path(get_kimai_datafolder()) / "export"
    gen_start = date(2022, 12, 19)
    #gen_end =  date.today() - timedelta(days=1)
    gen_end =  date(2023, 1, 22)
    empl = Angestellter.get_all_active("ANGESTELLTER")
    stud = Angestellter.get_all_active("WERKSTUDENT")
    schueler = Angestellter.get_all_active("SCHUELERAUSHILFE")
    for ma in empl + stud + schueler:
        for invoice in ma.export_monthly_journal(gen_start, gen_end, outfolder):
            dst = THIS_LOCATION / f"export/journal_{gen_start}_{gen_end}_{ma._alias}.pdf".replace(" ", "_")
            dst = str(dst)
            print(f"copy from {invoice} to {dst}")
            logging.info(f"copy from {invoice} to {dst}")
            copy(invoice, dst)


if __name__ == "__main__":
    thisfile = Path(__file__).resolve()
    logging.basicConfig(filename=str(thisfile.parent.parent / f"kimai2_autohire_{thisfile.stem}.log"), 
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    main()