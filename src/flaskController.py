
from heartsController import HeartsAdapter, HeartsController, random_legal_controller
from heartsModel import HeartsGame
from deckView import deck52
import json
import pickle
from flask import Flask, jsonify, render_template, escape, request, stream_with_context, Response

app = Flask(__name__)

@app.route('/single_player')
def main():
    return render_template('singlePlayer.html')

game = HeartsGame(pass_phase=False, num_hands=1)

def no_pass(hand, passing_to, points):
     pass

deedees = [random_legal_controller(i) for i in range(1,4)]
all_deedees = [random_legal_controller(0)] + deedees
def controllers_play_card(card_key):
    card = [c for c in deck52 if c.key == card_key][0]
    return [HeartsAdapter(0, HeartsController(play_trick=lambda _,__: card, pass_cards=no_pass))] + deedees 

#all continuations of various games.
games = {}
game_count = 0

@app.route('/start_game', methods=['GET'])
def play():
    state, cont = game()
    while cont and state.current_turn() != 0:
        state, cont = cont(all_deedees)
    #state, cont = cont(all_deedees)
    global games, game_count
    games[game_count] = (state, cont)
    game_count += 1
    return jsonify({'game_id': game_count-1})

@app.route('/gamestate', methods=['GET'])
def gamestate():
    state, cont = games[int(request.args['game_id'])]

    #fast forward to this player's turn. 
    #while cont and state.current_turn() != 0:
    #    state, cont = cont(all_deedees)

    hand = state.players[0].hand
    played, played_so_far = state.played_this_trick()
    nplayed = len(played_so_far)

    trick = state.trick_count
    previous = []
    previous_winner = -1
    if trick > 0:
    	previous_winner = state.trick_leader
    	previous = [p.played[trick-1].key for p in state.players]

    return jsonify({
            'hand': [{'key': c.key, 
                      'legal': state.legal_card(c, hand)} 
                      for c in hand],
            'previous': previous,
            'winner': previous_winner,
            'played': [c.key if c else "__" for c in played],
            'you lead': len(played_so_far)%4 == 0,
            'scores': [p.total_points() for p in state.players]
        })

@app.route('/play_card', methods=['POST'])
def play_card():
    args = request.json
    gid, card_key = int(args['game_id']), args['card_key']
    state, cont = games[gid]
    controller = controllers_play_card(card_key)
    state, cont = cont(controller)

    #fast forward to human player's turn.
    while cont and state.current_turn() != 0:
        state, cont = cont(controller)

    if not cont:
        games[gid] = None #game over.
        return Response("game over. TODO: summary.")
    else:
        games[gid] = (state, cont)
        return Response("game is still going. get /gamestate")


    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)

    