# soundcloud autodownloader
 only tested using python 3.10.11  

# setup
 install requirements.txt:  
 `python -m pip install -r requirements.txt`  

 run `manage_autodl.py`:  
 ```   
what would you like to do?
(A)dd user
(R)emove user
(L)ist users
(D)ump track metadata
set (W)ebhook
(Q)uit
pick an option:
```  

 run `autodl.py`:  
```  
usage: autodl.py [-h] -o DOWNLOADS_FOLDER [-d DELAY] [--skip-downloads] [--always-paginate]

options:
  -h, --help            show this help message and exit
  -o DOWNLOADS_FOLDER, --downloads-folder DOWNLOADS_FOLDER
						folder to download tracks to
  -d DELAY, --delay DELAY
						how many seconds between checking for new tracks (default: 5)
  --skip-downloads      skip downloads and only save metadata
  --always-paginate     always check all tracks by artists (to get unprivated songs too)
```  
 
 run `autodl.py` with `--skip-downloads` temporarily if you don't want it to download all existing tracks
 
# features
 * supports multiple users
 * saves full api metadata
 * upload files to discord with webhooks
 * optionally check older tracks from user (in case an old track is unprivated)
 * can re-download tracks that have had their audio replaced
 * doesn't care if a user changes their url
 
# notes
 you can access the saved api metadata by using [sqlite browser](https://sqlitebrowser.org/) to open the sqlite file, or by using the `D` option with `manage_autodl.py`  
   
 the more users you add the more you'll probably want to increase the delay, I use 60 seconds for 8 users with always-paginate, but you can probably get away with less than that
