import argparse
from io import BytesIO
import json
import re
import requests
from os import makedirs
from os.path import isfile, isdir, join
import sqlite3
import time
import yt_dlp
from yt_dlp import YoutubeDL

class GetFilesPP(yt_dlp.postprocessor.PostProcessor):
    files = {}
    exts = {}
    def run(self, info):
        self.files[int(info['id'])] = info['filepath']
        self.exts[int(info['id'])] = info['audio_ext']
        return [], info

def fetch_client_id():
    page = requests.get('https://m.soundcloud.com', headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36'})
    if not page.status_code in [200]: raise Exception(f'unable to update client id')
    return re.search(r'"clientId":"([0-9a-zA-Z\-_]{32})",', page.text)[1]

def check_new_tracks(tracks, dbname='autodl.sqlite', grabbed=time.time()):
    with sqlite3.connect(dbname) as conn:
        cur = conn.cursor()
        
        # dedupe track list
        cur.execute(f'SELECT id FROM downloaded_tracks WHERE id IN ({",".join([str(tid) for tid in tracks.keys()])})')
        existing_track_ids = [row[0] for row in cur.fetchall()]
        new_tracks = {t['id']: t for t in tracks.values() if not (t['id'] in existing_track_ids)}
        
        # insert new metas
        for tid, t in tracks.items():
            cur.execute('INSERT INTO track_metas (id, grabbed, metadata) VALUES (?, ?, ?) ON CONFLICT (id) DO NOTHING', (tid, grabbed, json.dumps(t)))
        
        # save metas first in case download crashes and song gets deleted
        cur.close()
        conn.commit()
    
    return new_tracks

headers = {'Origin': 'https://soundcloud.com', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
def main(args):
    ydl_opts = {
        # 'allowed_extractors': ['generic', 'soundcloud'],
        'paths': {'home': args.downloads_folder},
        'writeinfojson': True,
        'writethumbnail': True}
    
    # make outdir if needed
    if not isdir(args.downloads_folder):
        makedirs(args.downloads_folder)
    
    if not isfile('autodl.sqlite'):
        print('couldn\'t find database, have you ran manage_autodl.py yet?'); exit()
    
    # open db conn
    connst = time.time()
    conn = sqlite3.connect('autodl.sqlite', )
    
    # test/load client id
    with sqlite3.connect('autodl.sqlite') as conn:
        cur = conn.cursor()
        cur.execute('SELECT key, value FROM vars;')
        dbvars = {row[0]: row[1] for row in cur.fetchall()}
        client_id = dbvars.get('sc_client_id') if dbvars.get('sc_client_id') else None
        
        
        # test client id
        if client_id:
            print('testing client id..')
            resp = requests.get(f'https://api-v2.soundcloud.com/tracks/2?client_id={client_id}', headers=headers)
        
        # fetch client id if missing or invalid
        if (not client_id) or (resp.status_code == 401):
            print('fetching new soundcloud client_id...')
            client_id = fetch_client_id()
            cur.execute(f'INSERT INTO vars (key, value) VALUES (\'sc_client_id\', ?) ON CONFLICT (key) DO UPDATE SET value = value;', (client_id,))
        
        cur.close()
        conn.commit()
    
    # load user id / track ids
    with sqlite3.connect('autodl.sqlite') as conn:
        cur = conn.cursor()
        
        cur.execute('SELECT permalink, id FROM users;')
        users = {p: i for p, i in cur.fetchall()}
        
        # fetch user ids
        for permalink in [p for p, i in users.items() if not i]:
            print(f'fetching id for user {permalink}')
            resp = requests.get(f'https://api-v2.soundcloud.com/resolve?url=https://soundcloud.com/{permalink}&client_id={client_id}', headers=headers)
            if resp.status_code == 404:
                print(f'user {permalink} does not exist, remove them using manage_autodl.py'); exit()
            elif resp.status_code != 200:
                raise Exception(f'unknown resolve status code {resp.status_code}')
            
            # update db
            userid = resp.json()['id']
            cur.execute('UPDATE users SET id = ? WHERE permalink = ?', (userid, permalink))
            
            users[permalink] = userid
            
            conn.commit()
            time.sleep(1)
        
        cur.close()
    
    while True:
        print()
        iterationstart = time.time()
        
        # fetch tracks
        new_tracks = {}
        for permalink, userid in users.items():
            page = 0
            url = f'https://api-v2.soundcloud.com/users/{userid}/tracks?limit=50&client_id={client_id}'
            while url:
                page += 1
                print(f'checking {permalink} for new tracks (page {page})')
                
                ### TODO: move this to a function for retries/better error handling
                try:
                    rqst = time.time()
                    resp = requests.get(url, headers=headers)
                except Exception as e:
                    print(f'failed to check user tracks, error {e}')
                    time.sleep(args.delay); continue
                if resp.status_code != 200:
                    print(f'failed to check user tracks, bad status code {resp.status_code}')
                    time.sleep(args.delay); continue
                
                j = resp.json()
                user_tracks = {t['id']: t for t in j['collection']}
                user_new_tracks = check_new_tracks(user_tracks, grabbed=rqst)
                
                new_tracks.update(user_new_tracks)
                
                # always paginate if all tracks are new
                url = None
                if ((len(user_new_tracks) == len(user_tracks)) or args.always_paginate) and j['next_href']:
                    url = j['next_href'] + f'&client_id={client_id}'
                
                time.sleep(0.1) # don't go too fast now
        print(f'found {len(new_tracks)} new tracks')
        
        # download tracks
        track_files = {}
        track_exts = {}
        downloaded_tracks = {}
        with YoutubeDL(ydl_opts) as ydl:
            filespp = GetFilesPP()
            ydl.add_post_processor(filespp, when='post_process')
            
            for t in new_tracks.values():
                if args.skip_downloads:
                    print(f'skipping download for {t["user"]["permalink"]} - {t["permalink"]} (id: {t["id"]})')
                    downloaded_tracks[t['id']] = t
                else:
                    print(f'downloading {t["user"]["permalink"]} - {t["permalink"]} (id: {t["id"]})')
                    
                    try:
                        ydl.download([f'https://api-v2.soundcloud.com/tracks/{t["id"]}'])
                        downloaded_tracks[t['id']] = t
                        track_files[t['id']] = filespp.files[t['id']]
                        track_exts[t['id']] = filespp.exts[t['id']]
                    except yt_dlp.utils.DownloadError:
                        print('download failed, skipping for now')
                    except Exception as e:
                        print('\nERROR ERROR ERROR ERROR ERROR ERROR ERROR\n')
                        print(e)
                        print(type(e))
                        print('\nERROR ERROR ERROR ERROR ERROR ERROR ERROR\n')
        
        # mark tracks as finished
        if downloaded_tracks:
            with sqlite3.connect('autodl.sqlite') as conn:
                cur = conn.cursor()
                for t in downloaded_tracks.values():
                    cur.execute(f'INSERT INTO downloaded_tracks (id, user_id, title) VALUES (?, ?, ?) ON CONFLICT (id) DO NOTHING', (t['id'], t['user']['id'], t['title']))
                cur.close()
                conn.commit()
            
            if not args.skip_downloads:
                print(f'downloaded {len(downloaded_tracks)} new tracks')
            
            # do webhooks
            if dbvars.get('webhook'):
                for t in downloaded_tracks.values():
                    print(f'sending webhook for {t["user"]["permalink"]}_{t["permalink"]}')
                    
                    data = {'username': 'soundcloud autodl', 'content': f'grabbed {t["title"]} by {t["user"]["username"]}'}
                    files = {}
                    if track_files.get(t['id']):
                        with open(track_files[t['id']], 'rb') as fh:
                            fbin = BytesIO(fh.read())
                        if len(fbin.read()) > 26210390:
                            data['content'] += '\n(file too large to upload)'
                        else:
                            fbin.seek(0)
                            files = {f'{t["user"]["permalink"]}_{t["permalink"]}.{track_exts[t["id"]]}': fbin}
                    
                    try:
                        resp = requests.post(dbvars['webhook'], data=data, files=files)
                    except Exception as e:
                        print(f'\nWARNING: webhook failed with error {e}\n')
                        continue
                    if resp.status_code > 299: print(f'\nWARNING: webhook failed with code {resp.status_code}\n')
        
        elapsed = time.time() - iterationstart
        if not elapsed >= args.delay:
            print(f'sleeping for {round(args.delay - elapsed, 2)}s')    
            time.sleep(args.delay - elapsed)
        else:
            print(f'sleeping for 0s, if this happens often consider increasing the delay')
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--downloads-folder', default=None, help='folder to download tracks to', required=True)
    parser.add_argument('-d', '--delay', default=5, type=int, help='how many seconds between checking for new tracks (default: 5)')
    parser.add_argument('--skip-downloads', action='store_true', help='skip downloads and only save metadata')
    parser.add_argument('--always-paginate', action='store_true', help='always check all tracks by artists (to get unprivated songs too)')
    args = parser.parse_args()
    
    main(args)
