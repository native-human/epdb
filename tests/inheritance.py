#!/usr/bin/env python

class A:
    def get(self):
        return 'A'
    def show(self):
        print(self.get())


class B(A):
    def get(self):
        return 'B'

b = B()
b.show()
