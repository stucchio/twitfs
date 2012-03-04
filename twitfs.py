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
import twitter


if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

hello_path = '/hello'
hello_str = 'Hello World!\n'

class MyStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

TOKEN='514400263-FsbHAyi9A35MTswWWC0OWvdOu9MYG2wBaINU9xp4'
TOKEN_SECRET='NgA4ZI0U663pdPKWP9zAtEvVB0rQu89V0dCoCeG0cI'
CONSUMER='YKxpG65dN2rPIuqWxoQxTQ'
CONSUMER_SECRET='8KPpuMx2wvnBYAipG7ViaDTIaJBSQLx5pbXY463up4'
# Account: twitinpune/4g9fWC1

class TwitFS(Fuse):
    def __init__(self, *args, **kwargs):
        self.twitter = twitter.Twitter(auth=twitter.OAuth(TOKEN, TOKEN_SECRET, CONSUMER, CONSUMER_SECRET))
        self.__cached_tweets = {}
        Fuse.__init__(self, *args, **kwargs)

    def getattr(self, path):
        print "Getting attr for " + path
        st = MyStat()
        if path == '/':
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2
            return st
        try:
            data = self.__get_tweet(int(path[1:]))
            st.st_mode = stat.S_IFREG | 0444
            st.st_nlink = 1
            st.st_size = len(data['text'])
            return st
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT

    def readdir(self, path, offset):
        tweet_ids = [ str(t['id']) for t in self.twitter.statuses.home_timeline() ]
        for r in  ['.', '..'] +  tweet_ids:
            yield fuse.Direntry(r)

    def __get_tweet(self, id):
        if not self.__cached_tweets.has_key(id):
            self.__cached_tweets[id] = self.twitter.statuses.show(id=int(id))
        return self.__cached_tweets[id]

    def open(self, path, flags):
        try:
            data = self.__get_tweet(int(path[1:]))
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        return 0

    def __tweet_as_str(self, id):
        tweet = self.__get_tweet(id)
        result = str(tweet['user']['screen_name']) + "\n"
        result = result + str(tweet['text']) + "\n"
        return result

    def read(self, path, size, offset):
        try:
            result = self.__tweet_as_str(int(path[1:]))
            return str(result[offset:offset+size])
        except twitter.api.TwitterHTTPError:
            return -errno.ENOENT

def main():
    usage="""
    Userspace hello example

    """ + Fuse.fusage

    server = TwitFS(version="%prog " + fuse.__version__, usage=usage, dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()

if __name__ == '__main__':
    main()
