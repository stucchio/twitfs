#!/usr/bin/env python

#    Copyright (C) 2006  Andrew Straw  <strawman@astraw.com>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#

import os, stat, errno
# pull in some spaghetti to make this stuff work without fuse-py being installed
try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse
from datetime import datetime
import time
import twitter


if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

class MyStat(fuse.Stat):
    def __init__(self, time=0, mode=0, ino = 0):
        self.st_mode = mode
        self.st_ino = ino
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.set_time(time)

    def set_time(self, time):
        self.st_atime = time
        self.st_mtime = time
        self.st_ctime = time

TOKEN='514400263-FsbHAyi9A35MTswWWC0OWvdOu9MYG2wBaINU9xp4'
TOKEN_SECRET='NgA4ZI0U663pdPKWP9zAtEvVB0rQu89V0dCoCeG0cI'
CONSUMER='YKxpG65dN2rPIuqWxoQxTQ'
CONSUMER_SECRET='8KPpuMx2wvnBYAipG7ViaDTIaJBSQLx5pbXY463up4'
# Account: twitinpune/4g9fWC1

class TwitFS(Fuse):
    def __init__(self, *args, **kwargs):
        self.twitter = twitter.Twitter(auth=twitter.OAuth(TOKEN, TOKEN_SECRET, CONSUMER, CONSUMER_SECRET))
        self.__is_new_status = False
        self.__cached_tweets = {}
        self.__new_status = ""
        Fuse.__init__(self, *args, **kwargs)

    def getattr(self, path):
        print "Getting attr for " + path
        st = MyStat()
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2
            return st
        if path == "/status":
            st.st_mode = stat.S_IFREG | 0666
            st.st_size = len(self.__get_status()['text'])
            return st
        try:
            tweet_id = int(path[1:])
            data = self.__tweet_as_str(tweet_id)
            st.st_mode = stat.S_IFREG | 0444
            st.st_nlink = 1
            st.st_size = len(data)
            st.set_time(self.__tweet_time(tweet_id))
            return st
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT
        except ValueError:
            return -errno.ENOENT

    def readdir(self, path, offset):
        tweet_ids = [ str(t['id']) for t in self.twitter.statuses.home_timeline() ]
        for r in  ['.', '..', 'status'] +  tweet_ids:
            yield fuse.Direntry(r)

    def open(self, path, flags):
        if path == "/status":
            return 0 #Always legal to open status
        try: #For tweets, check if the tweet exists
            data = self.__get_tweet(int(path[1:]))
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR #Must be read only for tweets
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        return 0

    def __tweet_time(self, id):
        tweet = self.__get_tweet(id)
        d = datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
        return time.mktime(d.timetuple())

    def __tweet_as_str(self, id):
        tweet = self.__get_tweet(id)
        result = str(tweet['user']['screen_name']) + "\n"
        result = result + str(tweet['text']) + "\n"
        return result

    def read(self, path, size, offset):
        if path == "/status":
            if self.__is_new_status:
                status = self.__new_status
            else:
                status = self.__get_status()['text']
            return str(status[offset:offset+size])
        try:
            result = self.__tweet_as_str(int(path[1:]))
            return str(result[offset:offset+size])
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT

    def write(self, path, buff, offset):
        self.__is_new_status=True
        if path != "/status":
            return -errno.EACCES
        if offset + len(buff) > 140:
            return -errno.ENOSPC
        if len(self.__new_status) < offset:
            self.__new_status = self.__new_status.ljust(offset) + buff
        else:
            self.__new_status = self.__new_status[0:offset] + buff + self.__new_status[offset+len(buff):]
        return len(buff)

    def release(self, path, flags):
        if self.__is_new_status:
            self.__set_status(self.__new_status)
        return 0

    def truncate(self, path, offset):
        if path != "/status":
            return -errno.EACCES
        self.__is_new_status=True
        self.__new_status = self.__new_status[0:offset]
        return 0

    def __set_status(self, status):
        self.__status_tweet = self.twitter.statuses.update(status=status)
        return self.__status_tweet

    def __get_status(self):
        if (not hasattr(self, "__status_tweet")):
            self.__status_tweet = self.twitter.statuses.user_timeline(count=1)[0]
        return self.__status_tweet

    def __get_tweet(self, id):
        if not self.__cached_tweets.has_key(id):
            self.__cached_tweets[id] = self.twitter.statuses.show(id=int(id))
        return self.__cached_tweets[id]


def main():
    server = TwitFS(version="%prog " + fuse.__version__, usage="twitfs", dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
    main()
