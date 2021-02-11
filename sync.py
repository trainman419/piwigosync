#!/usr/bin/env python3

import argparse
import base64
import hashlib
import queue
import sys
import threading

import osxphotos
import piwigo

def print_category(category, indent=""):
    print("{}{}".format(indent, category["name"]))
    for key, val in category.items():
        if key == "sub_categories":
            print("{}  {}:".format(indent, key))
            for c in val:
                print_category(c, indent + "  ")
        elif key == "name":
            continue
        else:
            print("{}  {}: {}".format(indent, key, val))


def get_piwigo_album_map(category, path=()):
    path = (*path, category["name"])
    album_map = {path: category["id"]}
    for sub_category in category.get("sub_categories", []):
        album_map.update(get_piwigo_album_map(sub_category, path))
    return album_map


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

    piwigo_album_map = {}
    for category in piwigo_site.pwg.categories.getList(recursive=True, tree_output=True):
        piwigo_album_map.update(get_piwigo_album_map(category))
    print(piwigo_album_map)

    print("Loading iPhoto library")
    skip_folders = { "iPhoto Events" }
    photosdb = osxphotos.PhotosDB()

    iphoto_album_map = {}
    for album in photosdb.album_info:
        if len(album.folder_names) > 0 and album.folder_names[0] in skip_folders:
            continue

        iphoto_album_map[album.uuid] = (*album.folder_names, album.title)

    print(iphoto_album_map)

    # For each iphoto album that doesn't exist on piwigo, create it.
    def create_album(path):
        print("Create album on piwigo:", path)
        parent = (*path[:-1],)
        parents = [piwigo_album_map[parent]]
        name = path[-1]
        if len(parents) > 0:
            result = piwigo_site.pwg.categories.add(name=name, parents=parents)
        else:
            result = piwigo_site.pwg.categories.add(name=name)
        print("Album created", path, "with id", result["id"])
        return result["id"]

    for uuid, path in iphoto_album_map.items():
        if path not in piwigo_album_map:
            for l in range(1, len(path)):
                parents = path[:l]
                if not parents in piwigo_album_map:
                    piwigo_album_map[parents] = create_album(parents)
            piwigo_album_map[path] = create_album(path)


    hash_queue = queue.Queue()
    check_queue = queue.Queue()
    upload_queue = queue.Queue()
    album_queue = queue.Queue()

    def hash_photo():
        while True:
            photo, path = hash_queue.get()
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
                filename = item[0].original_filename
                if filename is None:
                    filename = item[0].filename
                if result[item[2]] is None:
                    print("Need to upload: {}".format(filename))
                    upload_queue.put(item)
                else:
                    print("Already uploaded: {}, {}".format(filename, result[item[2]]))
                    album_queue.put((item[0], item[2], result[item[2]]))
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
            try:
                data = open(path, "rb").read()
                chunks = []
                chunk_size = 500000
                while len(data) > 0:
                    chunks.append(data[:chunk_size])
                    data = data[chunk_size:]

                for i, chunk in enumerate(chunks):
                    print("Uploading chunk {} of {}".format(i, filename))
                    piwigo_site.pwg.images.addChunk(
                            data=base64.b64encode(chunk),
                            original_sum=md5,
                            type="file",
                            position=i)

                print("Final add: {} as {}".format(path, filename))
                add_result = piwigo_site.pwg.images.add(original_sum=md5, categories="1",
                        original_filename=filename)
                print("ADD RESULT: ", add_result)
                break
                #album_queue.put((photo, md5))
            except Exception as e:
                print("Error uploading {}: {}".format(filename, e))
            upload_queue.task_done()

    def set_albums():
        # For each photo in the album queue, pull the photo info from piwigo and update which
        # albums it is part of.
        while True:
            photo, md5, image_id = album_queue.get()
            categories = []
            for album_info in photo.album_info:
                if album_info.uuid in iphoto_album_map:
                    album = iphoto_album_map[album_info.uuid]
                    if album in piwigo_album_map:
                        categories.append(piwigo_album_map[album])
            if len(categories) > 0:
                info = piwigo_site.pwg.images.getInfo(image_id=image_id)
                existing_categories = {c["id"] for c in info["categories"]}
                print("Existing categories:", existing_categories)
                if not set(categories).issubset(existing_categories):
                    print("Set categories {} for md5 {} and id {}".format(categories, md5, image_id))
                    piwigo_site.pwg.images.setInfo(image_id=image_id, categories=categories)
            album_queue.task_done()

    hash_thread = threading.Thread(target=hash_photo, daemon=True)
    hash_thread.start()
    check_thread = threading.Thread(target=check_photo, daemon=True)
    check_thread.start()
    upload_threads = []
    for i in range(10):
        t = threading.Thread(target=upload_photo, daemon=True)
        t.start()
        upload_threads.append(t)

    album_threads = []
    for i in range(10):
        t = threading.Thread(target=set_albums, daemon=True)
        t.start()
        album_threads.append(t)

    # Uploading photos.
    print("Uploading photos")
    for photo in photosdb.photos(images=True, movies=False):
        if photo.ismissing:
            continue
        if photo.path is not None:
            hash_queue.put((photo, photo.path))

        if photo.path_edited is not None:
            hash_queue.put((photo, photo.path_edited))

    print("Done loading photos")

    hash_queue.join()
    print("Done hashing")
    check_queue.join()
    print("Done checking for photos")
    upload_queue.join()
    print("Done uploading photos")
    album_queue.join()
    print("Done updating album info")

if __name__ == '__main__':
    sys.exit(main())
