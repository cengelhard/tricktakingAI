
import random as rand
import numpy as np
from deckView import deck52
from heartsModel import HeartsGame
from heartsController import (ControlledGame, 
							  random_controller, 
							  random_legal_controller,
							  hyper_smart_controller,
							  HeartsAdapter,
							  HeartsController)



#indecies for a series of card columns
in_hand        = 0
played_by      = in_hand+1
played_index   = played_by+4
won            = played_index+4
cols_per_card  = won+4
current_points = 52*cols_per_card
trick_count    = current_points+4
total_cols = trick_count + 1


#52 cards, current_points x 4, current_playerx4, trick_count, hand_count, expected points, error?

def card_to_col(card):
	return deck52.index(card)*cols_per_card

def featurize_state(state, row = None):
	if row is None:
		row = np.zeros(total_cols)
	current_pid = state.current_turn()
	player = state.players[current_pid]

	for card in player.hand:
		row[card_to_col(card)+in_hand] = 1

	for player_i,player in enumerate(state.players):
		#normalize it to relative of current player
		player_i = (current_pid - player_i)%4
		player = state.players[player_i]

		row[current_points+player_i] = player.points()
		for played_i,card in enumerate(player.played):
			card_i = card_to_col(card)
			row[card_i+played_by   +player_i] = 1
			row[card_i+played_index+player_i] = played_i/13

		for card in player.won:
			card_i = card_to_col(card)
			row[card_i+won+player_i] = 1

	row[trick_count] = state.trick_count
	return row


single_state, single_cont = HeartsGame(pass_phase=False, num_hands=1)
#returns X, y
def np_from_controllers(controllers, iterations=10, fixed_rows=True):
	expected_rows = iterations*52*4
	X = [] if not fixed_rows else np.empty(shape=(expected_rows, total_cols))
	y = [] if not fixed_rows else np.empty(shape=(expected_rows,))
	xi = 0
	for i in range(iterations):
		#rand.shuffle(controllers)
		state, cont = single_state, single_cont
		starting_xi = xi
		while cont:
			state, cont = cont(controllers)
			if not fixed_rows:
				X.append(featurize_state(state))
				y.append(state.current_turn()) #temporarily store the current player.
			else:
				featurize_state(state, X[xi])
				y[xi] = state.current_turn() #temporarily store the current player.
			xi += 1

		if fixed_rows:
			assert (xi - starting_xi) == 52, "should be 52 rows per hand in fixed_rows"

		scores = [p.total_points() for p in state.players]
		mins = min(scores)
		maxs = max(scores)
		for yi in range(starting_xi, xi):
			#get the score for the current players.
			y[yi] = (scores[int(y[yi])]-mins) / (maxs-mins)
	return np.array(X),np.array(y)

default_controllers = [hyper_smart_controller(), random_legal_controller, random_legal_controller, random_legal_controller]
def sklearn_controller_raw(model, controllers = [ctrl(i) for i, ctrl in enumerate(default_controllers)]):
	X_train, y_train = np_from_controllers(controllers, 3)
	model.fit(X_train, y_train)

	no_pass = lambda _,__,___:None

	def controller(pid):

		def look_ahead_play_card(card, cont):
			controllers = [HeartsAdapter(i, HeartsController(pass_cards=no_pass, play_trick=lambda _,__: card)) if i==pid else random_legal_controller(i) for i in range(4)]
			state, _ = cont(controllers)
			return featurize_state(state)

		def play_trick(hand, state):
			_, cont = HeartsGame( initial_state = state, 
								  initial_cont = "play trick", 
							      initial_pid = pid,
							      num_hands = 1,
							      pass_phase = False)
			lhand = list(hand)
			lhand = [c for c in hand if state.legal_card(c,hand)]
			if len(lhand)==0:
				print(f'passed an empty hand? {state}')
				return None
			elif len(lhand)==1:
				return lhand[0]

			X_test = []
			for card in lhand:
				X_test.append(look_ahead_play_card(card, cont))
			y_hat = model.predict(X_test)
			mx, mn = max(y_hat), min(y_hat)
			if mx != mn:
				#y_hat =  (y_hat-mn) / (mx-mn)
				#y_hat = 1 - y_hat
				#rind = weighted_random_index(y_hat)
				#print(f"fine hand: {[c.key for c in lhand]}, picking: {lhand[rind].key}")
				#return lhand[rind]
				#choice = rand.choices(population=lhand, weights=y_hat)[0]
				choice = lhand[np.argmin(y_hat)]
				return choice
			else:
				return rand.choice(lhand)
		
		return HeartsAdapter(pid, HeartsController(pass_cards=no_pass, 
												   play_trick=play_trick))
	return controller