import colorama
import logging


class CustomFormatter(logging.Formatter):
    format = "%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: colorama.Fore.LIGHTWHITE_EX + format + colorama.Fore.RESET,
        logging.INFO: colorama.Fore.LIGHTWHITE_EX + format + colorama.Fore.RESET,
        logging.WARNING: colorama.Fore.YELLOW + format + colorama.Fore.RESET,
        logging.ERROR: colorama.Fore.RED + format + colorama.Fore.RESET,
        logging.CRITICAL: colorama.Fore.LIGHTRED_EX + format + colorama.Fore.RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def create_logger():
    colorama.init()

    logger = logging.getLogger("My_app")
    logger.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    return logger


logger = create_logger()
