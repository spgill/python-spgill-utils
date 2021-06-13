# stdlib imports
import sys

# vendor imports
import colorama as color
import pyperclip

# local imports
from ..shorten import shortenURL


# If main, shorten whatever is passed in through args
# and copy to the clipboard
if __name__ == "__main__":
    short = shortenURL(" ".join(sys.argv[1:]))
    pyperclip.copy(short)

    color.init()
    print(f"{color.Fore.YELLOW}{short}{color.Fore.RESET} copied to clipboard")
