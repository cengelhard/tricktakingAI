from browser import document, ajax, window
from browser.html import LI
import json
import pickle

def new_game(req):
    window.location.replace(req.text)

full_cast = ["Human", "Deedee", "Dexter", "Walter", "Galadriel", "Krang", "Peppy"]
controller_nams = ["Human", "Deedee", "Dexter", "Deedee"]

def click(event):
    req = ajax.Ajax()
    req.bind('complete', new_game)
    req.set_timeout(4, lambda: print("timed out."))
    #hard coding the start game options for now.
    req.open('GET', 
        f'/start_game/{json.dumps(controller_nams)}/{document["num_hands"].value}', True)
    req.set_header('Content-Type', 'application/json')
    req.send()

def html_id(pid):
    return f"player_select_{pid+1}"

def update_choices():
    print("um")
    for i in range(4):
        hid = html_id(i)
        ele = document[hid]
        open_hid = hid+"_open"
        ele.innerHTML = f'''<button id="{open_hid}" class="btn-primary" style="width:100px;">{controller_nams[i]}</button>'''
        document[open_hid].bind('click', player_button(i))
        

def player_button(pid):
    def click(event):
        ele = document[html_id(pid)]
        inner = '''
            <div class="custom-select" style="width:200px;">
              <ul>
        '''
        ids_to_clicks = {}
        for name in full_cast: 
            option_id = f"option_{name}_{pid}" 
            inner += f'''
                <li> <button id="{option_id}" class="btn-primary"> {name} 
                </button></li>
            ''' 

            def select_option(event2, name=name):
                controller_nams[pid] = name
                update_choices()

            ids_to_clicks[option_id] = select_option

        ele.innerHTML = inner+"</ul></div>"

        for option_id, f in ids_to_clicks.items():
            document[option_id].bind('click', f)
    return click

document['start_game_button'].bind('click', click)
update_choices()


