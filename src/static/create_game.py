from browser import document, ajax, window
from browser.html import LI
import json
import pickle

def new_game(req):
    window.location.replace(req.text)

def click(event):
    req = ajax.Ajax()
    req.bind('complete', new_game)
    req.set_timeout(4, lambda: print("timed out."))
    #hard coding the start game options for now.
    req.open('GET', 
        f'/start_game/{json.dumps(["Human", "Human", "Dexter", "Deedee"])}/{1}', True)
    req.set_header('Content-Type', 'application/json')
    req.send()

document['start_game_button'].bind('click', click)