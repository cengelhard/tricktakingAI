from browser import document, ajax, window, bind, timer
from browser.html import LI
import json
import pickle
import time
from threading import RLock, Lock
from queue import Queue

def pprint(*args):
    pass
    #print(*args)

#global - a client can only have one active game at a time.
#these are rendered to hidden elements on the html
#because I'm not sure how to pass it directly with brython.
gid = int(document['gid'].innerHTML)
pid = int(document['pid'].innerHTML)

def display_public_info(info):
    played_so_far = info['played']

    nplayed = len(played_so_far)
    document['previous_played'].html = str(info['previous'])
    document['played_so_far'].html = str(played_so_far) #if not info['you lead'] else "You are leading the trick." 
    document['scores'].html = str(info['scores'])

    if info["winner leading"]:
        winner = info['winner']
        lead_text = "You are" if winner == pid else f"Player {winner} is"
        document['played_so_far'].html = f"{lead_text} leading the trick."
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
    my_turn = info['current turn'] == pid
    for c in info['hand']:
        ckey = c['key']
        legal = my_turn and c['legal']
        button_id = "choose_"+ckey
        document['play_options'] <= LI(
            f'''<button 
                       id="{button_id}" 
                       class="btn-{"primary" if legal else "danger"}"
                       {'disabled' if not legal else ''}> 
                  {ckey} 
                </button>''')
        document[button_id].bind('click', pick_by_key(ckey))
    names = ["Dexter", "Peppy", "Galadriel", "Krang", "Walter"]
    hints_ul = document["hint_buttons"]
    if my_turn:
        def handle_hint(button_id, name):
            def get_hint(event):
                document[button_id].innerHTML = name+": "+info['hints'][name]
            return get_hint
        hints_ul.innerHTML = ""
        for name in names:
            button_id = "give_hint_"+name
            hints_ul <= LI(f'''
                <button id="{button_id}" class="btn-primary">{name}</button>
            ''')

            document[button_id].bind("click", handle_hint(button_id, name))
    else:
        hints_ul.innerHTML = ""
            


evtSource = window.EventSource.new(f'/game_stream/{gid}/{pid}')

def render_stream(event):
    pprint("rendering...")
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

q = Queue()

def take_from_queue():
    try:
        event = q.get(False)
    except:
        return
    render_stream(event)
    q.task_done()
    
    

def receive_stream(event):
    q.put(event)
        

evtSource.onmessage = receive_stream
window.on_message = receive_stream

window.setInterval(take_from_queue, 500)












