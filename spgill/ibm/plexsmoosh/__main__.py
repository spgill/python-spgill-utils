"""
Tool to process @ibm/plex module fonts into inline stylesheet data uri's.

First argument should be the directory of the @ibm/plex node module, and you
pipe the output to a file or whatever else. Output is compatible with Sass and
vanilla CSS.

Include flags `--mono`, `--sans`, `--condensed`, or `--serif` to select which
font families to include in the output.

Invoke with `--help` for syntax information.



Requires Python runtime 3.6 or greater, and third party module `click`.
"""

# stdlib imports
import base64
import pathlib
import re
import sys

# vendor imports
import click

# local imports


@click.command()
@click.argument('module')
@click.option('--mono', is_flag=True)
@click.option('--sans', is_flag=True)
@click.option('--condensed', is_flag=True)
@click.option('--serif', is_flag=True)
def main(**kwargs):
    # Throw an error if stdout is a terminal
    if sys.stdout.isatty():
        raise RuntimeError('Stdout should be a pipe!')

    # MODULE argument should be the path to the "@ibm/plex" node module folder
    modulePath = pathlib.Path(kwargs['module'])
    fontFaces = [
        'IBM-Plex-Mono' if kwargs['mono'] else '',
        'IBM-Plex-Sans' if kwargs['sans'] else '',
        'IBM-Plex-Sans-Condensed' if kwargs['condensed'] else '',
        'IBM-Plex-Serif' if kwargs['serif'] else '',
    ]

    # Open the master css template
    with (modulePath / 'css' / 'ibm-plex.css').open('r') as masterFile:
        master = masterFile.read()

    # Iterate through matched @font-face blocks in master
    for match in re.finditer(
        r'@font-face {.*?src:.*?url\(\"(\.\./([\w-]*?)/.*?)\"\).*?}',
        master, re.S
    ):
        # Ignore the woff2 fonts
        if 'woff2' in match.group(0):
            continue

        # Skip font families that aren't desired
        if match.group(2) not in fontFaces:
            continue

        # Report the matched font file
        sys.stderr.write(match.group(1) + '\n')

        # Locate, open, and read the font file
        fontPath = modulePath / 'css' / match.group(1)
        with fontPath.open('rb') as fontFile:
            fontData = fontFile.read()

        # Encode the data to base64
        enc = base64.b64encode(fontData).decode()

        # Construct the data uri replacement
        url = f'data:application/font-woff;base64,{enc}'

        # Replace the url with the base64 data uri
        sys.stdout.write(
            match.group(0).replace(match.group(1), url) + '\n\n'
        )


if __name__ == '__main__':
    main()
