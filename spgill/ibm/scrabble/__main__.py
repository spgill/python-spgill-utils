# stdlib imports
import re
import sys

# vendor imports
import pyperclip

# local imports

text = sys.argv[1].lower()
out = re.sub(r'([a-z])', r':letter-\1:', text).replace(' ', '   ')

print('Copying to clipboard;')
print(out)

pyperclip.copy(out)
