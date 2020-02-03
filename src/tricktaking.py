

from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)
from deck import deck52, Card, suit_keys
import random as rand
import sys

def hearts_points(card):
	return 1 if card.suit == "♥" else 13 if card.key == "Q♠" else 0

len4 = lambda p: (len(p)==4, "must be len 4")


#public information about a player in a hand of Hearts.
class HeartsPlayer(PRecord):

	#cards you've played previously this hand.
	played = pvector_field(Card, initial=v())
	#cards you've won in previous tricks this hand.
	won    = pvector_field(Card, initial=v())
	hand   = pset_field(Card, initial=s())

	#What you did in the previous hand.
	prev_player = field(initial=None) #field(type=('tricktaking.HeartsPlayer', type(None)))

	penalty = field(int, initial=0)


	def points_sans_penalty(self):
		return sum(map(hearts_points, self.won))
	def points(self):
		return self.points_sans_penalty() + self.penalty
	def total_points(self):
		return self.points() + (self.prev_player.total_points() if self.prev_player else 0)
	def privatize(self):
		return self.set(hand=s())
	def play_card(self, card):
		return self.set(played = self.played.append(card), hand=self.hand.remove(card))
	def with_penalty(self, amount=10):
		return self.set(penalty=self.penalty+amount)
	def shot_the_moon(self):
		return self.points_sans_penalty() == 26

class PlayerVec(CheckedPVector):
	__type__ = HeartsPlayer

unsigned = field(int, 
				 initial=0, 
				 invariant=lambda n: 
				 	(n >= 0, f"unsigned int can't be negative. got {n}"))

#the four players
class GameState(PRecord):

	players = field(PlayerVec, invariant=len4)
	trick_leader = field(int, 
						 mandatory=True, 
						 invariant=lambda x: (x<4, f"trick_leader cannot be {x}"), 
						 initial=-1)
	hand_count = unsigned 
	trick_count = field(int, initial=0, invariant = lambda n: (n >= 0 and n <= 13, f"trick count should be betwen 0 and 12. got {n}")) 
	#error = field(bool, initial=False)
	#featurization might want this.


	def _delta_pass(self, from_pid, dir):
		return (from_pid + dir*(((self.hand_count)%3) + 1))%4

	def passing_to(self,from_pid):
		'''get the player that from_pid will be passing to.'''
		return self._delta_pass(from_pid, 1)

	def passing_from(self,from_pid):
		'''inverse of passing_to'''
		return self._delta_pass(from_pid, -1)

	def set_player(self, pid, player):
		return self.set(players=self.players.set(pid, player))

	def map_players(self, f):
		return self.set(players=PlayerVec.create(map(f, range(4), self.players)))

	def private_to(self, pid): #i should not be able to see others' hands
		return self.map_players(lambda i, p: p if pid==i else p.privatize())

	def played_this_trick(self):
		'''returns both positional and list form.'''
		lens = [len(p.played) for p in self.players]
		m = max(lens)
		positional = pvector([p.played[-1] if len(p.played)==m else None for p in self.players])
		return positional, pvector(filter(None, positional))

	def hand_done(self):
		return self.trick_count == 12
		#return all(len(p.played)==13 for p in self.players)

	def current_turn(self):
		'''whose turn is it?'''
		_, played_so_far = self.played_this_trick()
		num_played = len(played_so_far)
		return (self.trick_leader + num_played)%4

	def legal_card(self, card, hand):
		played, only_played = self.played_this_trick()
		lsuit = played[self.trick_leader].suit
		not_in_hand = not (card in hand)
		not_first_play = len(only_played) != 4
		wrong_suit = card.suit != lsuit
		no_excuse = lsuit in [c.suit for c in hand]
		return not(not_in_hand or (not_first_play and wrong_suit and no_excuse))

def deal_4_players(deck):
	return [pset(h) for h in [deck[:13], deck[13:26], deck[26:39], deck[39:]]]

default_state = GameState(players=PlayerVec.create([HeartsPlayer() for _ in range(4)]))

def nextp(i):
	return (i+1)%4

#returns a function that starts the game.
#a msg, 4-tuples of functions for choices, and a second 'continuation' function.
#each player passes a callback to their function which is passed their hand and returns their choices.
#those returns get combined together into the continuation function.
#that returns a new continuation
def HeartsGame(initial_state = default_state, 
			   initial_cont = "play hand", 
		       initial_pid = -1,
		       num_hands = 3,
		       pass_phase = True):

	def private_call(controllers, key, state):
		return [controllers[i][key](state.private_to(i)) for i in range(4)]

	#takes a previous state from previous hands.
	def play_hand(prior_state):

		hands = None
		if len(prior_state.players[0].hand):
			#it is possible that the prior state already has hands set.
			hands = [p.hand for p in prior_state.players]
		else:
			deck = list(deck52)
			rand.shuffle(deck)
			hands = deal_4_players(deck)
		unpassed_state = prior_state.map_players(lambda i,p: p.set(hand=pset(hands[i])))
		def pass_cards(controllers):
			state = unpassed_state
			if pass_phase:
				choices = [pset(choice) for choice in private_call(controllers, "pass_cards", unpassed_state)]
				#choices = [pset(f(unpassed_state)) for f in chooser_fns]
				bad_choices = [len(cs) != 3 or (not cs.issubset(unpassed_state.players[i].hand)) for i,cs in enumerate(choices)]
				if any(bad_choices):
					#try again with penalties.
					return play_hand(state.map_players(lambda i, p: p if not bad_choices[i] else p.with_penalty()))
				def pass_helper(pass_to):
					pass_from = state.passing_from(pass_to)
					return hands[pass_to].difference(choices[pass_to]).union(choices[pass_from]) 
				new_hands = [pass_helper(i) for i in range(4)]
				state = state.map_players(lambda i, p: p.set(hand=new_hands[i], played=v(), prev_player=p))
			
			leader_i = 0
			leader_p = None
			two_of_clubs = None 
			for i in range(4):
				p = state.players[i]
				h = p.hand
				for c in h:
					if c.key == "2♣":
						leader_i = i
						leader_p = p
						two_of_clubs = c
						break
				if two_of_clubs:
					break
			new_state = state.set_player(leader_i, leader_p.play_card(two_of_clubs))
			return play_trick_card(nextp(leader_i), new_state.set(trick_leader=leader_i))

		return unpassed_state, pass_cards

	def play_trick_card(pid, state):
		player = state.players[pid]
		hand = player.hand
		turn_state = state
		def cont(controllers):
			substate = state
			card = controllers[pid].play_trick(state.private_to(pid)) #only care about one of the returns.
			legals = [c for c in hand if state.legal_card(c, hand)]
			if card not in legals:
				#try again with penalty
				#return play_trick_card(pid, state.set_player(pid, player.with_penalty()))
				#get random with penalty.
				card = rand.choice(legals)
				nonlocal player
				player = player.with_penalty()
				substate = substate.set_player(pid, player) 

			played_state = substate.set_player(pid, player.play_card(card))
			private_call(controllers, "alert_played", played_state)

			played, only_played = played_state.played_this_trick()

			if len(only_played) < 4:
				return play_trick_card(nextp(pid), played_state)
			else:
				led_card = only_played[nextp(pid)] #loop around to see the leader.
				lsuit = led_card.suit
				best_pid = -1
				best_rank = led_card.rank
				winner = None
				for i in range(4):
					card2 = played[i]
					if card2.suit == lsuit and card2.rank >= best_rank:
						best_pid = i
						best_rank = card2.rank
						winner = played_state.players[i]
				winner_state = played_state.set(trick_leader=best_pid).set_player(best_pid, winner.set(won = winner.won.extend(played)))
				if winner_state.hand_done():
					private_call(controllers, "alert_hand_complete", winner_state)
					if winner_state.hand_count == num_hands-1:
						return winner_state, None
					else:
						moon_shooters = pvector(p.shot_the_moon() for p in winner_state.players)
						winner_state = winner_state.set(hand_count=winner_state.hand_count+1,
														trick_count=0)
						if any(moon_shooters):
							private_call(controllers, "alert_shot_moon", winner_state)
							moon_shooter = moon_shooters.index(True)
							return play_hand(winner_state.map_players(lambda i, p: p.with_penalty(-26 if i==moon_shooter else 26)))
						else:
							return play_hand(winner_state)
				else:
					private_call(controllers, "alert_trick_complete", winner_state)
					return play_trick_card(best_pid, winner_state.set(trick_count=winner_state.trick_count+1))	
		return state, cont


	return play_hand(initial_state) if initial_cont=="play hand" else play_trick_card(initial_pid, initial_state)

def ControlledGame(game, controllers):
	state, cont = game
	while cont:
		try:
			state, cont = cont(controllers)
		except QuitGameException:
			print("quitting game")
			return
	return state

dont_care = lambda _:_
#basically just names to lambdas.
class HeartsController(PRecord):
	#required to play the game.
	play_trick = field(mandatory=True)
	pass_cards  = field(mandatory=True)

	#for IO, no return value.
	#these actually are mandatory when you pass it into the model.
	#but HeartsAdapter fills them in.
	alert_played         = field()
	alert_trick_complete = field()
	alert_hand_complete  = field()
	alert_shot_moon      = field()

#converts functions that take (state) into more useful args
#basically this just covers boilerplate for hand-coded controllers.
def HeartsAdapter(pid, ctrlr):

	def my_hand(state):
		return state.players[pid].hand

	def pass_cards(state):
		return ctrlr.pass_cards(my_hand(state), 
								state.passing_to(pid), 
								[p.total_points() for p in state.players])

	def play_trick(state):
		return ctrlr.play_trick(my_hand(state), state)

	#alerts
	#TODO: find a clever way to factor these.
	def alert_played(state):
		f = ctrlr.get('alert_played')
		if f:
			curr = state.trick_leader
			played, _ = state.played_this_trick()
			f(curr, played[curr])
	def alert_trick_complete(state):
		f = ctrlr.get('alert_trick_complete')
		if f:
			played, _ = state.played_this_trick()
			f(state, played)
	def alert_hand_complete(state):
		f = ctrlr.get('alert_hand_complete')
		if f:
			f(state.players) #probably want scores.
	def alert_shot_moon(state):
		f = ctrlr.get('alert_shot_moon')
		if f:
			f(state.trick_leader)

	return HeartsController(
		pass_cards = pass_cards,
		play_trick = play_trick,
		alert_played=alert_played,
		alert_trick_complete=alert_trick_complete,
		alert_hand_complete=alert_hand_complete,
		alert_shot_moon=alert_shot_moon
	)

#a completely random AI.
def random_controller(pid):
	def pass_cards(hand, passing_to, points):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		if len(hand):
			return rand.choice(tuple(hand))
		else:
			print("was passed an empty hand?")

	return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))

#random within legality
def random_legal_controller(pid):
	def pass_cards(hand, passing_to, points):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		assert len(hand), f"passed an empty hand? {state}"
		return rand.choice(tuple([c for c in hand if state.legal_card(c,hand)]))



	return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))

from termcolor import cprint

class QuitGameException(Exception):
	pass

def input_controller(pid):

	def print_hand(hand):
		print("your hand:")
		cprint("|".join(f"{i}:{card.key}" for i,card in enumerate(hand)), "red")

	def _input(hand):

		string = input("--->")
		if string[0] == '/':
			command = string[1:]
			if command == "quit":
				raise QuitGameException()
			elif command == "hand":
				print_hand(hand)
				return _input(hand)
			elif command == "score":
				pass 
		return string

	def pass_cards(hand, passing_to, points):
		print(f"player {pid}, please choose 3 card indecies, separated by commas.")
		print(f"passing to: {passing_to}")
		hand = list(hand)
		print_hand(hand)
		try:
			choices = [hand[int(sub)] for sub in _input(hand).split(',')]
			if len(choices)==3:
				return choices
		except QuitGameException:
			raise QuitGameException()
		except:
			pass
		print("something wasn't right.")
		return pass_cards(hand, passing_to, points)

	def play_trick(hand, state):
		print(f"---player {pid}'s turn---")

		#TODO: print how the previous trick went.

		played, just_played = state.played_this_trick()
		nplayed = len(just_played)
		if nplayed == 4:
			print("You are leading the trick.")
		else:
			leader = nextp(pid)
			while played[leader] == None:
				leader = nextp(leader)
			print(f"{[(c.key if c else '__') for c in played]}")
			#print(f"played so far: {[c.key for c in played.extend(played)[leader:leader+nplayed]]}")
			
		lhand = list(hand)
		lhand.sort(key=lambda c: state.legal_card(c, hand))
		lhand = lhand[::-1]
		print_hand(lhand)
		try:
			choice = lhand[int(_input(lhand))]
			return choice
		except QuitGameException:
			raise QuitGameException()
		except:
			pass
		print("something wasn't right")
		return play_trick(lhand, state)

	def alert_played(pid, card):
		pass#print(f"{other_pid} played {card.key}")

	def alert_trick_complete(state, played):
		print(f"{[c.key for c in played]}")
		print(f"{state.trick_leader} wins!")

	def alert_hand_complete(players):
		print(f"hand score : {[p.points() for p in players]}")
		print(f"total score: {[p.total_points() for p in players]}")

	return HeartsAdapter(pid,HeartsController(
		pass_cards=pass_cards,
		play_trick=play_trick,
		alert_played=alert_played,
		alert_trick_complete=alert_trick_complete,
		alert_hand_complete=alert_hand_complete))

#did a simplex descent and 0 was the best losing_index for both sort and non sort.
#non-sort also performed better.
def hyper_smart_controller(losing_index=0, sort_rank=False):

	def smart_controller(pid):

		def card_power(hand):
			by_suit = {s: list(filter(lambda c: c.suit==s, hand)) for s in suit_keys}
			return lambda c: (hearts_points(c)+1)**2 * (c.rank+1) / (len(by_suit[c.suit])+1)

		def sorted_hand(hand):
			lhand = list(hand)
			lhand.sort(key=card_power(hand), reverse=True)
			return lhand

		def pass_cards(hand, passing_to, points):
			return sorted_hand(hand)[:3]

		def play_trick(hand, state):
			played, played_so_far = state.played_this_trick()
			if state.trick_leader == pid:
				#lead card. for now just play weakest card.
				return sorted_hand(hand)[-1]
			else:
				#following
				on_suit = [c for c in hand if c.suit == played[state.trick_leader].suit]
				legals = [c for c in hand if state.legal_card(c,hand)]
				legals.sort(key=card_power(hand), reverse=True)
				points_in_play = sum(hearts_points(c) for c in played_so_far)
				points_previously_played = sum(sum(hearts_points(c) for c in p.won) for p in state.players)
				points_in_hand = sum(hearts_points(c) for c in hand)
				points_left_to_be_played = 26-points_previously_played-points_in_play-points_in_hand

				tricks_left = 13-state.trick_count
				#how many points can you expect in a trick
				trick_danger =  points_left_to_be_played/(tricks_left+1)
				#how many points can you expect in the rest of this trick
				play_danger = trick_danger*(3-len(played_so_far))*state.trick_count
				if not len(on_suit): #you can't follow suit and know you'll lose
					return legals[0] #play most powerful card.
				elif play_danger < 1.5 and not all(hearts_points(c) for c in legals): 
					#okay with winning, play most powerful point-free card.
					return [c for c in legals if not hearts_points(c)][0]
				else: #try to lose
					rank_to_beat = max(c.rank for c in played_so_far)
					worse_cards = [c for c in legals if c.rank < rank_to_beat]
					if len(worse_cards):
						return worse_cards[0] #play your highest card that will lose.
					else:
						#it isn't clear how this should be chosen so it's a hyperparam.
						if sort_rank:
							legals.sort(key=lambda c: c.rank)
						return legals[int((losing_index-.0000001)*len(legals))]

		return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))
	return smart_controller

def play_with_stupid(num_humans=1, game=HeartsGame()):
	game_state = ControlledGame(game, [random_controller(i) if i>num_humans-1 else input_controller(i) for i in range(4)])
	print([p.total_points() for p in game_state.players] if game_state else "game over.")

def test_bug():
	test_bug_hands = [pset(filter(lambda card: card.suit == suit, deck52)) for suit in suit_keys]
	test_bug_state = GameState(trick_leader = 0,
							   players=PlayerVec.create(
									[HeartsPlayer(played=v(),
												  won = v(),
												  prev_player = None,
												  penalty = 0,
												  hand=test_hand) 
										for test_hand in test_bug_hands]))
	return play_with_stupid(1, HeartsGame(test_bug_state))

controller_cast = {
	'Taz': random_controller,
	'Deedee' : random_legal_controller,
	'Dexter':  hyper_smart_controller(), 

}

def c_from_name(name):
	c = controller_cast.get(name)
	return c if c else input_controller

def cs_from_names(names):
	return [c_from_name(name)(i) for i,name in enumerate(names)]

def game_from_cast(names, game=HeartsGame()):
	return ControlledGame(game, cs_from_names(names))

def play_from_cast(names, game=HeartsGame()):
	game_state = game_from_cast(names, game)
	print("final scores: ")
	for i in range(4):
		print(f"{names[i]}: {game_state.players[i].total_points()}")

def iterate_from_controllers(controllers, iterations):
	scores = [0,0,0,0]
	for _ in range(iterations):
		game_state = ControlledGame(HeartsGame(),controllers)
		for i in range(4):
			scores[i] += game_state.players[i].total_points()
	s = sum(scores)
	return ([score/s for score in scores])

def iterate_from_cast(names, iterations=100):
	return iterate_from_controllers(cs_from_names(names), iterations)


def find_best_Dexter(iterations=10, innerations=30):
	mid = .50
	delta = .25
	for _ in range(iterations):
		low, high = mid-delta, mid+delta
		scores = iterate_from_controllers([hyper_smart_controller(losing_index=low)(0),
										   hyper_smart_controller(losing_index=mid)(1),
									       hyper_smart_controller(losing_index=high)(2),
									       random_legal_controller(3)], innerations)
		print(f"{low} - {mid} - {high}")
		print(scores)
		nextmid = [low, mid, high, mid]

		delta /= 2
		mid = nextmid[scores.index(min(scores))]







import pandas as pd
import numpy as np

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

#returns X, y
def np_from_controllers(controllers, iterations=10):
	expected_rows = iterations*52*4
	X = []#np.empty(shape=(expected_rows, total_cols))
	y = []#np.empty(shape=(expected_rows,))
	xi = 0
	for i in range(iterations):
		#rand.shuffle(controllers)
		state, cont = HeartsGame(pass_phase=False, num_hands=1)
		starting_xi = xi
		while cont:
			state, cont = cont(controllers)
			X.append(featurize_state(state)) #featurize_state(state, X[xi])
			#temporarily store the current player.
			y.append(state.current_turn())#y[xi] = state.current_turn()
			xi += 1

		scores = [p.total_points() for p in state.players]
		mins = min(scores)
		maxs = max(scores)
		for yi in range(starting_xi, xi):
			#get the score for the current players.
			y[yi] = (scores[y[yi]]-mins) / (maxs-mins)
	return np.array(X),np.array(y)





from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error as mse


def sklearn_controller_raw(model, controllers = cs_from_names(["Dexter", "Deedee", "Taz", "Taz"])):
	X_train, y_train = np_from_controllers(controllers, 3)
	model.fit(X_train, y_train)

	no_pass = lambda _,__,___:None

	#def weighted_random_index(xs):
		# r = rand.uniform(0,sum(xs))
		# so_far = 0
		# sxs = xs.copy()
		# sxs.sort()
		# for i,weight in enumerate(sxs):
		# 	so_far += weight
		# 	if so_far >= r:
		# 		return i
		# print(f"weighted random index couldn't solve {sxs}")
		# return 0

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
			#lhand = [c for c in hand if state.legal_card(c,hand)]
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
				y_hat =  (y_hat-mn) / (mx-mn)
				y_hat = 1 - y_hat
				#rind = weighted_random_index(y_hat)
				#print(f"fine hand: {[c.key for c in lhand]}, picking: {lhand[rind].key}")
				#return lhand[rind]
				choice = rand.choices(population=lhand, weights=y_hat)[0]
				return choice
			else:
				return rand.choice(lhand)
		
		return HeartsAdapter(pid, HeartsController(pass_cards=no_pass, 
												   play_trick=play_trick))
	return controller
			
def Krang():
	return sklearn_controller_raw(MLPRegressor(hidden_layer_sizes=(500,400), max_iter=1000))

def Walter():
	return sklearn_controller_raw(LinearRegression())
		
controller_cast['Krang'] = Krang()
controller_cast['Walter'] = Walter()

'''
TODO:
   + improve printing:
      + sort hand
      +- highlight playable cards
      + show intermediate plays
      + show winner of trick.
   + figure out how continuations are passed.
     + write lookahead AI.
   + proper passing and game end.
   + write smart AI:
   + write the recorder driver.
     + figure out a basic featurization.  
     - multithreading?
   - make a sklearn controller
     - takes a sklearn model
     - uses the predict method to get a list of weights for different cards.
     - uses the weights to randomly try a response.
'''
