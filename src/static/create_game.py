from browser import document, ajax
from browser.html import LI
import json
import pickle

def new_game(req):
    global gid
    gid = json.loads(req.text)['game_id']
    print(f"gid: {gid}")
    get_gamestate(req)

def click(event):
    req = ajax.Ajax()
    req.bind('complete', new_game)
    req.set_timeout(4, lambda: print("timed out."))
    #hard coding the start game options for now.
    req.open('GET', 
        f'/start_game/{json.dumps(["Human", "Deedee", "Dexter", "Deedee"])}/{1}', True)
    req.set_header('Content-Type', 'application/json')
    req.send()

document['start_game_button'].bind('click', click)