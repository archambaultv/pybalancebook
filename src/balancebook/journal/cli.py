import argparse
import colorlog
from balancebook.__about__ import __version__
from balancebook.errors import catch_and_log
from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal

parser = argparse.ArgumentParser(
          prog='balancebook', 
          description='Balance book, plain text budgeting')
parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
parser.add_argument('-c', '--config', metavar='CONFIG', type=str, dest='config_file',
                    help='Configuration file to use', default='journal/balancebook.yaml')
parser.add_argument('-v', '--verbose', action='store_true', dest='verbose')

subparsers = parser.add_subparsers(help='sub-command help', dest='command', title='subcommands')

verify_parser = subparsers.add_parser('verify', help='Verify the journal')

@catch_and_log
def main():
    setup_logger()
    args = parser.parse_args()

    if args.command == 'verify':
        journal = get_journal(args.config_file)
        journal.load()
        journal.verify_balances()
        if args.verbose:
            allgood()
    else:
        parser.print_help()
  
def get_journal(config_file):
    config = load_config(config_file)
    return Journal(config)

def setup_logger():
    handler = colorlog.StreamHandler()
    logger = colorlog.getLogger()
    logger.addHandler(handler)
    handler.setFormatter(colorlog.ColoredFormatter("%(log_color)s%(levelname)s:%(name)s:%(message)s"))

def allgood():
    ok_green = '\033[32m'
    end = '\033[0m'
    print(ok_green + "All good!" + end)