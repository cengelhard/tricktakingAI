
from heartsController import HeartsAdapter, HeartsController, random_legal_controller
from heartsModel import HeartsGame
from deckView import deck52
import json
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
	state, cont = cont(all_deedees)
	global games, game_count
	games[game_count] = (state, cont)
	game_count += 1
	return Response(str(game_count-1))

@app.route('/gamestate', methods=['GET'])
def gamestate():
	state, cont = games[int(request.args['game_id'])]
	hand = state.players[0].hand
	legal_keys = [c.key for c in hand if state.legal_card(c, hand)]
	_, played_so_far = state.played_this_trick()
	return Response(json.dumps({
		'legal_keys': legal_keys,
		'current_played': [c.key for c in played_so_far] if len(played_so_far) < 4 else "You are leading the trick."
	}))

@app.route('/play_card', methods=['POST'])
def play_card():
	args = request.json
	gid, card_key = int(args['game_id']), args['card_key']
	state, cont = games[gid]
	state, cont = cont(controllers_play_card(card_key))

	#fast forward to human player's turn.
	while cont and state.current_turn() != 0:
		state, cont = cont(all_deedees)

	if not cont:
		games[gid] = None #game over.
		return Response("game over. TODO: summary.")
	else:
		games[gid] = (state, cont)
		return Response("game is still going. get /gamestate")


	

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8001, debug=True)

    