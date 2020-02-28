
from heartsController import HeartsAdapter, HeartsController, random_legal_controller
from heartsModel import HeartsGame
from deckView import deck52
import json
import pickle
from flask import Flask, redirect, url_for, jsonify, render_template, escape, request, stream_with_context, Response
from driver import controller_cast
from threading import RLock, Thread
from queue import Queue
import time

app = Flask(__name__)

def pprint(*s):
    pass
    #print(*s, flush=True)

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

        def listen(card_key):
            with lock:
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


#key is gid. val is list of queues. 
#each stream has a queue
#each game puts to all queues in its list. (a game is just a worker thread.)
#connecting to a stream adds a queue to the list. 
game_queues = {}
queues_lock = RLock() 
#the queues themselves are lockless, but the dictionary is not.
#but it only needs to lock when a new stream connects or a game starts/finishes.
#the streams theselves only know about their own queue.

#just for testing.
@app.route('/initial_public/<int:gid>')
def initial_public(gid):
    state = None
    with games_lock:
        state = games.get(gid)
    return Response(json_from_state(state, gid) if state else "bad gid")

@app.route('/game_stream/<int:gid>', methods=["GET"])
def get_stream(gid):
    pprint("looking for a game queue list")

    def streamify(s):
        return "data: "+s+"\n\n"
    
    q = None
    with queues_lock:
        pprint(gid, game_queues)
        qs = game_queues.get(gid)
        if qs is not None:
            q = Queue()
            qs.append(q)
    if q is not None:
        pprint("found one")
        def stream():
            game_is_going = True
            while game_is_going:
                pprint("should yield something.")
                state, game_is_going = q.get()
                q.task_done()
                if game_is_going:
                    yield(streamify(json_from_state(state, gid)))
                else:
                    with app.test_request_context():
                        yield streamify(json.dumps({
                            'final scores': [p.total_points() for p in state.players],
                            'new game url': url_for("game_creation")}))

        
        return Response(stream(), mimetype="text/event-stream")
    pprint("didn't find one.")
    return Response("no such gid")


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

    local_queues = [] #will be mutated in place I think.
    with queues_lock:
        game_queues[gid] = local_queues #this will be filled in when clients connect.

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

    #will wait for somebody to connect.
    #will push all new states to all queues.
    #has its own thread and mostly pushes to queues.
    def run_game():
        nonlocal state, cont

        #first wait for somebody to connect.
        while True:
            with queues_lock:
                if len(local_queues):
                    break
            time.sleep(1)

        while cont:
            state, cont = cont(controllers)
            with games_lock:
                games[gid] = state
            with queues_lock:
                for q in local_queues:
                    q.put((state, cont))
            time.sleep(2)

        with games_lock:
            games.pop(gid)
        with queues_lock:
            game_queues.pop(gid)
            '''
            notably, any queues still in use will still exist
            and not be garbage collected until they are done.
            but NEW queues/streams will not be possible.
            '''

    t = Thread(target=run_game, daemon=True)
    t.start()

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

    