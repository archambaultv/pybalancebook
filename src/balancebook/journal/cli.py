import argparse
import logging
import os
import datetime
from balancebook.__about__ import __version__
from balancebook.errors import BBookException
from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
          prog='balancebook', 
          description='Balance book, plain text accouting')
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

dry_run = argparse.ArgumentParser(add_help=False)
dry_run.add_argument('-d', '--dry-run', action='store_true', dest='dry_run')

ouput_dir = argparse.ArgumentParser(add_help=False)
ouput_dir.add_argument('-o', '--output-dir', metavar='OUTPUT_DIR', type=str, dest='output_dir',
                    help='Output directory to use. If unspecified, the journal directory will be used and files will be overwritten.')

today = argparse.ArgumentParser(add_help=False)
today.add_argument('--today', 
                           metavar='TODAY', 
                           type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d').date(), 
                           dest='today',
                           help='Today\'s date (YYYY-MM-DD) to use for the relative date computation')

verify_parser = subparsers.add_parser('verify', help='Verify the journal', 
                                      parents=[parent_parser])
export_parser = subparsers.add_parser('export', help='Export the journal', 
                                      parents=[parent_parser, ouput_dir, today])
reformat_parser = subparsers.add_parser('reformat', help='Reformat the journal', 
                                        parents=[parent_parser, ouput_dir])
import_parser = subparsers.add_parser('import', help='Import transactions', 
                                      parents=[parent_parser])
autobalance_parser = subparsers.add_parser('autobalance', 
                                           help='Auto balance the transactions to match the balance assertions', 
                                           parents=[parent_parser, dry_run, ouput_dir])
autostatement_parser = subparsers.add_parser('autostatement',
                                                help='Modify the statement dates to match the balance assertions',
                                                parents=[parent_parser, dry_run, ouput_dir])

def catch_and_log(func):
    """Decorator to catch and log exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BBookException as e:
            logger.fatal(e)
            logger.debug("Exception info", exc_info=True)
            return 3
        except Exception as e:
            logger.fatal(e)
            logger.debug("Exception info", exc_info=True)
            return 1
    
    return wrapper

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
        journal.export(today = args.today, output_dir = args.output_dir)
        if args.verbose:
            allgood()
    elif args.command == 'reformat':
        journal = load_and_verify_journal(args.config_file)
        journal.write(sort=True, output_dir=args.output_dir)
        if args.verbose:
            allgood()
    elif args.command == 'import':
        journal = load_and_verify_journal(args.config_file)
        journal.auto_import()
        if args.verbose:
            allgood()
    elif args.command == 'autobalance':
        journal = load_journal(args.config_file)
        txns = journal.auto_balance()
        if args.dry_run:
            print("Dry run, no changes made")
            for t in txns:
                print(t)
        else:
            journal.verify_balances()
            journal.write(sort=True, what=['transactions'], output_dir=args.output_dir)
        if args.verbose:
            allgood()
    elif args.command == 'autostatement':
        journal = load_journal(args.config_file)
        ps = journal.auto_statement_date()
        if args.dry_run:
            print("Dry run, no changes made")
            for p in ps:
                print(p)
        else:
            journal.verify_balances()
            journal.write(sort=True, what=['transactions'], output_dir=args.output_dir)
        if args.verbose:
            allgood()
    else:
        parser.print_help()
  
def get_journal(config_file):
    config = load_config(config_file)
    return Journal(config)

def load_journal(config_file):
    journal = get_journal(config_file)
    journal.load()
    return journal

def load_and_verify_journal(config_file: str) -> Journal:
    journal = get_journal(config_file)
    journal.load()
    journal.verify_balances()
    return journal

def setup_logger(log_level: str = 'WARNING'):
    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())

    logger = logging.getLogger()
    logger.setLevel(logging._nameToLevel[log_level])
    logger.addHandler(handler)

def allgood():
    ok_green = '\033[32m'
    end = '\033[0m'
    print(ok_green + "All good!" + end)


# https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(levelname)s - %(message)s "

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)