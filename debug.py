#!/usr/bin/env python

import io

def debug(value, *args, sep=' ', end='\n'):
    output = io.StringIO()
    print(value, *args, sep=sep, end=end, file=output)
    for line in output.getvalue().splitlines():
        print('#' + line)