import re
import sqlite3

matchSCUserPermalink = re.compile(r'(?:https?://)?(?:www\.|m\.)?soundcloud\.com/([a-z0-9_\-]+)', re.IGNORECASE)

def init_db(conn):
    cur = conn.cursor()
    
    # create table for client id
    cur.execute('CREATE TABLE IF NOT EXISTS vars (key TEXT PRIMARY KEY, value TEXT);')
    
    # create users table
    cur.execute('CREATE TABLE IF NOT EXISTS users (id INT, permalink TEXT PRIMARY KEY)')
    
    # create tracks table
    cur.execute('CREATE TABLE IF NOT EXISTS downloaded_tracks (id INT PRIMARY KEY, user_id INT, title TEXT)')
    
    # create track metas table
    cur.execute('CREATE TABLE IF NOT EXISTS track_metas (id INT PRIMARY KEY, grabbed INT, metadata TEXT)')
    
    cur.close()
    conn.commit()

def main():
    while True:
        print('what would you like to do?')
        print('(A)dd user')
        print('(R)emove user')
        print('(L)ist users')
        print('(D)ump track metadata')
        print('set (W)ebhook')
        print('(Q)uit')
        ui = input('pick an option: ').lower()
        if ui in ['a', 'r', 'l', 'w', 'd']:
            break
        elif ui == 'q':
            exit()
        else:
            print('invalid choice')
            continue
    
    # create db
    conn = sqlite3.connect('autodl.sqlite')
    init_db(conn)
    
    cur = conn.cursor()
    if ui == 'l':
        cur.execute('SELECT id, permalink FROM users;')
        print('\nusers:')
        for uid, ulink in cur.fetchall():
            print(ulink)
    elif ui == 'r':
        u = input('\ngive soundcloud url for user to remove: ')
        u = matchSCUserPermalink.match(u)
        if not u:
            print('bad soundcloud url'); exit()
        u = u[1].lower()
        
        cur.execute('DELETE FROM users WHERE permalink = ?', (u,))
        print(f'removed user {u}')
    elif ui == 'a':
        u = input('\ngive soundcloud url for user to autodl from: ')
        u = matchSCUserPermalink.match(u)
        if not u:
            print('bad soundcloud url'); exit()
        u = u[1].lower()
        
        cur.execute('INSERT INTO users (permalink) VALUES (?) ON CONFLICT DO NOTHING', (u,))
        print(f'added user {u}')
    elif ui == 'w':
        u = input('\ngive webhook to send notifications to: ')
        if u:
            cur.execute('INSERT INTO vars (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value', ('webhook', u))
            print('set webhook')
        else:
            cur.execute('DELETE FROM vars WHERE key = \'webhook\'')
            print('cleared webhook')
    elif ui == 'd':
        u = input('\ngive track id to dump metadata for: ')
        u = int(u) if u.isdigit() else None
        if u:
            cur.execute(f'SELECT metadata FROM track_metas WHERE id = ?', (u,))
            row = cur.fetchone()
            tmeta = row[0] if row else None
            
            if tmeta:
                with open(f'./{u}.json', 'w+', encoding='utf-8') as o:
                    o.write(tmeta)
                print(f'wrote metadata to ./{u}.json')
            else:
                print(f'track {u} is not in database')
            
        else:
            print(f'bad track id provided')
    conn.commit()
    cur.close()
if __name__ == '__main__':
    main()
