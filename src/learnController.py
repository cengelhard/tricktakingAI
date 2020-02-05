
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
import math


#indecies for a series of card columns
in_hand           = 0
played_by         = in_hand+1
#played_index      = played_by+4
won               = played_by+4
cols_per_card     = won+1#played_by+4#won+4

current_points    = 52*cols_per_card
trick_count       = current_points+4
#points_this_trick = trick_count+0   TODO: points won because of this card you played.
points_on_table   = trick_count+1
points_in_hand    = points_on_table+1
points_won        = points_in_hand+1 #total number of points that have been won so far
danger            = points_won+1 #points unaccounted-for * trick_count
highest_rank      = danger+1 #highest rank on the table.
recent_rank       = highest_rank+1  #rank of most recently played card.
recent_QS         = recent_rank+1 #was the played card the Queen.
rank_ratio        = recent_QS+1
new_trick         = rank_ratio+1
total_cols = new_trick + 1


#52 cards, current_points x 4, current_playerx4, trick_count, hand_count, expected points, error?

def card_to_col(card):
	return deck52.index(card)*cols_per_card

#this is from the perspective of the previous player.
#basically, how the most recently played card sees the world.
def featurize_state(state, row = None):
	if row is None:
		row = np.zeros(total_cols)
	current_pid = state.last_played
	player = state.players[current_pid]

	for card in player.hand:
		row[card_to_col(card)+in_hand] = 1

	for objective_i,player in enumerate(state.players):
		#normalize it to relative of current player

		player_i = (current_pid - objective_i)%4
		inner_player = state.players[player_i]

		row[current_points+player_i] = inner_player.points_sans_penalty()/26
		#print(f"{player_i} has hand size of {len(player.hand)}")

		row[player_i] = inner_player.points()
		for played_i,card in enumerate(inner_player.played):
			card_i = card_to_col(card)
			row[card_i+played_by+player_i] = 1
			#row[card_i+played_index+player_i] = played_i/13

		for card in player.won:
			card_i = card_to_col(card)
			row[card_i+won+player_i] = 1
	_, played = state.played_this_trick()
	row[trick_count]     = state.trick_count/13
	row[points_on_table] = sum(map(hearts_points, state.played_this_trick()[1]))/26
	row[points_in_hand]  = sum(map(hearts_points, player.hand))/26
	row[points_won]      = sum(sum(map(hearts_points, p.won)) for p in state.players)/26
	row[danger]          = row[trick_count] * (1-row[points_on_table]-row[points_in_hand]-row[points_won])
	row[highest_rank]    = (max(card.rank for card in played)+1)/13
	row[recent_rank]     = (played[-1].rank+1)/13
	row[recent_QS]       = played[-1].key == "Q♠"
	row[rank_ratio]      = row[recent_rank] / row[highest_rank]
	row[new_trick]       = len(played)%4 == 0
	return row

from collections import Counter

#a model for every trick?

quick_game = HeartsGame(pass_phase=False, num_hands=1)
default_controllers = [ctrl(i) for i, ctrl in enumerate([hyper_smart_controller(), random_legal_controller, hyper_smart_controller(), random_legal_controller])]
default_controllers = [ctrl(i) for i, ctrl in enumerate([random_legal_controller, random_legal_controller, random_legal_controller, random_legal_controller])]
default_controllers = [ctrl(i) for i, ctrl in enumerate([hyper_smart_controller(), hyper_smart_controller(), hyper_smart_controller(), hyper_smart_controller()])]
#returns X, y
def np_from_controllers(controllers=default_controllers, iterations=10, fixed_rows=True):
	expected_rows = iterations*52
	X = [] if not fixed_rows else np.zeros(shape=(expected_rows, total_cols))
	y = [] if not fixed_rows else np.zeros(shape=(expected_rows,))
	xi = 0
	for i in range(iterations):
		#rand.shuffle(controllers)
		state, cont = quick_game()
		starting_xi = xi
		y_pids = []
		while cont:
			prev_turn = state.current_turn()
			if prev_turn == -1: #it's the first turn.
				prev_turn = state.trick_leader #it was the 2 of clubs.
			state, cont = cont(controllers)
			if not fixed_rows:
				X.append(featurize_state(state))
				y.append(prev_turn) #temporarily store the current player.
			else:
				featurize_state(state, X[xi])
				y_pids.append(prev_turn) #temporarily store the current player.
			xi += 1

		if fixed_rows:
			assert (xi - starting_xi) == 52, "should be 52 rows per hand in fixed_rows"
		assert len(y_pids)==52, f"um what {len(y_pids)}"
		scores = [p.total_points() for p in state.players]
		#print("scores though.")
		#print(scores)
		for yi in range(starting_xi, xi):
			#get the score for the current players.
			y[yi] = scores[(y_pids[yi-starting_xi])]/26
	#print(Counter(y))
	return np.array(X),np.array(y)


import matplotlib.pyplot as plt

def sklearn_controller_raw(model, controllers = default_controllers, amount_of_data=10):
	
	no_pass = lambda _,__,___:None

	if amount_of_data: #assume the model is already trained otherwise.
		X_train, y_train = np_from_controllers(controllers, amount_of_data)
		model.fit(X_train, y_train)

		#X_test, y_test = X_train, y_train
		X_test, y_test = np_from_controllers(controllers, amount_of_data//2)
		y_pred = model.predict(X_test)
		#mn, mx = min(y_pred), max(y_pred)
		#y_pred = (y_pred-mn)/(mx-mn)
		y_pred[y_pred < 0] = 0
		print(f"{model}")
		diff = y_test - y_pred

		fig, axs = plt.subplots(3)
		bins = 26
		axs[0].hist(y_test, bins=bins, label="actual")
		axs[1].hist(y_pred, bins=bins, label="predicted")
		axs[2].hist(diff,   bins=bins*2, label="diff")

		axs[0].set_xlim(0,1)
		axs[1].set_xlim(0,1)
		axs[2].set_xlim(-1,1)

		print(f"avg abs diff: {np.mean(np.abs(diff))}")
		print(f"mean diff: {np.mean(diff)}")
		print(f"std of diff : {np.std(diff)}")
		print(f"pred spread: {(np.mean(y_pred), np.std(y_pred))}")
		print(f"pred spread: {(min(y_pred), np.median(y_pred), max(y_pred))}")
		print(f"pred: {y_pred[50:55]}")
		print(f"actl: {y_test[50:55]}")

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

				print(["%.2f"%y for y in y_hat])
				print(["%.2f"%y for y in opponent_y])
				
				y_hat = y_hat * opponent_y**num_others

				print([c.key+"  " for c in lhand])
				print(["%.2f"%y for y in y_hat])
			
			return lhand[np.argmin(y_hat)]

		
		return HeartsAdapter(pid, HeartsController(pass_cards=no_pass, 
												   play_trick=play_trick))
	return controller



