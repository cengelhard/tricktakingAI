
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
	return [HeartsAdapter(0, HeartsController(play_card=lambda _,__: card, pass_cards=pass_cards))] + deedees 

@app.route('/start_game', methods=['POST', 'GET'])
def play():
	def generate():
		state, cont = game()
		while cont:
			#fast forward to player's turn.
			while state.current_turn() != 0:
				state, cont = cont(all_deedees)
			hand = state.players[0].hand
			legal_keys = [c.key for c in hand if state.legal_card(c, hand)]
			_, played_so_far = state.played_this_trick()
			yield json.dumps({
				'legal_keys': legal_keys,
				'current_played': [c.key for c in played_so_far] if len(played_so_far) < 4 else "You are leading the trick."
				})
			card_key = request.args['card_key']
			state, cont = cont(controllers_play_card(card_key))
	return Response(stream_with_context(generate()), mimetype='application/json')


@app.route('/play_card', methods=['POST'])
def play_card():
	global state, cont
	state, cont = cont(controllers_play_card(request.json))

	

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8001, debug=True)

    