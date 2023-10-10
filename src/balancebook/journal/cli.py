import argparse
import colorlog
import os
from balancebook.__about__ import __version__
from balancebook.errors import catch_and_log
from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal

parser = argparse.ArgumentParser(
          prog='balancebook', 
          description='Balance book, plain text budgeting')
parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

subparsers = parser.add_subparsers(help='sub-command help', dest='command', title='subcommands')

parent_parser = argparse.ArgumentParser(add_help=False)
parent_parser.add_argument('-c', '--config', metavar='CONFIG', type=str, dest='config_file',
                    help='Configuration file to use')
parent_parser.add_argument('-v', '--verbose', action='store_true', dest='verbose')

verify_parser = subparsers.add_parser('verify', help='Verify the journal', parents=[parent_parser])
export_parser = subparsers.add_parser('export', help='Export the journal', parents=[parent_parser])

@catch_and_log
def main():
    setup_logger()
    args = parser.parse_args()
    if args.config_file is None:
        # Get the pwd
        pwd = os.getcwd()
        args.config_file = os.path.join(pwd, 'journal/balancebook.yaml')

    if args.command == 'verify':
        get_and_verify_journal(args.config_file)
        if args.verbose:
            allgood()
    elif args.command == 'export':
        journal = get_and_verify_journal(args.config_file)
        journal.export()
        if args.verbose:
            allgood()
    else:
        parser.print_help()
  
def get_journal(config_file):
    config = load_config(config_file)
    return Journal(config)

def get_and_verify_journal(config_file: str) -> Journal:
    config = load_config(config_file)
    journal = Journal(config)
    journal.load()
    journal.verify_balances()
    return journal

def setup_logger():
    handler = colorlog.StreamHandler()
    logger = colorlog.getLogger()
    logger.addHandler(handler)
    handler.setFormatter(colorlog.ColoredFormatter("%(log_color)s%(levelname)s:%(name)s:%(message)s"))

def allgood():
    ok_green = '\033[32m'
    end = '\033[0m'
    print(ok_green + "All good!" + end)