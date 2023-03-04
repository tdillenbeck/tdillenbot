#!/usr/bin/env python3

import requests
import argparse
import os

API_KEY = os.environ['REBRANDLY_API_KEY']
LINK_ID = os.environ['REBRANDLY_LINK_ID']


def point_rebrandly(new_id):
    base_url = "https://www.youtube.com/watch?v="
    id = extract_video_id(new_id)
    new_destination = f'https://www.youtube.com/watch?v={id}'

    rebrandly_url = f'https://api.rebrandly.com/v1/links/{LINK_ID}'
    rebrandly_headers = {'apikey': API_KEY, 'Content-Type': 'application/json'}
    rebrandly_json = {"destination": new_destination}

    action = requests.post(rebrandly_url, json=rebrandly_json, headers=rebrandly_headers)
    return action.content


def extract_video_id(url):
    short_url = "https://youtu.be/"
    long_url = "https://www.youtube.com/watch?v="
    live_url = "https://youtube.com/live/"
    if short_url in url:
        id = url.replace(short_url, "")
    elif long_url in url:
        id = url.replace(long_url, "")
    elif live_url in url:
        id = url.replace(live_url, "")
    else:
        id = url

    return id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()

    url = args.url

    id = extract_video_id(url)
    print(f"Setting rebrandly to new id: {id}")
    point_rebrandly(id)
    print("Done setting rebrandly")


