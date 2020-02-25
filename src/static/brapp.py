from browser import document, ajax
from browser.html import LI
import json
import pickle

def display_solutions(req):
    print("hold up")
    info = json.loads(req.text)

    played_so_far = info['played']
    hand = info['hand']

    nplayed = len(played_so_far)
    document['previous_played'].html = str(info['previous'])
    document['previous_winner'].html = info['winner']
    document['played_so_far'].html = str(played_so_far) if not info['you lead'] else "You are leading the trick." 
    document['play_options'].html = ""
    def pick_by_key(ckey):
        def pick(event):
            req = ajax.Ajax()
            req.bind('complete', get_gamestate)
            req.open('POST', '/play_card')
            req.set_header('Content-Type', 'application/json')
            req.send(json.dumps({'game_id': str(gid), 'card_key': ckey}))
        return pick

    for c in info['hand']:
        ckey = c['key']
        legal = c['legal']
        button_id = "choose_"+ckey
        document['play_options'] <= LI(
            f'''<button 
                       id="{button_id}" 
                       class="btn-{"primary" if legal else "danger"}"
                       {'disabled' if not legal else ''}> 
                  {ckey} 
                </button>''')
        document[button_id].bind('click', pick_by_key(ckey))

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
    gid = json.loads(req.text)['game_id']
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




