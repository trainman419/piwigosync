#!/usr/bin/env python3

import argparse
import sys

import osxphotos

def main():
    skip_folders = { "iPhoto Events" }
    photosdb = osxphotos.PhotosDB()

    print(photosdb.album_info[0])
    for album in photosdb.album_info:
        if len(album.folder_names) > 0 and album.folder_names[0] in skip_folders:
            continue
        path = list(album.folder_names)
        path.append(album.title)
        print('/'.join(path))
    return 0

if __name__ == '__main__':
    sys.exit(main())
