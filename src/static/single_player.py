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
# req = ajax.Ajax()
# req.bind('complete', initial_public_info)
# req.open('GET', f'/initial_public/{gid}')
# req.set_header('Content-Type', 'application/json')
# req.send()

evtSource = window.EventSource.new(f'/game_stream/{gid}')

def receive_stream(event):
    pprint("streaming")
    pprint(event.data)
    display_public_info(json.loads(event.data))

evtSource.onmessage = receive_stream
window.on_message = receive_stream







