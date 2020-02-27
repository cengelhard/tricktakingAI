from browser import document, ajax, window, bind
from browser.html import LI
import json
import pickle

def pprint(*args):
    pass
    #print(*args)

#global - a client can only have one active game at a time.
#these are rendered to hidden elements on the html
#because I'm not sure how to pass it directly with brython.
gid = int(document['gid'].innerHTML)
pid = int(document['pid'].innerHTML)

def display_private_info(req):
    pprint("private")
    info = json.loads(req.text)

    #overwrite it.
    if info["you lead"]:
        document['played_so_far'].html = "You are leading the trick."
    hand = info['hand']

    document['play_options'].html = ""
    def pick_by_key(ckey):
        def pick(event):
            req = ajax.Ajax()
            #req.bind('complete', get_gamestate)
            req.open('POST', '/play_card')
            #req.set_header('Content-Type', 'application/json')
            req.set_header('content-type', 'application/x-www-form-urlencoded')
            req.send({'gid': gid, 'pid': pid, 'card_key': ckey})
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

def display_public_info(info):
    pprint("public")
    pprint(info)
    played_so_far = info['played']

    nplayed = len(played_so_far)
    document['previous_played'].html = str(info['previous'])
    document['previous_winner'].html = info['winner']
    document['played_so_far'].html = str(played_so_far) #if not info['you lead'] else "You are leading the trick." 
    document['scores'].html = str(info['scores'])

    if info['current turn'] == pid:
        req = ajax.Ajax()
        req.bind('complete', display_private_info)
        req.open('GET', f'/player_info/{gid}/{pid}')
        req.set_header('Content-Type', 'application/json')
        req.send()

def initial_public_info(req):
    return display_public_info(json.loads(req.text))

evtSource = window.EventSource.new(f'/game_stream/{gid}')

def receive_stream(event):
    pprint("streaming")
    pprint(event.data)
    data = json.loads(event.data)
    final_scores = data.get('final scores')
    if final_scores: #game is over.
        winners = [i for i in range(4) if final_scores[i] == min(final_scores)]
        root = document["root_container"]
        win_msg = f"player {winners[0]} wins!" if len(winners)==1 else f"it's a tie between {str(winners)}!"
        root.innerHTML = f''' <p>GAME OVER</p>
            <p>final scores: {str(final_scores)} </p>
            <p>{win_msg}</p>
            <button id="play again" class="btn-primary"> play again? </button>
        '''
        document["play again"].bind("click", lambda evt: window.location.replace(data['new game url']))
    else:
        display_public_info(data)

evtSource.onmessage = receive_stream
window.on_message = receive_stream







