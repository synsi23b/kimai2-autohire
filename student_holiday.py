import argparse
from datetime import datetime
from kimai_util import get_gen_projects
from pathlib import Path
import logging

THIS_LOCATION = Path(__file__).parent.resolve()


def main():
    projects = get_gen_projects()
    workers = []
    for pr in projects:
        workers += pr.get_workers()
    for wr in workers:
        print(wr._alias, wr.get_holiday_eligibility())
    return 0


if __name__ == "__main__":
    thisfile = Path(__file__).resolve()
    logging.basicConfig(filename=str(thisfile.parent.parent / f"kimai2_autohire_{thisfile.stem}.log"), 
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    try:
        #parser = argparse.ArgumentParser(description="create available holidays report for working students or set holidays taken")
        #parser.add_argument("--all", action="store_true", help="run the calculation for all students and send them emails about it")
        #parser.add_argument("name", action="store", help="the name of the student to run the function for")
        ret = main()
    except Exception as e:
        logging.exception(f"Uncaught exception in from main! {e}")
        ret = -1
    exit(ret)