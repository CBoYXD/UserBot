def get_lang_by_file_ext(file_ext: str) -> str:
    lang_extensions = {
        'python': 'py',
        'java': 'java',
        'cpp': 'cpp',
        'c++': 'cpp',
        'c': 'c',
        'csharp': 'cs',
        'c#': 'cs',
        'awk': 'awk',
        'bash': 'sh',
        'befunge93': ['be', 'bf', 'b93', 'b98', 'befunge'],
        'brainfuck': ['b', 'bf'],
        'clojure': [
            'clj',
            'boot',
            'cl2',
            'cljc',
            'cljs',
            'cljs.hl',
            'cljscm',
            'cljx',
            'hic',
        ],
        'cobol': ['cob', 'cbl', 'ccp', 'cobol', 'cpy'],
        'coffeescript': [
            '.coffee',
            '_coffee',
            'cake',
            'cjsx',
            'cson',
            'iced',
        ],
        'cow': 'cow',
        'crystal': 'cr',
        'csharp.net': 'cs',
        'd': ['d', 'di'],
        'dart': 'dart',
        'dash': 'dash',
        'dragon': 'dra',
        'elixir': ['ex', 'exs'],
        'emacs': ['el', 'emacs', 'emacs.desktop'],
        'erlang': ['erl', 'es', 'escript', 'hrl', 'xrl', 'yrl'],
        'file': [
            'exe',
            'bin',
            'axf',
            'elf',
            'o',
            'out',
            'prx',
            'puff',
            'ko',
            'mod',
            'so',
        ],
        'forte': ['forter', 'forte'],
        'fortran': [
            'f90',
            'f',
            'f03',
            'f08',
            'f77',
            'f95',
            'for',
            'fpp',
        ],
        'freebasic': ['bas', 'fbc', 'basic', 'qbasic', 'quickbasic'],
        'fsharp.net': ['fsharp', 'fs', 'f#', 'fs.net', 'f#.net'],
        'fsi': ['fsi', 'fsx'],
        'go': 'go',
        'golfscript': 'golfscript',
        'groovy': ['groovy', 'grt', 'gtpl', 'gvy'],
        'haskell': ['haskell', 'hs'],
        'husk': 'husk',
        'iverilog': ['verilog', 'vvp'],
        'japt': 'japt',
        'javascript': 'js',
        'jelly': 'jelly',
        'julia': 'jl',
        'kotlin': ['kt', 'ktm', 'kts'],
        'lisp': ['nl', 'lisp', 'lsp'],
        'llvm_ir': ['llvm', 'll'],
        'lolcode': 'lol',
        'lua': 'lua',
        'nasm': ['asm', 'nasm32'],
        'nasm64': 'asm64',
        'nim': 'nim',
        'ocaml': ['ocaml', 'ml'],
        'octave': ['matlab', 'm'],
        'osabie': ['osabie', 'usable'],
        'paradoc': 'paradoc',
        'pascal': ['pp', 'pas', 'inc'],
        'perl': ['pl', 'al', 'cgi', 'fcgi', 'perl'],
        'php': [
            'php',
            'aw',
            'ctp',
            'php3',
            'php4',
            'php5',
            'phps',
            'phpt',
        ],
        'ponylang': ['pony', 'ponyc'],
        'powershell': ['ps1', 'psd1', 'psm1'],
        'prolog': ['pl', 'pro', 'prolog', 'yap'],
        'pure': 'pure',
        'pyth': 'pyth',
        'racket': ['rkt', 'rktd', 'rktl', 'scrbl'],
        'raku': ['raku', 'rakudo', 'perl6', 'p6', 'pl6'],
        'rockstar': ['rock', 'rocky'],
        'rscript': 'r',
        'ruby': [
            'rb',
            'builder',
            'gemspec',
            'god',
            'irbrc',
            'jbuilder',
            'pluginspec',
            'podspec',
            'rabl',
            'rake',
            'ru',
            'ruby',
        ],
        'rust': ['rs', 'rs.in'],
        'scala': ['scala', 'sbt', 'sc'],
        'sqlite3': ['sqlite', 'sql'],
        'swift': 'swift',
        'typescript': ['ts', 'tsx'],
        'basic': [
            'vb',
            'bas',
            'cls',
            'frm',
            'frx',
            'vba',
            'vbhtml',
            'vbs',
        ],
        'vlang': 'v',
        'vyxal': 'vyxal',
        'yeethon': ['yeethon', 'yeethon3'],
        'zig': 'zig',
    }

    for lang, ext in lang_extensions.items():
        if file_ext == ext or file_ext in ext:
            return lang
