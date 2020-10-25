#!/usr/bin/env python3

import argparse
import hashlib
import queue
import sys
import threading

import osxphotos
import piwigo

def upload_thread():
    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--piwigo", default="http://arg:8000")
    parser.add_argument("--piwigo-user", default="austin")
    parser.add_argument("--piwigo-password")

    args = parser.parse_args()
    print("Connecting to Piwigo server")

    piwigo_site = piwigo.Piwigo(args.piwigo)
    print("Piwigo server version: {}".format(piwigo_site.pwg.getVersion()))
    piwigo_site.pwg.session.login(username=args.piwigo_user,
            password=args.piwigo_password)

    print("Loading iPhoto library")
    skip_folders = { "iPhoto Events" }
    photosdb = osxphotos.PhotosDB()

    hash_queue = queue.Queue()
    check_queue = queue.Queue()
    upload_queue = queue.Queue()

    def hash_photo():
        while True:
            photo, path = hash_queue.get()
            #print("Hash: {}".format(path))
            try:
                md5 = hashlib.md5(open(path, "rb").read()).hexdigest()
                check_queue.put((photo, path, md5))
            except FileNotFoundError:
                pass
            hash_queue.task_done()

    def check_photo():
        while True:
            items = [check_queue.get()]
            while True:
                try:
                    i = check_queue.get_nowait()
                    items.append(i)
                except queue.Empty:
                    break
            md5sum_list = [i[2] for i in items]
            print("Checking", md5sum_list)
            result = piwigo_site.pwg.images.exist(md5sum_list=",".join(md5sum_list))
            for item in items:
                if result[item[2]] is None:
                    print("Need to upload: {}".format(item[0].original_filename))
                    upload_queue.put(item)
                else:
                    print("Already uploaded: {}".format(item[0].original_filename))
                check_queue.task_done()

    def upload_photo():
        while True:
            photo, path, md5 = upload_queue.get()
            filename = photo.original_filename
            if filename is None:
                filename = photo.filename
            name = photo.title
            if name is None:
                pass
            print("Upload {} as {}".format(path, filename))
            try:
                data = open(path, "rb").read()
                chunks = []
                chunk_size = 500000
                while len(data) > 0:
                    chunks.append(data[:chunk_size])
                    data = data[chunk_size:]

                for i, chunk in enumerate(chunks):
                    print("Uploading chunk {} of {}".format(i, path))
                    piwigo_site.pwg.images.addChunk(
                            data=chunk,
                            original_sum=md5,
                            type="file",
                            position=i)

                print("Final add: {} as {}".format(path, filename))
                piwigo_site.pwg.images.add(original_sum=md5, categories="1",
                        original_filename=filename)
            except Exception as e:
                print("Error uploading {}: {}".format(path, e))
            upload_queue.task_done()

    hash_thread = threading.Thread(target=hash_photo, daemon=True)
    hash_thread.start()
    check_thread = threading.Thread(target=check_photo, daemon=True)
    check_thread.start()
    upload_thread = threading.Thread(target=upload_photo, daemon=True)
    upload_thread.start()

    # Uploading photos.
    print("Uploading photos")
    i = 0
    for photo in photosdb.photos(images=True, movies=False):
        if photo.ismissing:
            continue
        if photo.path is not None:
            hash_queue.put((photo, photo.path))

        if photo.path_edited is not None:
            hash_queue.put((photo, photo.path_edited))
        i += 1
        if i >= 10:
            break
    print("Done loading photos")
        
    hash_queue.join()
    print("Done hashing")
    check_queue.join()
    print("Done checking for photos")
    upload_queue.join()
    print("Done uploading photos")

if __name__ == '__main__':
    sys.exit(main())
