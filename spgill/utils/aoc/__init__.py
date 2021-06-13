"""
This module provides helper functions for my Advent of Code solutions.
"""

# Stdlib imports
import functools
import pathlib

# vendor imports
import click
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init()


def solution(func):
    """
    Wrapper func making a solution function have a fully-featured CLI, with
    a pre-configured puzzle input file argument.
    """

    @click.command()
    @click.argument("path", type=str)
    @functools.wraps(func)
    def withClick(*args, **kwargs):

        # Process the puzzle input arg and convert it to a path object
        inputPath = pathlib.Path(kwargs["path"])
        if not inputPath.exists():
            printError("Input file does not exist")
            exit()
        kwargs["path"] = inputPath.resolve()

        return func(*args, **kwargs)

    return withClick


def printAnswer(part: int, value: any) -> None:
    """ Print the solution to Part `part` of the puzzle """
    print(f"{Fore.GREEN}Answer (Part {part}):{Style.RESET_ALL} {value}")


def printComputationWarning() -> None:
    """ Print a warning about computation time. """
    print(
        f"{Fore.YELLOW}Warning:{Style.RESET_ALL} "
        "It may take awhile to compute answers..."
    )


def printComputationWarningWithPrompt() -> None:
    """
    Print a warning about computation time,
    prompting the user to continue.
    """
    click.confirm(
        f"{Fore.YELLOW}Warning:{Style.RESET_ALL} "
        "It may take a very long while to compute answers. Continue?",
        default=True,
        abort=True,
    )


def printError(message: str) -> None:
    """ Print an error in red and abort execution """
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")
    exit(1)
