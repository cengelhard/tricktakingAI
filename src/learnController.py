
import random as rand
import numpy as np
from deckView import deck52
from heartsView import hearts_points
from heartsModel import HeartsGame
from heartsController import (ControlledGame, 
							  random_controller, 
							  random_legal_controller,
							  hyper_smart_controller,
							  HeartsAdapter,
							  HeartsController)



#indecies for a series of card columns
in_hand           = 0
played_by         = in_hand+1
played_index      = played_by+4
won               = played_index+4
cols_per_card     = won+4
current_points    = 52*cols_per_card
trick_count       = current_points+4
#points_this_trick = trick_count+0   TODO: special col, must be filled in at end of trick
points_on_table   = trick_count+1
points_in_hand    = points_on_table+1
total_cols = points_in_hand + 1


#52 cards, current_points x 4, current_playerx4, trick_count, hand_count, expected points, error?

def card_to_col(card):
	return deck52.index(card)*cols_per_card

#this is from the perspective of the previous player.
#basically, how the most recently played card sees the world.
def featurize_state(state, row = None):
	if row is None:
		row = np.zeros(total_cols)
	current_pid = state.current_turn()-1 #previous player.
	#print(f"current player: {current_pid}")
	player = state.players[current_pid]

	for card in player.hand:
		row[card_to_col(card)+in_hand] = 1

	for player_i,player in enumerate(state.players):
		#normalize it to relative of current player
		player_i = (current_pid - player_i - 0)%4
		player = state.players[player_i]

		#print(f"{player_i} has hand size of {len(player.hand)}")

		row[current_points+player_i] = player.points()
		for played_i,card in enumerate(player.played):
			card_i = card_to_col(card)
			row[card_i+played_by   +player_i] = 1
			row[card_i+played_index+player_i] = played_i/13

		for card in player.won:
			card_i = card_to_col(card)
			row[card_i+won+player_i] = 1

	row[trick_count] = state.trick_count
	row[points_on_table] = sum(map(hearts_points, state.played_this_trick()[1]))/26
	row[points_in_hand] = sum(map(hearts_points, player.hand))/26
	return row


quick_game = HeartsGame(pass_phase=False, num_hands=1)
#returns X, y
def np_from_controllers(controllers, iterations=10, fixed_rows=True):
	expected_rows = iterations*52*4
	X = [] if not fixed_rows else np.zeros(shape=(expected_rows, total_cols))
	y = [] if not fixed_rows else np.zeros(shape=(expected_rows,))
	xi = 0
	for i in range(iterations):
		#rand.shuffle(controllers)
		state, cont = quick_game()
		starting_xi = xi
		while cont:
			state, cont = cont(controllers)
			if not fixed_rows:
				X.append(featurize_state(state))
				y.append(state.current_turn()) #temporarily store the current player.
			else:
				featurize_state(state, X[xi])
				y[xi] = (state.current_turn()-0)%4 #temporarily store the current player.
			xi += 1

		if fixed_rows:
			assert (xi - starting_xi) == 52, "should be 52 rows per hand in fixed_rows"

		scores = [p.total_points() for p in state.players]
		mins = min(scores)
		maxs = max(scores)
		for yi in range(starting_xi, xi):
			#get the score for the current players.
			y[yi] = 0.5 if (mins==maxs) else (scores[int(y[yi])]-mins) / (maxs-mins)
	return np.array(X),np.array(y)

default_controllers = [ctrl(i) for i, ctrl in enumerate([hyper_smart_controller(), random_legal_controller, hyper_smart_controller(), random_legal_controller])]
def sklearn_controller_raw(model, controllers = default_controllers, amount_of_data=10):
	X_train, y_train = np_from_controllers(controllers, amount_of_data)
	model.fit(X_train, y_train)

	no_pass = lambda _,__,___:None

	X_test, y_test = np_from_controllers(controllers, 1)
	y_pred = model.predict(X_test)
	print(f"{model}")
	print(f"avg distance: {np.mean(np.abs(y_test - y_pred))}")
	print(f"pred: {y_pred[:5]}")
	print(f"actl: {y_test[:5]}")

	def controller(pid):

		def try_card(card):
			def try_it(_,__):
				return card
			return try_it
		def try_legal_card(hand, state):
			#will be an empty hand. Just return a legal card though.
			return rand.choice([c for c in deck52 if state.legal_card(c, deck52)])


		def look_ahead_play_card(card, cont, state):
			controllers = [HeartsAdapter(i, HeartsController(pass_cards=no_pass, play_trick=try_card(card))) if i==pid else random_legal_controller(i) for i in range(4)]
			trick = state.trick_count
			state, cont = cont(controllers)
			opponent_preds = []
			while False and cont and state.trick_count == trick: #for each next player in the trick.
				#try a few cards, and find a "worst case" where that player is happiest.
				#15-trick so that it tries 14 on trick 0, 1 on trick 13
				states_conts = [cont(controllers) for _ in range(min(4,14-trick))]
				states, conts = zip(*states_conts)
				predictions = model.predict([featurize_state(st) for st in states])
				best_ind = np.argmin(predictions) #which one turned out best for this opponent.
				state, cont = states_conts[best_ind] #move forward assuming this opponent chose that card.
				opponent_preds.append(predictions[best_ind]) #add the predictions.
				#move on to next opponent

			return featurize_state(state), opponent_preds

		def play_trick(hand, state):
			look_ahead_game = HeartsGame( initial_state = state.unprivate(pid), 
								  initial_cont = "play trick", 
							      initial_pid = pid,
							      num_hands = 1,
							      pass_phase = False)
			state, cont = look_ahead_game()
			lhand = list(hand)
			lhand = [c for c in hand if state.legal_card(c,hand)]
			if len(lhand)==0:
				print(f'passed an empty hand? {state}')
				return None
			elif len(lhand)==1:
				return lhand[0]

			X_hand = []
			X_opponent_preds = []
			for card in lhand:
				my_state, opponent_preds = look_ahead_play_card(card, cont, state)
				#opponent_preds may be an empty list.
				X_hand.append(my_state)
				X_opponent_preds.append(opponent_preds)
			y_hat = model.predict(X_hand)
			num_others = len(X_opponent_preds[0])
			if num_others: #if you aren't last in the trick
				#get the mean of how happy/unhappy each opponent is with a random card they might play.
				opponent_y = np.array([np.mean(preds) for preds in X_opponent_preds])
				
				def normalize(xs):
					return xs
					#return xs - min(xs) + 0.01
					
					#mx, mn = max(xs), min(xs)
					#if mx==mn:
					#	return xs
					#return ((xs-mn) / (mx-mn)) + .01

				opponent_y = normalize(1-opponent_y)
				y_hat = normalize(y_hat)

				#print(["%.2f"%y for y in y_hat])
				#print(["%.2f"%y for y in opponent_y])
				
				y_hat = y_hat * opponent_y**num_others

				#print([c.key+"  " for c in lhand])
				#print(["%.2f"%y for y in y_hat])
			
			return lhand[np.argmin(y_hat)]

		
		return HeartsAdapter(pid, HeartsController(pass_cards=no_pass, 
												   play_trick=play_trick))
	return controller



