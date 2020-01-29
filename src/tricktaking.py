

from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)
from deck import deck52, Card
import random as rand
import sys

def hearts_points(card):
	return 1 if card.suit == "♥" else 13 if card.key == "Q♠" else 0

len4 = lambda p: (len(p)==4, "must be len 4")


#public information about a player in a hand of Hearts.
class HeartsPlayer(PRecord):

	#cards you've played previously this hand.
	played = pvector_field(Card)
	#cards you've won in previous tricks this hand.
	won    = pvector_field(Card)
	hand   = pset_field(Card)

	#What you did in the previous hand.
	prev_player = field() #field(type=('tricktaking.HeartsPlayer', type(None)))

	penalty = field(int)


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

#the four players
class GameState(PRecord):

	players = field(PlayerVec, invariant=len4)
	trick_leader = field(int, invariant=lambda x: (x<4, f"trick_leader cannot be {x}"))

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


#returns a function that starts the game.
#a msg, 4-tuples of functions for choices, and a second 'continuation' function.
#each player passes a callback to their function which is passed their hand and returns their choices.
#those returns get combined together into the continuation function.
#that returns a new continuation
def HeartsGame():

	def nextp(i):
		return (i+1)%4

	#takes a previous state from previous hands.
	def play_hand(prior_state):

		hands = None
		if len(prior_state.players[0].hand):
			#it is possible that the prior state already has hands set.
			hands = [p.hand for p in prior_state]
		else:
			deck = deck52.copy()
			rand.shuffle(deck)
			hands = deal_4_players(deck)

		def pass_left(chooser_fns):
			
			choices = [pset(chooser_fns[i](hands[i])) for i in range(4)]
			bad_choices = [len(cs) != 3 for cs in choices]
			if any(bad_choices):
				#try again with penalties.
				return pass_left(prior_state.map_players(lambda i, p: p if not bad_choices[i] else p.with_penalty()))

			new_hands = [hands[i].difference(choices[i]).union(choices[nextp(i)]) for i in range(4)]
			state = prior_state.map_players(lambda i, p: p.set(hand=new_hands[i], played=v(), prev_player=p))
			
			#imperative programming outa nowhere!
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

		return "pass left", pass_left

	def play_trick_card(pid, state):
		player = state.players[pid]
		hand = player.hand
		played, only_played = state.played_this_trick()
		def cont(chooser_fns):
			card = chooser_fns[pid](hand, state.private_to(pid))
			valid_card = (len(only_played) == 4)
			if not valid_card:
				lsuit = only_played[0].suit
				valid_card |= (card.suit == lsuit)
				valid_card |= (lsuit not in [c.suit for c in hand])
				valid_card &= (card in hand)
				if not valid_card:
					#try again with penalty
					return play_trick_card(pid, state.set_player(pid, player.with_penalty()))
			
			played_state = state.set_player(pid, player.play_card(card))

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
				winner_state = played_state.set_player(best_pid, winner.set(won = winner.won.extend(new_played)))
				if winner_state.hand_done():
					if winner_state.game_done():
						return "game over", winner_state
					else:
						moon_shooters = pvector(p.shot_the_moon() for p in winner_state.players)
						if (any(moon_shooters)):
							moon_shooter = moon_shooters.index(True)
							return play_hand(winner_state.map_players(lambda i, p: p.with_penalty(-26 if i==moon_shooter else 26)))
						else:
							return play_hand(winner_state)
				else:
					return play_trick_card(best_pid, winner_state)	
		return "play a card", cont

	initial_state = GameState(players=PlayerVec.create([HeartsPlayer(played=v(),
												    won = v(),
												    prev_player = None,
												    penalty = 0,
												    hand=s()) for _ in range(4)]))
	return play_hand(initial_state)



def ControlledGame(game, controllers):
	msg, cont = game()
	while msg != "game over":
		try:
			msg, cont = cont([c[msg] for c in controllers])
		except QuitGameException:
			print("quitting game")
			return
	return cont

#a completely random AI.
def stupid_controller(pid):
	def pass_left(hand):
		return rand.sample(hand, 3)

	def play_trick(hand, state):
		if len(hand):
			return rand.choice(tuple(hand))
		else:
			print("was passed an empty hand?")

	#doesn't ask anything, just informing you for possible IO
	def someone_else(other_pid, card, state):
		pass

	return {'pass left': pass_left, 
			'play a card': play_trick,
			'someone else': someone_else}

def stupid_test():
	game_state = ControlledGame(HeartsGame, [stupid_controller(i) for i in range(4)])
	print([p.total_points() for p in game_state])

class QuitGameException(Exception):
	pass

def input_controller(pid):

	def print_hand(hand):
		print("your hand:")
		print("|".join(f"{i}:{card.key}" for i,card in enumerate(hand)))

	def _input(hand):

		string = input("--->")
		if string[0] == '/':
			command = string[1:]
			if command == "quit":
				raise QuitGameException()
			elif command == "hand":
				print_hand(hand)
				return _input(hand)
		return string

	def pass_left(hand):
		print(f"player {pid}, please choose 3 card indecies, separated by commas.")
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
		return pass_left(hand)

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

	#doesn't ask anything, just informing you for possible IO
	#(doesn't even give you information that a future msg won't.)
	def someone_else(other_pid, card, state):
		print(f"{other_pid} played {card.key}")

	return {'pass left': pass_left,
			'play a card': play_trick,
			'someone else': someone_else}

def play_with_stupid():
	game_state = ControlledGame(HeartsGame, [stupid_controller(i) if i>0 else input_controller(i) for i in range(4)])
	print([p.total_points() for p in game_state.players] if game_state else "game quit early")


