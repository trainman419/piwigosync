#!/usr/bin/env python3

import argparse
import sys

import osxphotos
import piwigo

def main():
    print("Connecting to Piwigo server")
    piwigo_url = "http://arg:8000"

    piwigo_site = piwigo.Piwigo(piwigo_url)
    print("Piwigo server version: {}".format(piwigo_site.pwg.getVersion()))

    print("Loading iPhoto library")
    skip_folders = { "iPhoto Events" }
    photosdb = osxphotos.PhotosDB()

    print("Checking albums")
    for album in photosdb.album_info:
        if len(album.folder_names) > 0 and album.folder_names[0] in skip_folders:
            continue
        path = list(album.folder_names)
        path.append(album.title)
        print('/'.join(path))
    return 0

if __name__ == '__main__':
    sys.exit(main())
