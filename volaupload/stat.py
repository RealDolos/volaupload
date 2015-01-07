""" RealDolos' funky volafile upload tool (Stats)"""

from datetime import datetime


FAC = 1024.0 * 1024.0


class Statistics:
    """Keep some statistics"""

    def __init__(self):
        self.start = datetime.now()
        self.lasts = [(self.start, 0)]

    def record(self, pos):
        """Record a position in time"""
        self.lasts += (datetime.now(), pos),
        if len(self.lasts) > 10:
            self.lasts.pop(0)

    @property
    def time(self):
        """Last time recorded"""
        return self.lasts[-1][0]

    @property
    def pos(self):
        """Last position recorded"""
        return self.lasts[-1][1]

    @property
    def runtime(self):
        """Total runtime so far"""
        return (self.time - self.start).total_seconds()

    @property
    def brate(self):
        """Total avg. byterate so far"""
        try:
            return self.pos / self.runtime
        except ZeroDivisionError:
            return 0

    @property
    def rate(self):
        """Total avg. megabyterate so far"""
        return self.brate / FAC

    def eta(self, total):
        """Estimated time of arrival"""
        try:
            return (total - self.pos) / self.brate
        except ZeroDivisionError:
            return 0.0

    @property
    def rate_last(self):
        """Avg. megabyterate over the last samples"""
        diff = (self.time - self.lasts[0][0]).total_seconds()
        try:
            return (self.pos - self.lasts[0][1]) / FAC / diff
        except ZeroDivisionError:
            return 0.0
