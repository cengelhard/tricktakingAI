

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
	def with_penalty(self, amount=1):
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
	#starts at 0, goes up each hand.
	hand_count = unsigned
	#only used by play_card controller fns.
	current_turn = unsigned

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
	#returns both positional and list form.
	def played_this_trick(self):
		lens = [len(p.played) for p in self.players]
		m = max(lens)
		positional = pvector([p.played[-1] if len(p.played)==m else None for p in self.players])
		return positional, pvector(filter(None, positional))
	#returns none if there are 4 cards played... ambiguous as far as it knows.
	def hand_done(self):
		return all(len(p.played)==13 for p in self.players)
	def game_done(self):
		return any(p.total_points() > 50 for p in self.players)


def deal_4_players(deck):
	return [pset(h) for h in [deck[:13], deck[13:26], deck[26:39], deck[39:]]]


default_state = GameState(players=PlayerVec.create([HeartsPlayer() for _ in range(4)]))


#returns a function that starts the game.
#a msg, 4-tuples of functions for choices, and a second 'continuation' function.
#each player passes a callback to their function which is passed their hand and returns their choices.
#those returns get combined together into the continuation function.
#that returns a new continuation
def HeartsGame(initial_state = default_state, initial_cont = "play hand", initial_pid = -1):

	def nextp(i):
		return (i+1)%4

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
			choices = [pset(choice) for choice in private_call(controllers, "pass_cards", unpassed_state)]
			#choices = [pset(f(unpassed_state)) for f in chooser_fns]
			bad_choices = [len(cs) != 3 or (not cs.issubset(unpassed_state.players[i].hand)) for i,cs in enumerate(choices)]
			if any(bad_choices):
				#try again with penalties.
				return play_hand(prior_state.map_players(lambda i, p: p if not bad_choices[i] else p.with_penalty()))
			def pass_helper(pass_to):
				pass_from = prior_state.passing_from(pass_to)
				return hands[pass_to].difference(choices[pass_to]).union(choices[pass_from]) 
			new_hands = [pass_helper(i) for i in range(4)]
			state = prior_state.map_players(lambda i, p: p.set(hand=new_hands[i], played=v(), prev_player=p))
			
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
		played, only_played = state.played_this_trick()
		turn_state = state.set(current_turn=pid)
		def cont(controllers):
			card = controllers[pid].play_trick(turn_state.private_to(pid)) #only care about one of the returns.
			lsuit = played[state.trick_leader].suit
			not_in_hand = not (card in hand)
			not_first_play = len(only_played) != 4
			wrong_suit = card.suit != lsuit
			no_excuse = lsuit in [c.suit for c in hand]
			if not_in_hand or (not_first_play and wrong_suit and no_excuse):
				#try again with penalty
				return play_trick_card(pid, state.set_player(pid, player.with_penalty()))

			played_state = turn_state.set_player(pid, player.play_card(card))
			private_call(controllers, "alert_played", played_state)

			new_played, new_only_played = played_state.played_this_trick()

			if len(new_only_played) < 4:
				return play_trick_card(nextp(pid), played_state)
			else:
				led_card = new_only_played[nextp(pid)] #loop around to see the leader.
				lsuit = led_card.suit
				best_pid = -1
				best_rank = led_card.rank
				winner = None
				for i in range(4):
					card2 = new_played[i]
					if card2.suit == lsuit and card2.rank >= best_rank:
						best_pid = i
						best_rank = card2.rank
						winner = played_state.players[i]
				winner_state = played_state.set(trick_leader=best_pid).set_player(best_pid, winner.set(won = winner.won.extend(new_played)))
				if winner_state.hand_done():
					private_call(controllers, "alert_hand_complete", winner_state)
					if winner_state.game_done():
						return winner_state, None
					else:
						moon_shooters = pvector(p.shot_the_moon() for p in winner_state.players)
						winner_state = winner_state.set(hand_count=winner_state.hand_count+1)
						if any(moon_shooters):
							private_call(controllers, "alert_shot_moon", winner_state)
							moon_shooter = moon_shooters.index(True)
							return play_hand(winner_state.map_players(lambda i, p: p.with_penalty(-26 if i==moon_shooter else 26)))
						else:
							return play_hand(winner_state)
				else:
					private_call(controllers, "alert_trick_complete", winner_state)
					return play_trick_card(best_pid, winner_state)	
		return turn_state, cont


	return play_hand(initial_state) if initial_cont=="play hand" else play_trick(initial_state, initial_pid)

def ControlledGame(game, controllers):
	state, cont = game
	while cont:
		try:
			state, cont = cont(controllers)
		except QuitGameException:
			print("quitting game")
			return
	return cont

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
		current_pid = state.current_turn
		if current_pid == pid: #not necessary in practice but go off.
			return ctrlr.play_trick(my_hand(state), state)

	#alerts
	#TODO: find a clever way to factor these.
	def alert_played(state):
		f = ctrlr.get('alert_played')
		if f:
			curr = state.current_turn
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
		alert_hand_complete=alert_hand_complete
	)

#a completely random AI.
def stupid_controller(pid):
	def pass_cards(hand, passing_to, points):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		if len(hand):
			return rand.choice(tuple(hand))
		else:
			print("was passed an empty hand?")

	return HeartsAdapter(pid, HeartsController(pass_cards=pass_cards, play_trick=play_trick))

from termcolor import cprint

def stupid_test():
	game_state = ControlledGame(HeartsGame(), [stupid_controller(i) for i in range(4)])
	#print([p.total_points() for p in game_state])

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
		return pass_cards(hand)

	def play_trick(hand, state):
		print(f"---player {pid}'s turn---")

		#TODO: print how the previous trick went.

		played, just_played = state.played_this_trick()
		nplayed = len(just_played)
		if nplayed == 4:
			print("You are leading the trick.")
		else:
			leader = pid+1
			while played[leader] == None:
				leader = (leader+1)%4
			print(f"played so far: {[c.key for c in played.extend(played)[leader:leader+nplayed]]}")
			
		hand = list(hand)
		print_hand(hand)
		try:
			choice = hand[int(_input(hand))]
			return choice
		except QuitGameException:
			raise QuitGameException()
		except:
			pass
		print("something wasn't right")
		return play_trick(hand, state)

	def alert_played(other_pid, card):
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

def play_with_stupid(num_humans=1, game=HeartsGame()):
	game_state = ControlledGame(game, [stupid_controller(i) if i>num_humans-1 else input_controller(i) for i in range(4)])
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

'''
TODO:
   - improve printing:
      - sort hand
      - highlight playable cards
      + show intermediate plays
      + show winner of trick.
   + figure out how continuations are passed.
     + write lookahead AI.
   - proper passing and game end.
   - write smart AI:
'''
