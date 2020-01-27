

from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)
from deck import deck52, Card
import random as rand

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

	def points(self):
		return sum(map(hearts_points, self.won)) + self.penalty
	def total_points(self):
		return self.points() + (self.prev_player.total_points() if self.prev_player else 0)
	def privatize(self):
		return self.set(hand=s())
	def play_card(self, card):
		return self.set(played = self.played.append(card), hand=self.hand.remove(card))
	def with_penalty(self):
		return self.set(penalty=self.penalty+1)


#the four players
class GameState(CheckedPVector):
	__type__ = HeartsPlayer
	#__invariant__ = len4

	def trick_leader(self):
		m = max(len(p.played) for p in self)
		for i,p in enumerate(self):
			if len(p.played)==m:
				return i
	def private_to(self, i): #i should not be able to see others' hands
		return GameState.create([self[j] if j==i else self[j].privatize() for j in range(4)])

	#returns both positional and list form.
	def played_this_trick(self):
		lens = [len(p.played) for p in self]
		m = max(lens)
		positional = pvector([p.played[-1] if len(p.played)==m else None for p in self])
		return positional, pvector(filter(None, positional))
	def hand_done(self):
		return all(len(p.played)==13 for p in self)
	def game_done(self):
		return any(p.total_points() > 50 for p in self)

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
		deck = deck52.copy()
		rand.shuffle(deck)
		hands = deal_4_players(deck)

		def pass_left(chooser_fns):
			
			choices = [pset(chooser_fns[i](hands[i])) for i in range(4)]
			bad_choices = [len(cs) != 3 for cs in choices]
			if any(bad_choices):
				#try again with penalties.
				return pass_left(GameState.create([prior_state[i] if not bad_choices[i] else prior_state[i].with_penalty() for i in range(4)]))

			new_hands = [hands[i].difference(choices[i]).union(choices[nextp(i)]) for i in range(4)]
			state = GameState.create([prior_state[i].set(hand=new_hands[i],
														 played = v(), 
														 prev_player=prior_state[i]) for i in range(4)])
			
			#imperative programming outa nowhere!
			leader_i = 0
			leader_p = None
			two_of_clubs = None 

			for i in range(4):
				p = state[i]
				h = p.hand
				for c in h:
					if c.key == "2♣":
						leader_i = i
						leader_p = p
						two_of_clubs = c
						break
				if two_of_clubs:
					break
			print(f"2 of clubs went to {leader_i}")
			new_state = state.set(leader_i, leader_p.play_card(two_of_clubs))
			return play_trick_card(nextp(leader_i), new_state)

		return "pass left", pass_left

	def play_trick_card(pid, state):
		player = state[pid]
		hand = player.hand
		played, only_played = state.played_this_trick() #now indexed by pid
		if len(only_played) != 4 and played[pid] != None:
			print(f"{pid} already played card {played[pid].key}. cards in play: {[c.key if c else 'no' for c in played]}")
		def cont(chooser_fns):
			card = chooser_fns[pid](hand, state.private_to(pid), played)
			valid_card = (len(only_played) == 0)
			if not valid_card:
				lsuit = only_played[0].suit
				valid_card |= (card.suit == lsuit)
				valid_card |= (lsuit not in [c.suit for c in hand])
				valid_card &= (card in hand)
				if not valid_card:
					#try again with penalty
					#print(f"{card.key} no match for {lsuit}")
					return play_trick_card(pid, state.set(pid, player.with_penalty()))
			
			played_state = state.set(pid, player.play_card(card))

			new_played, new_only_played = played_state.played_this_trick()

			print(f"{pid} played {card.key}")

			if len(new_only_played) < 4:
				return play_trick_card(nextp(pid), played_state)
			else:
				led_card = new_only_played[nextp(pid)] #loop around to see the leader.
				lsuit = led_card.suit
				leader_id = state.trick_leader()
				best_pid = leader_id
				best_rank = led_card.rank
				winner = played_state[best_pid]
				for i in range(4):
					card2 = new_played[i]
					if card2.suit == lsuit and card2.rank > best_rank:
						#normalize to player id.
						best_pid = i
						best_rank = card2.rank
						winner = played_state[i]
				print(f"finishing trick. winner: {best_pid} with {winner.played[-1].key}")
				print(f"played cards {[c.key for c in new_played]}")
				winner_state = played_state.set(best_pid, winner.set(won = winner.won.extend(new_played)))
				if winner_state.hand_done():
					print("hand done")
					print(f"score so far: {[p.total_points() for p in winner_state]}")
					print("--------------------------")
					if winner_state.game_done():
						print("game done")
						return "game over", winner_state
					else:
						print("game not done")
						return play_hand(winner_state)
				else:
					print("hand not done.")
					return play_trick_card(best_pid, winner_state)	
		return "play a card", cont

	initial_state = GameState.create([HeartsPlayer(played=v(),
												    won = v(),
												    prev_player = None,
												    penalty = 0,
												    hand=s()) for _ in range(4)])
	return play_hand(initial_state)

def stupid_choose_pass(hand):
	return rand.sample(hand, 3)

all_stupid_pass = [stupid_choose_pass for _ in range(4)]

def stupid_choose_trick(hand, state, played):
	if len(hand):
		#print("passed good hand")
		return rand.choice(tuple(hand))
	else:
		print("was passed an empty hand?")

all_stupid_choose = [stupid_choose_trick for _ in range(4)]

def stupid_test():
	msg, cont = HeartsGame()
	while msg != "game over":
		if msg=="pass left":
			msg, cont = cont(all_stupid_pass)
		elif msg=="play a card":
			msg, cont = cont(all_stupid_choose)
		else:
			break
	game_state = cont
	print(p.total_points() for p in game_state)


