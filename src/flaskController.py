
from heartsController import HeartsAdapter, HeartsController, random_legal_controller
from heartsModel import HeartsGame
from deckView import deck52
import json
import pickle
from flask import Flask, redirect, jsonify, render_template, escape, request, stream_with_context, Response
from driver import controller_cast
from threading import RLock
import time

app = Flask(__name__)

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
            'gid': gid #not sure if this will be needed.
        })

def FlaskController(gid, pid):

    def play_trick(hand, state):
        #listen() will fill this in on another thread.
        #rule of thumb: keep locks simple and short and don't compose them.
        #this lock only exists while waiting for a client to give a message.
        #TODO: timeout? vote-kick? host can kick?
        #      some way to get rid of a player who is taking too long.
        card = None
        lock = RLock()

        def listen(card_key):
            with lock:
                nonlocal card
                card = card_from_key(card_key)

        app.add_url_rule(f'/play_card/{gid}/{pid}/<string:card_key>', 'listen', listen, methods=["POST"])
        
        #block the thread.
        while True:
            with lock:
                if card != None:
                    break 
            time.sleep(.1)

        #take the chosen card.
        return card

    return HeartsAdapter(pid, HeartsController(
        pass_cards = no_pass,
        play_trick = play_trick,
    ))

#global game id.
game_count = 0
#global game states
games = {}
#make sure reads and writes are atomic
games_lock = RLock()

@app.route('/start_game/<string:players>/<int:num_hands>', methods=['GET'])
def play(players, num_hands):

    players = json.loads(players)

    gid = -1
    with games_lock:
        global game_count
        gid = game_count
        game_count += 1

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

    state, cont = HeartsGame(pass_phase=False, num_hands=num_hands)()

    global games
    games[gid] = state

    def stream():
        def eventStream():
            nonlocal state, cont
            while cont: #while the game isn't over
                state, cont = cont(controllers)
                with games_lock:
                    games[gid] = state
                yield "data: "+json_from_state(state, gid)
            #TODO: yield end of game info.
        return Response(eventStream(), mimetype="text/event-stream")


    #the single_player page will listen to this.
    #(and on complete it will ask about private information)
    app.add_url_rule(f'/game_stream/{gid}', 'game_stream', stream)

    #redirect the host to the game. 
    #host is assumed to be the first human.
    #the host can then share links for the other humans. 
    return redirect(url_for(f'single_player/{gid}/{first_human}'))
 
#get the private player info (or just info specific to a player).
#TODO: add security so players can't cheat and see other players' hands
@app.route("/player_info/<int:gid>/<int:pid>", methods=['GET'])
def player_info(gid, pid):
    state = None
    with games_lock:
        state = games.get(gid)
    if not state:
        return Response("bad game id")

    hand = state.players[pid]
    _, played_so_far = state.played_this_trick()

    return jsonify({
            'hand': [{'key': c.key, 
                      'legal': state.legal_card(c, hand)} 
                      for c in hand],
            'you lead': len(played_so_far)%4 == 0,
            'gid': gid #not sure if this will be needed.
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True, threaded=True)

    