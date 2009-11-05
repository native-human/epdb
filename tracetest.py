

import sys
import linecache

def tracefunc(frame, event, arg):
    if event == 'line':
        print('Line: ' + str(frame.f_code.co_filename) + ':' + str(frame.f_lineno) + ':' + linecache.getline(frame.f_code.co_filename, frame.f_lineno))
        return tracefunc
    if event == 'call':
        print('Call: ' + str(frame.f_code.co_filename))
        return tracefunc
    if event == 'return':
        print('Return')
        return tracefunc
    if event == 'exception':
        print('Exception')
        return tracefunc
    if event == 'c_call':
        print('c_call')
        return tracefunc
    if event == 'c_exception':
        print('c_exception')
        return tracefunc
    if event == 'c_return':
        print('c_return')
        return tracefunc
    print('Unknown event')
    return tracefunc

def start_logging():
    frame = sys._getframe().f_back
    while frame:
        frame.f_trace = tracefunc
        frame = frame.f_back
    sys.settrace(tracefunc)

start_logging()

#def blah():
#    return 'blah'

#def yahoo(x):
#    blah()
#    x = 2 + 1
#    return 'x'
    
print('Hello World')

x = 3 + 4 +34 +54
#print(yahoo(3))
