import argparse
import colorlog
import logging
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
parent_parser.add_argument( '--loglevel',
                            dest='log_level',
                            default='WARNING',
                            choices=logging._nameToLevel.keys(),
                            help='Set the logging level.')

verify_parser = subparsers.add_parser('verify', help='Verify the journal', parents=[parent_parser])
export_parser = subparsers.add_parser('export', help='Export the journal', parents=[parent_parser])
reformat_parser = subparsers.add_parser('reformat', help='Reformat the journal', parents=[parent_parser])
import_parser = subparsers.add_parser('import', help='Import transactions', parents=[parent_parser])

@catch_and_log
def main():
    args = parser.parse_args()
    setup_logger(args.log_level)
    if args.config_file is None:
        # Get the pwd
        pwd = os.getcwd()
        args.config_file = os.path.join(pwd, 'journal/balancebook.yaml')

    if args.command == 'verify':
        load_and_verify_journal(args.config_file)
        if args.verbose:
            allgood()
    elif args.command == 'export':
        journal = load_and_verify_journal(args.config_file)
        journal.export()
        if args.verbose:
            allgood()
    elif args.command == 'reformat':
        journal = load_and_verify_journal(args.config_file)
        journal.write(sort=True)
        if args.verbose:
            allgood()
    elif args.command == 'import':
        journal = load_and_verify_journal(args.config_file)
        journal.auto_import()
        if args.verbose:
            allgood()
    else:
        parser.print_help()
  
def get_journal(config_file):
    config = load_config(config_file)
    return Journal(config)

def load_and_verify_journal(config_file: str) -> Journal:
    journal = get_journal(config_file)
    journal.load()
    journal.verify_balances()
    return journal

def setup_logger(log_level: str = 'WARNING'):
    handler = colorlog.StreamHandler()
    logger = colorlog.getLogger()
    logger.setLevel(logging._nameToLevel[log_level])
    logger.addHandler(handler)
    handler.setFormatter(colorlog.ColoredFormatter("%(log_color)s%(levelname)s:%(name)s:%(message)s"))

def allgood():
    ok_green = '\033[32m'
    end = '\033[0m'
    print(ok_green + "All good!" + end)