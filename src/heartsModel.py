from deckView import deck52
from heartsView import GameState, HeartsPlayer, PlayerVec
import random as rand
from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)


def deal_4_players(deck):
	return [pset(h) for h in [deck[:13], deck[13:26], deck[26:39], deck[39:]]]

default_state = GameState(players=PlayerVec.create([HeartsPlayer() for _ in range(4)]))

def nextp(i,d=1):
	return (i+d)%4

#returns a tuple of (state, continuation)
#pass the continuation a list of controllers, and it will return a new (state, continuation)
def HeartsGame(initial_state = default_state, 
			   initial_cont = "play hand", 
		       initial_pid = -1,
		       num_hands = 3,
		       pass_phase = True):
	def init():
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
				new_state = state.set(last_played=leader_i).set_player(leader_i, leader_p.play_card(two_of_clubs))
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

				played_state = substate.set(last_played=pid).set_player(pid, player.play_card(card))
				private_call(controllers, "alert_played", played_state)

				played, only_played = played_state.played_this_trick()

				if len(only_played) < 4:
					return play_trick_card(nextp(pid), played_state)
				else:
					led_card = only_played[0]#only_played[nextp(pid)] #loop around to see the leader.
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
						moon_shooters = pvector(p.shot_the_moon() for p in winner_state.players)

						if any(moon_shooters):
							private_call(controllers, "alert_shot_moon", winner_state)
							moon_shooter = moon_shooters.index(True)
							winner_state = winner_state.map_players(lambda i, p: p.with_penalty(-26 if i==moon_shooter else 26))

						private_call(controllers, "alert_hand_complete", winner_state)
						if winner_state.hand_count == num_hands-1:
							return winner_state, None
						else:
							return play_hand(winner_state.set(hand_count=winner_state.hand_count+1,
															trick_count=0))
					else:
						private_call(controllers, "alert_trick_complete", winner_state)
						return play_trick_card(best_pid, winner_state.set(trick_count=winner_state.trick_count+1))	
			return state, cont

		return play_hand(initial_state) if initial_cont=="play hand" else play_trick_card(initial_pid, initial_state)
	return init

#single_hand_game = HeartsGame(pass_phase=False, num_hands=1)


