import sys

import googletrans


translator = googletrans.Translator()
origin = ' '.join(sys.argv[1:])

print(f'INPUT:   {origin}')

targets = [
   'de',
   'es',
   'fr',
   'it',
   'ja',
   'ko',
   'pt',
   'ru',
   'zh-cn',
   'zh-tw',
]

for target in targets:
    output = translator.translate(origin, dest=target)
    print(f'{target.upper():<9}{output.text}')
