import logging
import sys

logger: logging.Logger = logging.getLogger('nextcord')


class LoggingFormatter(logging.Formatter):
    blue = "\x1b[38;5;39m"
    bold_red = "\x1b[31;1m"
    dark_gray = "\x1b[38;5;241m"
    gray = "\x1b[38;5;15m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    yellow = "\x1b[33;20m"
    
    def __init__(self, colors: bool = True):
        super().__init__()
        self.colors = colors

    def get_format(self, record: logging.LogRecord) -> str:
        if not self.colors:
            return "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        level = record.levelno

        color_primary = None
        color_secondary = self.gray
        color_less_important = self.dark_gray
        color_message = self.gray

        if level == logging.INFO:
            color_primary = self.blue
            if len(record.getMessage()) > 500:
                color_message = self.dark_gray
        elif level == logging.WARNING:
            color_primary = color_message = self.yellow
        elif level == logging.ERROR:
            color_primary = color_message = self.red
        elif level == logging.CRITICAL:
            color_primary = color_message = self.bold_red

        return f"{color_less_important}%(asctime)s{color_secondary} - " \
               f"{color_less_important}%(name)s{color_secondary} - " \
               f"{color_primary}%(levelname)s{color_secondary} - " \
               f"{color_message}%(message)s{self.reset}"

    def format(self, record: logging.LogRecord):
        log_fmt = self.get_format(record)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def load_logging_handlers() -> None:
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='a')
    handler.setFormatter(LoggingFormatter(colors=False))
    logger.addHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LoggingFormatter())
    logger.addHandler(handler)


def combine(message: str, args: [object]) -> str:
    if args and len(args) > 0:
        for arg in args:
            message += " " + str(arg)
    return message


def info(message: str, *args) -> None:
    logger.info(combine(message, args))


def warning(message: str, *args) -> None:
    logger.warning(combine(message, args))


def error(message: str, *args) -> None:
    logger.error(combine(message, args))


def critical(message: str, *args) -> None:
    logger.critical(combine(message, args))
