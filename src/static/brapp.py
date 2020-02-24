from browser import document, ajax
from browser.html import LI
import json


def display_solutions(req):
    print("hold up")
    info = json.loads(req.text)
    print(info)
    # note the syntax for setting the child text of an element
    document['played_so_far'].html = str(info['current_played'])
    document['play_options'].html = ""
    for ckey in info['legal_keys']:
        button_id = "choose_"+ckey
        document['play_options'] <= LI(
            f'''<input type="button" id="{button_id}" class="btn-primary"> 
                  {ckey} 
                </input>''')
        def pick_it(event):
            req = ajax.Ajax()
            req.bind('complete', get_gamestate)
            req.open('POST', '/play_card', 'application/json')
            req.set_header('Content-Type', 'application/json')
            req.send(json.dumps({'game_id': str(gid), 'card_key': ckey}))

        document[button_id].bind('click', pick_it)

#global - a client can only have one active game at a time.
gid = -1

def get_gamestate(req):
    print(f"gid: {gid}")
    req.bind('complete', display_solutions)
    req.open('GET', f'/gamestate?game_id={gid}', True)
    req.set_header('Content-Type', 'application/json')
    req.send()

def new_game(req):
    global gid
    gid = json.loads(req.text)
    print(f"gid: {gid}")
    get_gamestate(req)

def click(event):
    req = ajax.Ajax()
    req.bind('complete', new_game)
    req.set_timeout(4, lambda: print("timed out."))
    req.open('GET', '/start_game', True)
    req.set_header('Content-Type', 'application/json')
    req.send()

document['start_game_button'].bind('click', click)




