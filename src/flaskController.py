
from heartsController import HeartsAdapter, HeartsController, random_legal_controller
from heartsModel import HeartsGame
from deckView import deck52
import json
import pickle
from flask import Flask, redirect, url_for, jsonify, render_template, escape, request, stream_with_context, Response
from driver import controller_cast
from threading import RLock
import time

app = Flask(__name__)

def pprint(s):
    pass
    #print(s, flush=True)

def no_pass(hand, passing_to, points):
     pass

@app.route('/single_player/<int:gid>/<int:pid>')
def single_player(gid, pid):
    return render_template('singlePlayer.html', gid=gid, pid=pid)

@app.route('/game_creation')
def game_creation():
    return render_template('createGame.html')

deedees = [random_legal_controller(i) for i in range(1,4)]
all_deedees = [random_legal_controller(0)] + deedees

def card_from_key(card_key):
    return [c for c in deck52 if c.key == card_key][0]

#not using, might delete
def controllers_play_card(card_key):
    card = card_from_key(card_key)
    return [HeartsAdapter(0, HeartsController(play_trick=lambda _,__: card, pass_cards=no_pass))] + deedees 

#This is the PUBLIC information about a game.
#if you want player specific information (like your hand), 
#use /player_info/{pid}
def json_from_state(state, gid):

    played, played_so_far = state.played_this_trick()
    nplayed = len(played_so_far)

    trick = state.trick_count
    previous = []
    previous_winner = -1
    if trick > 0:
        previous_winner = state.trick_leader
        previous = [p.played[trick-1].key for p in state.players]

    return json.dumps({
            'previous': previous,
            'winner': previous_winner,
            'played': [c.key if c else "__" for c in played],
            'scores': [p.total_points() for p in state.players],
            'gid': gid, #not sure if this will be needed.
            'current turn': state.current_turn()
        })

#this is a global mutable variable to avoid dynamically binding routes
#which is apparently worse than global mutable variables?
#keys = f"{gid}_{pid}"
#values = listen function which closes over a nonlocal var in the controller.
card_choice_listeners = {}
card_choice_lock = RLock()

@app.route('/play_card', methods=['POST'])
def pick_card():

    gid = request.form['gid']
    pid = request.form['pid']
    card_key = request.form['card_key']

    pprint(f"player {pid} wants to play {card_key}")

    listener = None
    with card_choice_lock:
        listener = card_choice_listeners.get(f"{gid}_{pid}")

    if listener:
        listener(card_key)
        return Response("okay, good.")
    else:
        return Response("this gid/pid combo isn't currently listening.")

def FlaskController(gid, pid):

    def play_trick(hand, state):

        #this lock only exists while waiting for a client to give a message.
        card = None
        lock = RLock() 

        pprint('a')

        def listen(card_key):
            pprint('c')
            with lock:
                pprint('d')
                nonlocal card
                card = card_from_key(card_key)

        #add the listener
        with card_choice_lock:
            card_choice_listeners[f"{gid}_{pid}"] = listen
       
        #block the thread waiting for a response from the client.
        while True:
            with lock:
                if card != None:
                    break 
            time.sleep(.01)

        pprint('b')

        #remove the listener
        with card_choice_lock:
            card_choice_listeners[f"{gid}_{pid}"] = None

        #return the chosen card.
        return card

    return HeartsAdapter(pid, HeartsController(
        pass_cards = no_pass,
        play_trick = play_trick,
    ))


game_count = 0 #game id generator.
games = {} #global game states
games_lock = RLock() #make sure reads and writes are atomic

#like games but holds Responses that contain generators.
game_streams = {}
streams_lock = RLock() #I hate how many locks there are, it worries me.

#just for testing.
@app.route('/initial_public/<int:gid>')
def initial_public(gid):
    state = None
    with games_lock:
        state = games.get(gid)
    return Response(json_from_state(state, gid) if state else "bad gid")

@app.route('/game_stream/<int:gid>', methods=["GET"])
def get_stream(gid):
    pprint("looking for a stream")
    stream = None
    with streams_lock:
        stream = game_streams.get(gid)
    pprint("found it" if stream else "nope")
    return stream() if stream else Response("No such gid")

@app.route('/start_game/<string:players>/<int:num_hands>', methods=['GET'])
def play(players, num_hands):

    players = json.loads(players)

    state, cont = HeartsGame(pass_phase=False, num_hands=num_hands)()

    gid = -1
    with games_lock:
        global game_count, games
        gid = game_count
        game_count += 1
        games[gid] = state

    controllers = []
    first_human = -1
    for i in range(4):
        name = players[i]
        if name == "Human":
            if first_human == -1:
                first_human = i
            controllers.append(FlaskController(gid, i))
        else:
            controllers.append(controller_cast[name](i))

    def stream():
        def streamify(s):
            return "data: "+s+"\n\n"
        def eventStream():
            nonlocal state, cont
            while cont: #while the game isn't over
                with games_lock:
                    games[gid] = state
                time.sleep(1) #just for visuals. 
                pprint("yielding")
                yield streamify(json_from_state(state, gid))
                state, cont = cont(controllers)
            with app.test_request_context():
                yield streamify(json.dumps({
                    'final scores': [p.total_points() for p in state.players],
                    'new game url': url_for("game_creation")}))
            #TODO: yield end of game info.
        return Response(eventStream(), mimetype="text/event-stream")

    with streams_lock:
        game_streams[gid] = stream

    #redirect the host to the game. 
    #host is assumed to be the first human.
    #the host can then share links for the other humans. 
    #return redirect(url_for(f'single_player', gid=gid, pid=first_human))
    #return single_player(gid, first_human)
    return Response(url_for(f'single_player', gid=gid, pid=first_human))
 
#get the private player info (or just info specific to a player).
#TODO: add security so players can't cheat and see other players' hands
@app.route("/player_info/<int:gid>/<int:pid>", methods=['GET'])
def player_info(gid, pid):
    state = None
    with games_lock:
        state = games.get(gid)
    if not state:
        return Response("bad game id")

    hand = state.players[pid].hand
    _, played_so_far = state.played_this_trick()

    return jsonify({
            'hand': [{'key': c.key, 
                      'legal': state.legal_card(c, hand)} 
                      for c in hand],
            'you lead': len(played_so_far)%4 == 0,
            'gid': gid #not sure if this will be needed.
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True, threaded=True)

'''
TODO:

+ finish game creation screen.
  - add AIs after training them
+ multiple hands
- end game info dump
  - "play again?" button.
- host it on aws
  - test multiplayer more.
  - train some AIs on aws.

- perf
- beauty

'''

    